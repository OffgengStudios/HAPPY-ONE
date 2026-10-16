import hashlib
import io
import socket
import struct
import zipfile
from pathlib import PureWindowsPath
from typing import Literal
from uuid import uuid4
from xml.etree import ElementTree

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.iam.models import now
from app.modules.supply.models import Document, Participant
from app.storage.s3 import get_storage_client

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCX_MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
ScanResult = Literal["AVAILABLE", "REJECTED", "SCANNING"]


def validate_file(data: bytes, filename: str, declared: str) -> tuple[str, str]:
    filename = PureWindowsPath(filename).name
    if not filename or len(filename) > 200 or any(ord(c) < 32 for c in filename):
        raise ApiError(422, "FILE_TYPE_NOT_ALLOWED", "Choose a file with a valid filename.")
    if not data or len(data) > settings.file_max_bytes:
        raise ApiError(
            413, "FILE_TOO_LARGE", "Choose a non-empty CV within the configured file size limit."
        )
    extension = PureWindowsPath(filename).suffix.lower()
    try:
        if extension == ".pdf" and declared == PDF and data.startswith(b"%PDF-"):
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or len(reader.pages) > 100:
                raise ValueError("PDF cannot be verified")
            return filename, PDF
        if extension == ".docx" and declared == DOCX and data.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 1000 or sum(v.file_size for v in entries) > 26214400:
                    raise ValueError("Document exceeds expansion limit")
                names = set(archive.namelist())
                if not {"[Content_Types].xml", "word/document.xml"} <= names:
                    raise ValueError("Invalid Word document")
                if any(
                    "vbaproject" in name.lower() or name.startswith("/") or ".." in name.split("/")
                    for name in names
                ):
                    raise ValueError("Unsupported document content")
                xml = [
                    archive.read(name).decode("utf-8-sig")
                    for name in ("[Content_Types].xml", "word/document.xml")
                ]
                if any(
                    "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper()
                    for content in xml
                ):
                    raise ValueError("Unsupported XML declarations")
                types, document = [ElementTree.fromstring(content) for content in xml]
                if (
                    types.tag
                    != "{http://schemas.openxmlformats.org/package/2006/content-types}Types"
                    or document.tag
                    != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"
                ):
                    raise ValueError("Invalid Word document XML")
                if not any(
                    entry.attrib.get("PartName") == "/word/document.xml"
                    and entry.attrib.get("ContentType") == DOCX_MAIN
                    for entry in types
                ):
                    raise ValueError("Word document content type is missing")
            return filename, DOCX
    except Exception:
        raise ApiError(
            422, "FILE_TYPE_NOT_ALLOWED", "The file could not be validated as a supported CV."
        ) from None
    raise ApiError(422, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF or DOCX with a matching file type.")


def scan(data: bytes) -> ScanResult:
    if not settings.file_scan_host:
        return "SCANNING"
    try:
        # clamd's INSTREAM protocol scans bytes, never a client-supplied filesystem path.
        with socket.create_connection(
            (settings.file_scan_host, settings.file_scan_port), timeout=10
        ) as connection:
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(data), 65536):
                chunk = data[offset : offset + 65536]
                connection.sendall(struct.pack("!I", len(chunk)) + chunk)
            connection.sendall(struct.pack("!I", 0))
            response = bytearray()
            while len(response) < 4096:
                chunk = connection.recv(1024)
                if not chunk:
                    break
                response.extend(chunk)
                if b"\0" in chunk or b"\n" in chunk:
                    break
            result = bytes(response).strip(b"\0\n ")
            if result == b"stream: OK":
                return "AVAILABLE"
            if result.startswith(b"stream: ") and result.endswith(b" FOUND"):
                return "REJECTED"
    except OSError:
        pass
    return "SCANNING"


def upload(
    db: Session, row: Participant, data: bytes, filename: str, declared: str, actor: object
) -> Document:
    name, mime = validate_file(data, filename, declared)
    result = scan(data)
    version = (
        db.scalar(
            select(func.max(Document.version_number)).where(Document.participant_id == row.id)
        )
        or 0
    ) + 1
    document = Document(
        participant_id=row.id,
        document_code="DOC-" + uuid4().hex.upper(),
        storage_key=f"participants/{row.id}/cv/{uuid4().hex}",
        original_filename=name,
        mime_type=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        version_number=version,
        scan_status=result,
        created_by=actor,
        scan_details={"provider": "clamd" if settings.file_scan_host else "unconfigured"},
    )
    if result != "REJECTED":
        try:
            get_storage_client().put_object(
                Bucket=settings.s3_bucket, Key=document.storage_key, Body=data, ContentType=mime
            )
        except Exception:
            raise ApiError(
                503, "STORAGE_UNAVAILABLE", "Private storage is unavailable. Retry the upload."
            ) from None
    db.add(document)
    if result != "REJECTED" and not row.current_cv_id:
        row.cv_status = "UPLOADED"
    return document


def verified_bytes(document: Document) -> bytes:
    try:
        result = get_storage_client().get_object(
            Bucket=settings.s3_bucket, Key=document.storage_key
        )
        body = result["Body"]
        try:
            data = body.read(settings.file_max_bytes + 1)
        finally:
            body.close()
        if len(data) != document.size_bytes or hashlib.sha256(data).hexdigest() != document.sha256:
            raise ValueError("Stored file integrity mismatch")
        return data
    except Exception:
        raise ApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "The stored CV could not be verified. Contact an administrator.",
        ) from None


def archive(document: Document, row: Participant) -> None:
    document.scan_status = "ARCHIVED"
    document.archived_at = now()
    if row.current_cv_id == document.id:
        row.current_cv_id = None
        row.cv_status = "MISSING"

"""Stateless HAPPY processing service. Never imports the standalone candidate API."""

import base64
import binascii
import hmac
import os
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from pdfplumber.utils.exceptions import PdfminerException

os.environ["HAPPY_PROCESSING_ONLY"] = "1"

from classifier.classifier import classify_cv  # noqa: E402
from parser.extractor import ExtractionError, extract_text  # noqa: E402
from parser.parser import parse_cv  # noqa: E402

MAX_BYTES = 10 * 1024 * 1024
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=200)
    mime_type: Literal[
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    content_base64: str = Field(min_length=4, max_length=((MAX_BYTES + 2) // 3) * 4)


class Suggestion(BaseModel):
    field: Literal["first_name", "surname", "other_names", "phone_raw", "email", "skills", "job_role"]
    value: str | list[str]
    confidence: float | None = Field(default=None, ge=0, le=1)


class ParseResponse(BaseModel):
    schema_version: Literal["1"] = "1"
    provider: Literal["happy-cv-parser"] = "happy-cv-parser"
    model: str = "extraction-classifier-v1"
    suggestions: list[Suggestion]


def authenticated(request: Request) -> None:
    expected = os.environ.get("HAPPY_PARSER_TOKEN", "")
    header = request.headers.get("authorization", "")
    supplied = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
    if len(expected) < 32 or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Valid machine credentials are required.")


app = FastAPI(title="HAPPY CV processing", docs_url=None, redoc_url=None)


@app.middleware("http")
async def bounded_request(request: Request, call_next):
    # Bound the streamed body too; Content-Length alone is not trustworthy.
    if request.method == "POST":
        total = 0
        chunks = []
        async for chunk in request.stream():
            total += len(chunk)
            if total > 14 * 1024 * 1024:
                response = JSONResponse({"detail": "Request too large."}, status_code=413)
                response.headers["Cache-Control"] = "no-store"
                return response
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    # FastAPI's default validation response can echo CV contents.
    return JSONResponse({"detail": "Check the parser request."}, status_code=422)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "happy-cv-parser"}


@app.post("/api/v1/integrations/happy/parse", response_model=ParseResponse)
def parse(data: ParseRequest, machine: Annotated[None, Depends(authenticated)]) -> ParseResponse:
    extension = PureWindowsPath(data.filename).suffix.lower()
    if (extension, data.mime_type) not in {(".pdf", PDF), (".docx", DOCX)}:
        raise HTTPException(422, "Filename and MIME type must agree.")
    try:
        content = base64.b64decode(data.content_base64, validate=True)
        if not content or len(content) > MAX_BYTES:
            raise ValueError("size")
        if extension == ".pdf" and not content.startswith(b"%PDF-"):
            raise ValueError("signature")
        # A generated path keeps user filenames and identifiers out of extractor logs.
        with tempfile.TemporaryDirectory(prefix="happy_parse_") as directory:
            path = Path(directory) / ("document" + extension)
            path.write_bytes(content)
            if extension == ".docx":
                with zipfile.ZipFile(path) as archive:
                    entries = archive.infolist()
                    if len(entries) > 1000 or sum(v.file_size for v in entries) > 26214400:
                        raise ValueError("expansion")
                    if not {"[Content_Types].xml", "word/document.xml"} <= set(archive.namelist()):
                        raise ValueError("format")
                    if any("vbaproject" in e.filename.lower() for e in entries):
                        raise ValueError("macro")
            else:
                import pdfplumber

                with pdfplumber.open(path) as pdf:
                    if not 1 <= len(pdf.pages) <= 100:
                        raise ValueError("pages")
            text = extract_text(path)
        parsed = parse_cv(text)
        classification = classify_cv(text, parsed.skills)
    except (binascii.Error, ValueError, OSError, zipfile.BadZipFile, ExtractionError, PdfminerException):
        raise HTTPException(422, "The document could not be processed as a supported CV.") from None
    suggestions = []
    name_parts = (parsed.name or "").split()
    for field, value in (
        ("first_name", name_parts[0] if name_parts else None),
        ("surname", name_parts[-1] if len(name_parts) > 1 else None),
        ("other_names", " ".join(name_parts[1:-1]) or None),
        ("email", parsed.email),
        ("phone_raw", parsed.phone),
        ("skills", parsed.skills),
    ):
        if value:
            # Heuristic fields have no calibrated confidence; do not invent percentages.
            suggestions.append(Suggestion(field=field, value=value))
    if classification.confidence > 0:
        suggestions.append(
            Suggestion(
                field="job_role", value=classification.subcategory,
                confidence=classification.confidence,
            )
        )
    if not suggestions:
        raise HTTPException(422, "No reviewable fields were extracted.")
    return ParseResponse(suggestions=suggestions)

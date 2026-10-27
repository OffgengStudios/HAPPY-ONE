"""Opt-in acceptance against an actual provisioned clamd; never patches scan success."""

import base64
import io
import os
import socket
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import select
from test_public_intake_integration import ORIGIN, payload, staff_login, submit

from app.core.config import settings
from app.main import app
from app.modules.supply import files
from app.modules.supply.models import Participant

pytest_plugins = ["test_public_intake_integration"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_REAL_SCANNER") != "1",
        reason="Requires actual provisioned ClamAV.",
    ),
]


def clean_pdf():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    return output.getvalue()


def eicar():
    return base64.b64decode(
        "WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FS"
        "LVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo="
    )


def test_actual_scanner_accepts_pdf_docx_and_rejects_eicar():
    assert settings.file_scan_host
    output = io.BytesIO()
    with ZipFile(output, "w") as document:
        document.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/></Types>',
        )
        document.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Synthetic clean fixture</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )
    assert files.scan(clean_pdf()) == "AVAILABLE"
    assert files.scan(output.getvalue()) == "AVAILABLE"
    assert files.scan(eicar()) == "REJECTED"


def test_actual_scan_download_permissions_and_recovery(db, monkeypatch):
    public = TestClient(app, headers=ORIGIN)
    assert submit(public, payload()).status_code == 202
    participant = db.scalar(select(Participant))
    staff = staff_login(db, "ADMIN")
    original_port = settings.file_scan_port
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
    monkeypatch.setattr(settings, "file_scan_port", unused_port)
    uploaded = staff.post(
        f"/api/v1/participants/{participant.id}/cv",
        data={"version": participant.version},
        files={"file": ("synthetic-clean.pdf", clean_pdf(), files.PDF)},
    )
    assert uploaded.status_code == 201, uploaded.text
    pending = uploaded.json()
    path = f"/api/v1/files/{pending['id']}/download"
    assert pending["scan_status"] == "SCANNING"
    assert staff.get(path).status_code == 409
    assert public.get(path).status_code == 401
    monkeypatch.setattr(settings, "file_scan_port", original_port)
    db.refresh(participant)
    scanned = staff.post(
        f"/api/v1/files/{pending['id']}/rescan", json={"version": participant.version}
    )
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()["scan_status"] == "AVAILABLE"
    assert staff.get(path).content == clean_pdf()
    db.refresh(participant)
    infected_output = io.BytesIO()
    infected_pdf = PdfWriter()
    infected_pdf.add_blank_page(width=100, height=100)
    infected_pdf.add_attachment("eicar.txt", eicar())
    infected_pdf.write(infected_output)
    infected = infected_output.getvalue()
    assert files.scan(infected) == "REJECTED"
    rejected = staff.post(
        f"/api/v1/participants/{participant.id}/cv",
        data={"version": participant.version},
        files={"file": ("synthetic-eicar.pdf", infected, files.PDF)},
    )
    assert rejected.status_code == 201, rejected.text
    assert rejected.json()["scan_status"] == "REJECTED"
    assert staff.get(f"/api/v1/files/{rejected.json()['id']}/download").status_code == 409

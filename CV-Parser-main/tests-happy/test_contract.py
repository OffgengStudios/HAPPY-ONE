import base64
import io
import logging
import sys
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "CV-Parser-main/cv_system_output"))
sys.path.insert(0, str(ROOT / "HAPPY_PLATFORM_CODEX/apps/api"))

from happy_service import DOCX, PDF, app  # noqa: E402
from app.integrations.cv_parser.adapter import ParserResponseContract  # noqa: E402

TOKEN = "synthetic-parser-machine-token-at-least-32-characters"
PATH = "/api/v1/integrations/happy/parse"
LINES = ["Synthetic Ada Example", "synthetic@example.org", "+233241234567", "Skills", "Python, Excel, SQL"]


def document(kind):
    target = io.BytesIO()
    if kind == "pdf":
        canvas = Canvas(target)
        for index, line in enumerate(LINES):
            canvas.drawString(60, 780 - index * 25, line)
        canvas.save()
    else:
        doc = Document()
        for line in LINES:
            doc.add_paragraph(line)
        doc.save(target)
    return target.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HAPPY_PARSER_TOKEN", TOKEN)
    with TestClient(app) as instance:
        yield instance


def request(kind="pdf", content=None):
    return {
        "filename": "synthetic." + kind,
        "mime_type": PDF if kind == "pdf" else DOCX,
        "content_base64": base64.b64encode(document(kind) if content is None else content).decode(),
    }


@pytest.mark.parametrize("kind", ["pdf", "docx"])
def test_real_extraction_matches_happy_contract(client, kind, caplog):
    with caplog.at_level(logging.INFO):
        response = client.post(PATH, json=request(kind), headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 200, response.text
    parsed = ParserResponseContract.model_validate(response.json())
    values = {item.field: item.value for item in parsed.suggestions}
    assert values["email"] == "synthetic@example.org"
    assert "skills" in values and values["first_name"] == "Synthetic"
    assert not {"Candidate", "database.session", "google_sheets", "whatsapp"} & set(sys.modules)
    assert "synthetic@example.org" not in caplog.text
    assert "+233241234567" not in caplog.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("authorization", ["", "Bearer incorrect", "Basic abc"])
def test_machine_auth_required(client, authorization):
    assert client.post(PATH, json=request(), headers={"Authorization": authorization}).status_code == 401


def test_unconfigured_credential_fails_closed(client, monkeypatch):
    monkeypatch.delenv("HAPPY_PARSER_TOKEN")
    assert client.post(PATH, json=request(), headers={"Authorization": "Bearer " + TOKEN}).status_code == 401


@pytest.mark.parametrize("content", [b"broken pdf", b"%PDF-1.7\nbroken", b"", b"PKbad"])
def test_malformed_file_returns_safe_error(client, content):
    response = client.post(PATH, json=request(content=content), headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 422
    assert "content_base64" not in response.text and "Traceback" not in response.text


def test_invalid_base64_and_mime_return_safe_error(client):
    data = request()
    data["content_base64"] = "not-base64-private-data"
    response = client.post(PATH, json=data, headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 422 and data["content_base64"] not in response.text
    data["mime_type"] = "text/plain"
    assert client.post(PATH, json=data, headers={"Authorization": "Bearer " + TOKEN}).status_code == 422


def test_health_does_not_require_candidate_database(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/candidates").status_code == 404


@pytest.mark.parametrize("stage", ["extraction", "structured_parsing"])
def test_processing_failures_do_not_log_private_exception_content(
    client, monkeypatch, caplog, stage
):
    from parser import extractor
    from parser import parser as fields

    private = "private-cv-person@example.org"

    def broken(*args, **kwargs):
        raise ValueError(private)

    if stage == "extraction":
        monkeypatch.setattr(extractor, "Document", broken)
    else:
        monkeypatch.setattr(fields, "_group_lines_into_sections", broken)
    with caplog.at_level(logging.WARNING):
        response = client.post(
            PATH, json=request("docx"), headers={"Authorization": "Bearer " + TOKEN}
        )
    assert response.status_code == (422 if stage == "extraction" else 200)
    assert private not in response.text
    assert private not in caplog.text
    assert "Traceback" not in caplog.text
    assert caplog.records  # A safe operational diagnostic is retained.

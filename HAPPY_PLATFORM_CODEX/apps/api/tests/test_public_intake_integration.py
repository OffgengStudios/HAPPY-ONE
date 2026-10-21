import csv
import io
import json
import os
from contextlib import nullcontext
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pypdf import PdfWriter
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.integrations.intake.models import IntakeDocument, PublicIntake
from app.main import app
from app.modules.cv_parser.models import ParserJob
from app.modules.iam.models import AuditEvent, User
from app.modules.supply import files
from app.modules.supply.models import (
    Consent,
    Document,
    Education,
    Experience,
    Participant,
    SensitiveProfile,
    Skill,
)
from app.storage.s3 import get_storage_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1",
        reason="Requires isolated PostgreSQL/private storage.",
    ),
]
ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture(scope="module")
def engine():
    schema, url = create_test_schema()
    instance = create_engine(url)
    try:
        yield instance
    finally:
        instance.dispose()
        drop_test_schema(schema)


@pytest.fixture
def db(engine, monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: session
    monkeypatch.setattr(
        settings, "identity_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-1")
    monkeypatch.setattr(
        settings, "supply_privacy_notice_text", "Synthetic test notice; not programme policy."
    )
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(
        settings, "supply_required_sections", ["basic", "contact", "consent", "review"]
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])
    monkeypatch.setattr(
        settings, "employer_intake_notice_text", "Synthetic employer intake notice."
    )
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])
    try:
        yield session
    finally:
        for row in session.scalars(select(IntakeDocument)):
            get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=row.storage_key)
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()


def payload():
    return {
        "submission_id": str(uuid4()),
        "basic": {"first_name": "Synthetic", "surname": "Intake"},
        "contact": {"phone_raw": "0241234567", "community": "Accra"},
        "consent": {"accepted": True, "notice_version": "SYNTHETIC-1"},
        "reviewed": True,
    }


def submit(client, data, **kwargs):
    return client.post("/api/v1/participant-intake", data={"payload": json.dumps(data)}, **kwargs)


def test_public_submission_uses_central_domain_without_accounts(db):
    client = TestClient(app, headers=ORIGIN)
    data = payload()
    data["education"] = [{"education_level": "SECONDARY"}]
    data["sensitive"] = {"disability_status": "SELF_REPORTED_NONE"}
    data["employment"] = {
        "skills": [{"skill_name": "Excel", "source": "SELF_REPORTED"}],
        "experience": [
            {
                "employer_name": "Synthetic Employer",
                "role_title": "Assistant",
                "start_date": "2025-01-01",
            }
        ],
    }
    response = submit(client, data)
    assert response.status_code == 202, response.text
    assert set(response.json()) == {"receipt_id", "status"}
    assert not client.cookies
    row = db.scalar(select(Participant))
    assert row and row.source_system == "HAMIS" and row.created_via == "PARTICIPANT"
    assert row.created_by is None and row.onboarding_status == "COMPLETE"
    assert db.scalar(select(func.count()).select_from(User)) == 0
    grant = db.scalar(select(Consent))
    assert grant.status == "ACTIVE" and grant.method == "DIGITAL"
    assert grant.source_system == "HAMIS" and grant.created_via == "PARTICIPANT"
    assert grant.created_by is None
    for model in (Education, Experience, Skill, SensitiveProfile):
        detail = db.scalar(select(model).where(model.participant_id == row.id))
        assert detail.source_system == "HAMIS" and detail.created_via == "PARTICIPANT"
        assert detail.created_by is None
    assert db.scalar(
        select(AuditEvent).where(AuditEvent.event_code == "participant_intake.submitted")
    )
    assert response.headers["cache-control"] == "no-store"
    assert submit(client, data).json() == response.json()
    assert db.scalar(select(func.count()).select_from(Participant)) == 1
    data["basic"]["first_name"] = "Changed"
    assert submit(client, data).status_code == 409
    assert client.get("/api/v1/participants").status_code == 401
    assert client.get("/api/v1/participant-intake/me").status_code == 404
    assert client.get("/api/v1/intake-operations").status_code == 401


def test_public_formula_input_is_literal_in_synchronous_and_worker_csv(db, monkeypatch):
    from app.modules.reporting import worker
    from app.modules.reporting.models import ReportExportJob
    from app.modules.supply.models import Person

    public = TestClient(app, headers=ORIGIN)
    submitted = payload()
    submitted["basic"] = {"first_name": "=1+", "surname": "1"}
    assert submit(public, submitted).status_code == 202
    assert db.scalar(select(Person)).first_name == "=1+"  # Only the export representation changes.
    staff = staff_login(db, "ADMIN")
    request = {"kpi_code": "KPI-SUP-001", "date_from": "2026-01-01", "date_to": "2026-12-31"}
    synchronous = staff.post("/api/v1/reports/export", json=request)
    assert synchronous.status_code == 200
    rows = list(csv.DictReader(io.StringIO(synchronous.text)))
    assert rows[0]["participant"] == "'=1+ 1"
    queued = staff.post("/api/v1/reports/export-jobs", json=request)
    assert queued.status_code == 202
    job = db.get(ReportExportJob, queued.json()["id"])
    monkeypatch.setattr(worker, "get_session_factory", lambda: lambda: nullcontext(db))
    try:
        assert worker.run_once()
        assert job.status == "SUCCEEDED"
        prepared = staff.get(f"/api/v1/reports/export-jobs/{job.id}/download")
        assert prepared.status_code == 200
        assert list(csv.DictReader(io.StringIO(prepared.text))) == rows
        assert public.get(f"/api/v1/reports/export-jobs/{job.id}/download").status_code == 401
    finally:
        if job.storage_key:
            assert job.storage_key.startswith(f"reports/exports/{job.requested_by}/")
            get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=job.storage_key)


def test_possible_duplicate_requires_review_without_disclosing_person(db):
    client = TestClient(app, headers=ORIGIN)
    assert submit(client, payload()).status_code == 202
    second = payload()
    second["basic"]["first_name"] = "Another"
    response = submit(client, second)
    assert response.status_code == 202
    assert response.json()["status"] == "RECEIVED"
    assert db.scalar(select(func.count()).select_from(Participant)) == 1
    row = db.scalar(
        select(PublicIntake).where(PublicIntake.submission_id == second["submission_id"])
    )
    assert row.status == "NEEDS_REVIEW" and row.participant_id is None
    assert "Another" not in row.payload_ciphertext
    assert "duplicate" not in response.text.lower()


def test_public_validation_rejects_staff_fields_and_invalid_notice(db):
    client = TestClient(app, headers=ORIGIN)
    data = payload()
    data["basic"]["assigned_user_id"] = str(uuid4())
    assert submit(client, data).status_code == 422
    data = payload()
    data["consent"]["notice_version"] = "OUTDATED"
    assert submit(client, data).status_code == 422
    data = payload()
    data["employment"] = {"skills": [{"skill_name": "Excel", "verified": True}]}
    assert submit(client, data).status_code == 422
    assert db.scalar(select(func.count()).select_from(Participant)) == 0


def test_origin_rate_and_abuse_controls(db, monkeypatch):
    assert submit(TestClient(app), payload()).status_code == 403
    client = TestClient(app, headers=ORIGIN)
    data = payload()
    data["website"] = "bot-content"
    assert submit(client, data).status_code == 422
    monkeypatch.setattr(settings, "public_intake_limit", 1)
    assert submit(client, payload()).status_code == 429
    assert db.scalar(select(func.count()).select_from(Participant)) == 0


def test_private_cv_queues_parser_without_authoritative_profile_update(db, monkeypatch):
    monkeypatch.setattr(files, "scan", lambda content: "AVAILABLE")
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(target)
    client = TestClient(app, headers=ORIGIN)
    data = payload()
    response = submit(
        client, data, files={"cv": ("synthetic.pdf", target.getvalue(), "application/pdf")}
    )
    assert response.status_code == 202, response.text
    document = db.scalar(select(Document))
    staged = db.scalar(select(IntakeDocument))
    assert staged.linked_document_id == document.id
    assert files.verified_bytes(document) == target.getvalue()
    job = db.scalar(select(ParserJob))
    assert job and job.status == "QUEUED" and job.created_by is None
    assert "storage_key" not in response.text
    assert (
        submit(
            client, data, files={"cv": ("synthetic.pdf", target.getvalue(), "application/pdf")}
        ).json()
        == response.json()
    )
    assert db.scalar(select(func.count()).select_from(Document)) == 1


def test_invalid_upload_rolls_back_submission(db):
    client = TestClient(app, headers=ORIGIN)
    response = submit(
        client, payload(), files={"cv": ("synthetic.pdf", b"bad file", "application/pdf")}
    )
    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(PublicIntake)) == 0
    assert db.scalar(select(func.count()).select_from(Participant)) == 0


def test_intake_operations_are_staff_only_and_duplicate_link_preserves_profile(db):
    public = TestClient(app, headers=ORIGIN)
    first = submit(public, payload())
    participant = db.scalar(select(Participant))
    duplicate = payload()
    duplicate["basic"]["first_name"] = "Different name awaiting review"
    response = submit(public, duplicate)
    receipt_id = response.json()["receipt_id"]
    assert public.get("/api/v1/intake-operations").status_code == 401
    staff = staff_login(db, "ADMIN")
    evidence = staff.get(f"/api/v1/intake-operations/{receipt_id}")
    assert evidence.status_code == 200
    assert evidence.json()["payload"]["basic"]["first_name"] == duplicate["basic"]["first_name"]
    resolved = staff.post(
        f"/api/v1/intake-operations/{receipt_id}/resolve",
        json={
            "existing_participant_id": str(participant.id),
            "reason": "Human reviewed duplicate; preserve existing profile",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert staff.get(f"/api/v1/participants/{participant.id}").json()["first_name"] == "Synthetic"
    assert db.scalar(select(func.count()).select_from(Participant)) == 1
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_code == "intake.evidence_viewed"))
    assert first.status_code == 202


def test_required_policy_fields_and_request_size_are_enforced(db, monkeypatch):
    monkeypatch.setattr(settings, "supply_required_fields", ["date_of_birth"])
    public = TestClient(app, headers=ORIGIN)
    response = submit(public, payload())
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"
    )
    assert db.scalar(select(func.count()).select_from(Participant)) == 0
    monkeypatch.setattr(settings, "file_max_bytes", 1024)
    response = public.post(
        "/api/v1/participant-intake",
        content=b"x" * 263169,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 413
    assert "x" * 30 not in response.text


def synthetic_pdf():
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(target)
    return target.getvalue()


def test_pending_intake_scan_cannot_parse_until_authorized_security_retry(db, monkeypatch):
    monkeypatch.setattr(files, "scan", lambda content: "SCANNING")
    public = TestClient(app, headers=ORIGIN)
    response = submit(
        public, payload(), files={"cv": ("synthetic.pdf", synthetic_pdf(), "application/pdf")}
    )
    assert response.status_code == 202
    staged = db.scalar(select(IntakeDocument))
    assert db.scalar(select(func.count()).select_from(ParserJob)) == 0
    path = f"/api/v1/intake-operations/{staged.intake_id}/documents/{staged.id}/rescan"
    assert public.post(path).status_code == 401
    monkeypatch.setattr(files, "scan", lambda content: "AVAILABLE")
    staff = staff_login(db, "ADMIN")
    assert staff.post(path).status_code == 200
    assert db.scalar(select(Document)).scan_status == "AVAILABLE"
    assert db.scalar(select(ParserJob)).status == "QUEUED"


def test_parser_worker_recovers_outage_restart_and_exhausted_final_lease(db, monkeypatch):
    from contextlib import nullcontext
    from datetime import UTC, datetime

    from app.integrations.cv_parser import ParserOutput, ParserSuggestion, UnavailableCvParser
    from app.modules.cv_parser import worker
    from app.modules.cv_parser.models import ParserResult
    from app.modules.supply.models import Person

    monkeypatch.setattr(files, "scan", lambda content: "AVAILABLE")
    public = TestClient(app, headers=ORIGIN)
    assert (
        submit(
            public, payload(), files={"cv": ("synthetic.pdf", synthetic_pdf(), "application/pdf")}
        ).status_code
        == 202
    )
    monkeypatch.setattr(worker, "get_session_factory", lambda: lambda: nullcontext(db))
    monkeypatch.setattr(worker, "get_cv_parser", lambda: UnavailableCvParser())
    assert worker.run_once()
    job = db.scalar(select(ParserJob))
    assert job.status == "QUEUED" and job.attempt_count == 1
    assert job.next_attempt_at and not job.lease_owner

    class RestoredParser:
        def parse(self, content, mime_type, filename):
            assert content.startswith(b"%PDF")
            return ParserOutput(
                provider="SYNTHETIC_RECOVERY",
                suggestions=(ParserSuggestion("email", "suggested@example.org"),),
            )

    # An expired lease models a worker that died after claiming this job.
    job.status = "RUNNING"
    job.lease_owner = "synthetic-dead-worker"
    job.lease_expires_at = datetime(2026, 1, 1, tzinfo=UTC)
    job.next_attempt_at = None
    db.commit()
    monkeypatch.setattr(worker, "get_cv_parser", lambda: RestoredParser())
    assert worker.run_once()
    db.refresh(job)
    assert job.status == "SUCCEEDED" and job.attempt_count == 2
    assert db.scalar(select(ParserResult)).review_status == "PENDING_REVIEW"
    assert db.scalar(select(Person)).email is None
    assert worker.run_once() is False

    staff = staff_login(db, "ADMIN")
    retry = staff.post(f"/api/v1/cv/{job.document_id}/parse")
    assert retry.status_code == 201
    exhausted = db.get(ParserJob, retry.json()["id"])
    exhausted.status = "RUNNING"
    exhausted.attempt_count = settings.cv_parser_max_attempts
    exhausted.lease_owner = "synthetic-final-worker"
    exhausted.lease_expires_at = datetime(2026, 1, 1, tzinfo=UTC)
    db.commit()
    assert worker.run_once()
    assert exhausted.status == "FAILED" and exhausted.error_code == "RETRY_LIMIT_EXCEEDED"
    assert exhausted.attempt_count == settings.cv_parser_max_attempts
    assert worker.run_once() is False


def employer_payload():
    return {
        "submission_id": str(uuid4()),
        "company_name": "Synthetic Public Employer",
        "region": "GREATER_ACCRA",
        "district": "TEMA",
        "industry": "LOGISTICS",
        "city": "Tema",
        "address": "Synthetic test location",
        "contact_name": "Synthetic Contact",
        "contact_phone": "0241234567",
        "contact_email": "synthetic-employer@example.org",
        "partnership_type": "COMBINED",
        "consent_agreement": True,
        "consent_contact": True,
        "vacancies": [
            {
                "jobTitle": "Warehouse Assistant",
                "location": "Tema",
                "employmentType": "FULL_TIME",
                "openings": 3,
                "salary_min": "1500.00",
                "salary_max": "2000.00",
                "salary_frequency": "MONTHLY",
                "work_days": "Monday to Friday",
                "work_hours": "08:00–17:00",
                "accommodation": True,
                "benefits": ["Transport"],
                "requirements": [
                    {
                        "criterion_type": "SKILL",
                        "criterion_key": "EXCEL",
                        "operator": "EQ",
                        "value_json": "Excel",
                        "display_order": 1,
                    }
                ],
            }
        ],
    }


def staff_login(db, code="DEMAND"):
    from app.modules.iam.models import Role
    from app.modules.iam.security import hasher

    role = db.scalar(select(Role).where(Role.code == code))
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic Staff",
        password_hash=hasher.hash("Synthetic staff password 123"),
        roles=[role],
        primary_role_id=role.id,
    )
    db.add(user)
    db.commit()
    client = TestClient(app, headers=ORIGIN)
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "Synthetic staff password 123"}
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = client.cookies.get("happy_csrf")
    return client


def test_employer_intake_is_reviewed_and_maps_central_draft_vacancy(db, monkeypatch):
    from app.integrations.employer_portal.models import EmployerSubmission
    from app.modules.demand.models import (
        Contact,
        Organization,
        Partnership,
        PartnershipDocument,
        Requirement,
        Vacancy,
    )

    monkeypatch.setattr(files, "scan", lambda content: "AVAILABLE")
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(target)
    data = employer_payload()
    data["documents"] = [{"kind": "MOU"}]
    client = TestClient(app, headers=ORIGIN)
    response = client.post(
        "/api/v1/employer-intake",
        data={"payload": json.dumps(data)},
        files=[("files", ("synthetic.pdf", target.getvalue(), "application/pdf"))],
    )
    assert response.status_code == 202, response.text
    assert db.scalar(select(func.count()).select_from(Organization)) == 0
    row = db.scalar(select(EmployerSubmission))
    staff = staff_login(db)
    detail = staff.get(f"/api/v1/integrations/employer-portal/submissions/{row.id}").json()
    private_document = detail["documents"][0]
    download_path = (
        f"/api/v1/integrations/employer-portal/submissions/{row.id}"
        f"/documents/{private_document['id']}/download"
    )
    assert client.get(download_path).status_code == 401
    downloaded = staff.get(download_path)
    assert downloaded.status_code == 200 and downloaded.content == target.getvalue()
    assert downloaded.headers["cache-control"] == "no-store"
    converted = staff.post(
        f"/api/v1/integrations/employer-portal/submissions/{row.id}/convert",
        json={"version": row.version, "reason": "Synthetic staff review", "mou_required": True},
    )
    assert converted.status_code == 200, converted.text
    vacancy = db.scalar(select(Vacancy))
    assert vacancy.status == "DRAFT" and vacancy.required_headcount == 3
    assert str(vacancy.salary_min) == "1500.00" and vacancy.work_days_text == "Monday to Friday"
    assert vacancy.benefits == ["Transport"] and vacancy.accommodation_available
    assert db.scalar(select(Organization)).district_code == "TEMA"
    assert db.scalar(select(Partnership)).partnership_type == "COMBINED"
    assert db.scalar(select(Contact)).email == data["contact_email"]
    assert db.scalar(select(Requirement).where(Requirement.criterion_key == "EXCEL"))
    assert db.scalar(select(PartnershipDocument)).storage_key.startswith("intakes/")
    assert db.scalar(select(IntakeDocument)).linked_document_id is not None


def test_employer_duplicates_by_contact_require_explicit_existing_selection(db):
    from app.integrations.employer_portal.models import EmployerSubmission
    from app.modules.demand.models import Organization

    client = TestClient(app, headers=ORIGIN)
    staff = staff_login(db)
    first = employer_payload()
    assert (
        client.post("/api/v1/employer-intake", data={"payload": json.dumps(first)}).status_code
        == 202
    )
    row = db.scalar(select(EmployerSubmission))
    path = f"/api/v1/integrations/employer-portal/submissions/{row.id}/convert"
    assert (
        staff.post(path, json={"version": row.version, "reason": "Synthetic review"}).status_code
        == 200
    )
    organization = db.scalar(select(Organization))
    second = employer_payload()
    second["company_name"] = "Synthetic Alternate Spelling"
    assert (
        client.post("/api/v1/employer-intake", data={"payload": json.dumps(second)}).status_code
        == 202
    )
    other = db.scalar(
        select(EmployerSubmission).where(
            EmployerSubmission.external_submission_id == second["submission_id"]
        )
    )
    path = f"/api/v1/integrations/employer-portal/submissions/{other.id}/convert"
    assert (
        staff.post(path, json={"version": other.version, "reason": "Synthetic review"}).status_code
        == 409
    )
    assert (
        staff.post(
            path,
            json={
                "version": other.version,
                "existing_organization_id": str(organization.id),
                "reason": "Reviewed contact match",
            },
        ).status_code
        == 200
    )
    assert db.scalar(select(func.count()).select_from(Organization)) == 1


def test_integrated_golden_workflow_uses_public_intakes_and_real_parser(db, monkeypatch):
    import socket
    import subprocess
    import sys
    import time
    from pathlib import Path
    from urllib.request import urlopen

    from app.core.process import creation_flags
    from app.integrations.cv_parser.adapter import HttpCvParser
    from app.integrations.employer_portal.models import EmployerSubmission
    from app.modules.cv_parser import service as parsing
    from app.modules.cv_parser.models import ParserResult
    from app.modules.demand.models import Vacancy
    from app.modules.supply.models import Person

    monkeypatch.setattr(files, "scan", lambda content: "AVAILABLE")
    staff = staff_login(db, "ADMIN")
    public = TestClient(app, headers=ORIGIN)

    def post(path, body):
        response = staff.post("/api/v1" + path, json=body)
        assert response.status_code in {200, 201}, response.text
        return response.json()

    assert (
        public.post(
            "/api/v1/employer-intake", data={"payload": json.dumps(employer_payload())}
        ).status_code
        == 202
    )
    inbox = db.scalar(select(EmployerSubmission))
    post(
        f"/integrations/employer-portal/submissions/{inbox.id}/convert",
        {"version": inbox.version, "reason": "Synthetic Demand review"},
    )
    vacancy = db.scalar(select(Vacancy))
    for target in ("PENDING_CONFIRMATION", "ACTIVE"):
        post(
            f"/vacancies/{vacancy.id}/transition",
            {"version": vacancy.version, "to_status": target, "reason": "Reviewed opportunity"},
        )

    # Generate a real text PDF in memory using the existing PDF dependency.
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 72 720 Td (Synthetic Intake) Tj "
        b"0 -18 Td (parsed-synthetic@example.org) Tj "
        b"0 -18 Td (Skills: Excel and customer service) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    target = io.BytesIO()
    writer.write(target)
    submitted = submit(
        public, payload(), files={"cv": ("synthetic.pdf", target.getvalue(), "application/pdf")}
    )
    assert submitted.status_code == 202, submitted.text
    participant = db.scalar(select(Participant))
    person = db.get(Person, participant.person_id)
    assert person.email is None
    job = db.scalar(select(ParserJob))
    document = db.scalar(select(Document))

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    parser_root = Path(__file__).resolve().parents[4] / "CV-Parser-main/cv_system_output"
    parser_token = "synthetic-golden-parser-token-with-over-32-characters"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "happy_service:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=parser_root,
        env={**os.environ, "HAPPY_PARSER_TOKEN": parser_token},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags(),
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=1):
                    break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("Synthetic real parser service did not start.")
                time.sleep(0.1)
        monkeypatch.setattr(
            settings, "cv_parser_url", f"http://127.0.0.1:{port}/api/v1/integrations/happy/parse"
        )
        monkeypatch.setattr(settings, "cv_parser_token", SecretStr(parser_token))
        parsing.process_job(db, job, document, participant, HttpCvParser())
        assert job.status == "SUCCEEDED", job.error_code
    finally:
        process.terminate()
        process.wait(timeout=10)
    assert person.email is None  # Suggestions have no authority before staff review.
    result = db.scalar(select(ParserResult))
    decisions = [
        {"field": item["field"], "decision": "APPROVE" if item["field"] == "email" else "REJECT"}
        for item in result.suggestions_json
    ]
    post(
        f"/cv-parser/results/{result.id}/review",
        {"participant_version": participant.version, "decisions": decisions},
    )
    assert person.email == "parsed-synthetic@example.org"
    post(f"/cv/{document.id}/approve", {"version": participant.version})
    post(
        f"/participants/{participant.id}/readiness",
        {
            "version": participant.version,
            "readiness_status": "JOB_READY",
            "availability_status": "AVAILABLE",
            "reason": "Supply review complete",
        },
    )
    candidate = post(
        "/candidate-vacancies",
        {"participant_id": str(participant.id), "vacancy_id": str(vacancy.id)},
    )
    for state in ("RECRUITER_REVIEW", "PRE_SCREEN"):
        candidate = post(
            f"/candidate-vacancies/{candidate['id']}/transition",
            {
                "version": candidate["version"],
                "to_status": state,
                "reason": "Synthetic human review",
            },
        )
    candidate = post(
        f"/candidate-vacancies/{candidate['id']}/pre-screen",
        {
            "version": candidate["version"],
            "result": "QUALIFIED",
            "participant_interested": True,
            "availability_confirmed": True,
            "salary_accepted": True,
            "location_accepted": True,
        },
    )
    candidate = post(
        f"/candidate-vacancies/{candidate['id']}/submit", {"version": candidate["version"]}
    )
    interview = post(
        "/interviews",
        {
            "candidate_vacancy_id": candidate["id"],
            "candidate_version": candidate["version"],
            "scheduled_at": "2026-10-12T10:00:00Z",
            "format": "IN_PERSON",
            "location_or_link": "Synthetic office",
        },
    )
    interview = post(
        f"/interviews/{interview['id']}/attend",
        {"version": interview["version"], "reason": "Attended"},
    )
    post(
        f"/interviews/{interview['id']}/outcome",
        {"version": interview["version"], "outcome": "PASSED", "reason": "Reviewed outcome"},
    )
    candidate = staff.get(f"/api/v1/candidate-vacancies/{candidate['id']}").json()
    candidate = post(
        f"/candidate-vacancies/{candidate['id']}/employer-decision",
        {"version": candidate["version"], "decision": "SELECTED", "reason": "Employer selected"},
    )
    placement = post(
        "/placements",
        {
            "candidate_vacancy_id": candidate["id"],
            "candidate_version": candidate["version"],
            "expected_start_date": "2026-10-10",
            "salary_amount": "1800.00",
            "salary_frequency": "MONTHLY",
            "payroll_frequency": "MONTHLY",
            "payday_rule_json": {"day": 25, "cutoff_day": 15},
        },
    )
    assert placement["status"] != "CONFIRMED"
    placement = post(
        f"/placements/{placement['id']}/confirm-start",
        {
            "version": placement["version"],
            "actual_start_date": "2026-10-10",
            "notes": "Actual start verified",
        },
    )
    assert placement["status"] == "AWAITING_FIRST_INCOME" and not placement["confirmed_at"]
    placement = post(
        f"/placements/{placement['id']}/first-income/confirm",
        {
            "version": placement["first_income"]["version"],
            "actual_income_received_date": "2026-10-18",
            "amount_received": "1800.00",
            "notes": "Synthetic first monthly income verified",
        },
    )
    assert placement["status"] == "CONFIRMED"
    counts = staff.get(f"/api/v1/vacancies/{vacancy.id}/headcount").json()
    assert counts == {"required": 3, "started": 1, "confirmed_placements": 1, "outstanding": 2}
    follow = post(
        "/follow-ups",
        {
            "placement_id": placement["id"],
            "follow_up_type": "EMPLOYMENT_VERIFICATION",
            "scheduled_for": "2026-10-19",
        },
    )
    post(
        f"/follow-ups/{follow['id']}/complete",
        {
            "version": follow["version"],
            "contact_result": "REACHED",
            "notes": "Synthetic participant reached",
        },
    )
    post(
        "/outcomes",
        {
            "placement_id": placement["id"],
            "follow_up_id": follow["id"],
            "as_of_date": "2026-10-19",
            "currently_working": True,
        },
    )
    report = staff.get("/api/v1/reports/kpis?date_from=2026-01-01&date_to=2026-12-31")
    assert report.status_code == 200
    metrics = {item["code"]: item for item in report.json()["items"]}
    assert metrics["KPI-PLC-001"]["value"] == "1"
    events = {item.event_code for item in db.scalars(select(AuditEvent))}
    assert {
        "participant_intake.submitted",
        "employer_intake.submitted",
        "cv_parser.succeeded",
        "placement.first_income_confirmed",
        "outcome.created",
    } <= events

import os
from contextlib import nullcontext
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Organization, Vacancy
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher
from app.modules.matching.models import CandidateHistory, CandidateVacancy, EmployerDecision
from app.modules.merl.models import DataQualityIssue, Outcome
from app.modules.placement.models import Placement
from app.modules.reporting import worker as reporting_worker
from app.modules.reporting.models import ReportExportJob
from app.modules.supply.models import Participant, Person
from app.storage.s3 import get_storage_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic Reporting password 123"
ORIGIN = {"Origin": "http://localhost:3000"}
PERIOD = "date_from=2026-10-01&date_to=2026-10-31"


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
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()


def login(db: Session, code: str) -> tuple[TestClient, User]:
    role = db.scalar(select(Role).where(Role.code == code))
    assert role
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic " + code,
        password_hash=hasher.hash(PASSWORD),
        roles=[role],
        primary_role_id=role.id,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200
    client.headers.update({**ORIGIN, "X-CSRF-Token": client.cookies.get("happy_csrf")})
    return client, user


def reporting_records(db: Session, user: User) -> None:
    person = Person(
        first_name="Akua",
        surname="Reporting Fixture",
        normalized_name="akua reporting fixture",
        phone_raw="0240000000",
        phone_normalized="+233240000000",
        community="Accra",
        created_at=datetime(2026, 10, 2, tzinfo=UTC),
        created_by=user.id,
    )
    db.add(person)
    db.flush()
    participant = Participant(
        participant_code="HAPPY-REPORTING",
        person_id=person.id,
        onboarding_status="COMPLETE",
        readiness_status="JOB_READY",
        availability_status="AVAILABLE",
        completed_at=datetime(2026, 10, 5, tzinfo=UTC),
        created_at=datetime(2026, 10, 2, tzinfo=UTC),
        created_by=user.id,
    )
    organization = Organization(
        organization_code="ORG-REPORTING",
        name="Reporting Employer",
        normalized_name="reporting employer",
        organization_type="EMPLOYER",
        created_by=user.id,
    )
    db.add_all([participant, organization])
    db.flush()
    for index in range(2):
        vacancy = Vacancy(
            vacancy_code=f"VAC-REPORTING-{index}",
            organization_id=organization.id,
            title=f"Reporting role {index}",
            status="ACTIVE",
            required_headcount=3,
            created_by=user.id,
        )
        db.add(vacancy)
        db.flush()
        candidate = CandidateVacancy(
            participant_id=participant.id,
            vacancy_id=vacancy.id,
            status="CONFIRMED_PLACEMENT" if index == 0 else "STARTED",
            source="STAFF",
            priority="NORMAL",
            submitted_at=datetime(2026, 10, 4, tzinfo=UTC),
            selected_at=datetime(2026, 10, 8, tzinfo=UTC),
            created_by=user.id,
        )
        db.add(candidate)
        db.flush()
        for stage, day in (
            ("QUALIFIED", 3),
            ("SUBMITTED", 4),
            *(([("INTERVIEW", 6)]) if index == 0 else []),
            ("SELECTED", 8),
        ):
            db.add(
                CandidateHistory(
                    candidate_vacancy_id=candidate.id,
                    from_status=None,
                    to_status=stage,
                    actor_type="USER",
                    actor_id=str(user.id),
                    occurred_at=datetime(2026, 10, day, tzinfo=UTC),
                )
            )
        db.add(
            EmployerDecision(
                candidate_vacancy_id=candidate.id,
                decision="SELECTED",
                reason="Synthetic decision",
                created_at=datetime(2026, 10, 8 + index, tzinfo=UTC),
                created_by=user.id,
            )
        )
        placement = Placement(
            placement_code=f"PLC-REPORTING-{index}",
            participant_id=participant.id,
            candidate_vacancy_id=candidate.id,
            organization_id=organization.id,
            vacancy_id=vacancy.id,
            status="CONFIRMED" if index == 0 else "STARTED",
            actual_start_date=date(2026, 10, 10 + index),
            confirmed_at=datetime(2026, 10, 20, tzinfo=UTC) if index == 0 else None,
            currently_working=True,
            created_by=user.id,
        )
        db.add(placement)
        db.flush()
        db.add(
            Outcome(
                participant_id=participant.id,
                placement_id=placement.id,
                as_of_date=date(2026, 10, 22),
                currently_working=index == 1,
                current_role=vacancy.title,
                verified_by=user.id,
                created_by=user.id,
            )
        )
    db.add(
        DataQualityIssue(
            issue_code="DQI-REPORTING",
            entity_type="PARTICIPANT",
            entity_id=participant.id,
            issue_type="DUPLICATE_SUSPECT",
            severity="HIGH",
            status="OPEN",
            description="Synthetic duplicate review.",
            created_by=user.id,
        )
    )
    db.commit()


def by_code(response) -> dict[str, dict]:
    return {row["code"]: row for row in response.json()["items"]}


def test_kpi_dictionary_formulas_and_drilldowns(db: Session) -> None:
    client, user = login(db, "MANAGEMENT")
    reporting_records(db, user)
    response = client.get("/api/v1/reports/kpis?" + PERIOD)
    assert response.status_code == 200, response.text
    metrics = by_code(response)
    assert metrics["KPI-PLC-001"]["value"] == "1"
    assert metrics["KPI-PLC-002"]["value"] == "1"
    assert metrics["KPI-VAC-001"]["value"] == "6"
    assert metrics["KPI-VAC-002"]["value"] == "2"
    assert metrics["KPI-VAC-003"]["value"] == "4"
    assert metrics["KPI-MATCH-001"]["numerator"] == 2
    assert metrics["KPI-MATCH-001"]["denominator"] == 2
    assert metrics["KPI-MATCH-002"]["value"] == "50.0"
    assert metrics["KPI-MATCH-004"]["value"] == "50.0"
    assert metrics["KPI-SUP-001"]["value"] == "100.0"
    assert metrics["KPI-MERL-001"]["value"] == "1"
    drill = client.get("/api/v1/reports/kpis/KPI-PLC-001/drilldown?" + PERIOD)
    assert drill.status_code == 200 and len(drill.json()["items"]) == 1
    assert drill.json()["items"][0]["participant"] == "Akua Reporting Fixture"


def test_targets_gap_forecast_and_export_permissions(db: Session) -> None:
    admin, _ = login(db, "ADMIN")
    target = admin.post(
        "/api/v1/reports/targets",
        json={
            "kpi_code": "KPI-PLC-001",
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "target_value": "2",
            "forecast_value": "1.5",
            "notes": "Synthetic configured target.",
        },
    )
    assert target.status_code == 201, target.text
    management, _ = login(db, "MANAGEMENT")
    metrics = by_code(management.get("/api/v1/reports/kpis?" + PERIOD))
    assert metrics["KPI-PLC-001"]["target"] == "2.00"
    assert metrics["KPI-PLC-001"]["gap"] == "2.00"
    assert metrics["KPI-PLC-001"]["forecast"] == "1.50"
    assert management.post("/api/v1/reports/targets", json={}).status_code == 403
    exported = management.post(
        "/api/v1/reports/export",
        json={"kpi_code": "KPI-PLC-001", "date_from": "2026-10-01", "date_to": "2026-10-31"},
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "confirmed_at" in exported.text
    denied = management.post(
        "/api/v1/reports/export",
        json={
            "kpi_code": "KPI-PLC-001",
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "include_sensitive": True,
            "privacy_acknowledged": True,
        },
    )
    assert denied.status_code == 403
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "report.exported"))


def test_persisted_export_job_is_private_audited_and_downloadable(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user = login(db, "MANAGEMENT")
    reporting_records(db, user)
    monkeypatch.setattr(
        reporting_worker,
        "get_session_factory",
        lambda: lambda: nullcontext(db),
    )
    response = client.post(
        "/api/v1/reports/export-jobs",
        json={"kpi_code": "KPI-PLC-001", "date_from": "2026-10-01", "date_to": "2026-10-31"},
    )
    assert response.status_code == 202, response.text
    identifier = response.json()["id"]
    assert response.json()["status"] == "PENDING"
    assert reporting_worker.run_once() is True
    job = client.get(f"/api/v1/reports/export-jobs/{identifier}")
    assert job.status_code == 200
    assert job.json()["status"] == "SUCCEEDED"
    assert job.json()["row_count"] == 1
    downloaded = client.get(f"/api/v1/reports/export-jobs/{identifier}/download")
    assert downloaded.status_code == 200
    assert "confirmed_at" in downloaded.text
    other, _ = login(db, "MANAGEMENT")
    assert other.get(f"/api/v1/reports/export-jobs/{identifier}").status_code == 404
    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == identifier)))
    assert {
        "report.export_requested",
        "report.export_completed",
        "report.export_downloaded",
    } <= actions
    row = db.get(ReportExportJob, identifier)
    assert row and row.storage_key
    get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=row.storage_key)


def test_export_worker_retries_failures_and_recovers_expired_leases(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user = login(db, "MANAGEMENT")
    reporting_records(db, user)
    monkeypatch.setattr(
        reporting_worker,
        "get_session_factory",
        lambda: lambda: nullcontext(db),
    )
    response = client.post(
        "/api/v1/reports/export-jobs",
        json={"kpi_code": "KPI-PLC-001", "date_from": "2026-10-01", "date_to": "2026-10-31"},
    )
    assert response.status_code == 202
    row = db.get(ReportExportJob, response.json()["id"])
    assert row
    row.status = "RUNNING"
    row.lease_owner = "dead-worker"
    row.lease_expires_at = datetime(2026, 1, 1, tzinfo=UTC)
    db.commit()

    def unavailable_storage():
        raise RuntimeError("Synthetic storage outage")

    monkeypatch.setattr(reporting_worker, "get_storage_client", unavailable_storage)
    assert reporting_worker.run_once() is True
    db.refresh(row)
    assert row.status == "PENDING"
    assert row.attempt_count == 1
    assert row.next_attempt_at is not None
    assert row.lease_owner is None

    row.next_attempt_at = datetime(2026, 1, 1, tzinfo=UTC)
    row.attempt_count = settings.background_job_max_attempts - 1
    db.commit()
    assert reporting_worker.run_once() is True
    db.refresh(row)
    assert row.status == "FAILED"
    assert row.attempt_count == settings.background_job_max_attempts
    assert db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "report.export_failed", AuditEvent.entity_id == row.id
        )
    )


def test_unapproved_kpis_are_explicitly_unavailable(db: Session) -> None:
    client, _ = login(db, "MANAGEMENT")
    metrics = by_code(client.get("/api/v1/reports/kpis?" + PERIOD))
    for code in ("KPI-MERL-002", "KPI-DQ-001", "KPI-MKT-003"):
        assert metrics[code]["available"] is False
        assert metrics[code]["value"] is None
        response = client.get(f"/api/v1/reports/kpis/{code}/drilldown?{PERIOD}")
        assert response.status_code == 422


def test_reporting_is_server_authorized_and_period_is_bounded(db: Session) -> None:
    marketing, _ = login(db, "MARKETING")
    assert marketing.get("/api/v1/reports/kpis?" + PERIOD).status_code == 403
    management, _ = login(db, "MANAGEMENT")
    assert (
        management.get("/api/v1/reports/kpis?date_from=2026-11-01&date_to=2026-10-01").status_code
        == 422
    )
    assert management.get("/api/v1/reports/dashboard?" + PERIOD).status_code == 200

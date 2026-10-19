import os
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Organization, Vacancy
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, Role, User
from app.modules.iam.security import hasher
from app.modules.matching.models import CandidateVacancy
from app.modules.merl.models import (
    DataQualityIssue,
    FollowUpTemplate,
    Outcome,
    OutcomeRevision,
)
from app.modules.placement.models import EmploymentStatusHistory, Placement
from app.modules.supply.models import Participant, Person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic MERL password 123"
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


def login(db: Session, code: str = "MERL") -> tuple[TestClient, User]:
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


def placement(db: Session, user: User, *, started: bool = True, ended: bool = False) -> Placement:
    token = uuid4().hex[:10]
    person = Person(
        first_name="Synthetic",
        surname="MERL Candidate",
        normalized_name="synthetic merl candidate " + token,
        phone_raw="0241234567",
        phone_normalized="+233241234567",
        community="Accra",
        created_by=user.id,
    )
    db.add(person)
    db.flush()
    participant = Participant(
        participant_code="HAPPY-" + token.upper(),
        person_id=person.id,
        onboarding_status="COMPLETE",
        created_by=user.id,
    )
    organization = Organization(
        organization_code="ORG-" + token.upper(),
        name="Synthetic MERL Employer",
        normalized_name="synthetic merl employer " + token,
        organization_type="EMPLOYER",
        created_by=user.id,
    )
    db.add_all([participant, organization])
    db.flush()
    vacancy = Vacancy(
        vacancy_code="VAC-" + token.upper(),
        organization_id=organization.id,
        title="Synthetic role",
        status="ACTIVE",
        required_headcount=2,
        created_by=user.id,
    )
    db.add(vacancy)
    db.flush()
    candidate = CandidateVacancy(
        participant_id=participant.id,
        vacancy_id=vacancy.id,
        status="CONFIRMED_PLACEMENT" if started else "SELECTED",
        source="STAFF",
        priority="NORMAL",
        submitted_at=datetime(2026, 9, 28, tzinfo=UTC),
        selected_at=datetime(2026, 9, 30, tzinfo=UTC),
        created_by=user.id,
    )
    db.add(candidate)
    db.flush()
    row = Placement(
        placement_code="PLC-" + token.upper(),
        participant_id=participant.id,
        candidate_vacancy_id=candidate.id,
        organization_id=organization.id,
        vacancy_id=vacancy.id,
        status="ENDED" if ended else "CONFIRMED" if started else "START_PENDING",
        actual_start_date=date(2026, 10, 1) if started else None,
        confirmed_at=datetime(2026, 10, 5, tzinfo=UTC) if started else None,
        employment_end_date=date(2026, 10, 8) if ended else None,
        employment_end_reason="Contract completed" if ended else None,
        currently_working=False if ended else True if started else None,
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    return row


def test_manual_and_template_follow_up_scheduling_without_seeded_cadence(db: Session) -> None:
    client, user = login(db)
    row = placement(db, user)
    today = datetime.now(UTC).date().isoformat()
    assert db.scalar(select(func.count()).select_from(FollowUpTemplate)) == 0
    manual = client.post(
        "/api/v1/follow-ups",
        json={
            "placement_id": str(row.id),
            "follow_up_type": "RETENTION_CHECK",
            "scheduled_for": today,
            "owner_id": str(user.id),
        },
    )
    assert manual.status_code == 201, manual.text
    assert manual.json()["participant_id"] == str(row.participant_id)
    assert manual.json()["status"] == "DUE"
    pending = placement(db, user, started=False)
    rejected = client.post(
        "/api/v1/follow-ups",
        json={
            "placement_id": str(pending.id),
            "follow_up_type": "RETENTION_CHECK",
            "scheduled_for": today,
        },
    )
    assert rejected.status_code == 409

    admin, _ = login(db, "ADMIN")
    template = admin.post(
        "/api/v1/follow-up-templates",
        json={
            "template_code": "SYNTHETIC_30_DAY",
            "name": "Synthetic 30 day check",
            "follow_up_type": "RETENTION_CHECK",
            "anchor": "ACTUAL_START",
            "offset_days": 30,
            "required_questions": ["currently_working"],
            "owner_role_code": "MERL",
        },
    )
    assert template.status_code == 201, template.text
    templated = client.post(
        "/api/v1/follow-ups",
        json={
            "placement_id": str(row.id),
            "template_id": template.json()["id"],
        },
    )
    assert templated.status_code == 201
    assert templated.json()["scheduled_for"] == "2026-10-31"


def test_follow_up_outcomes_are_historical_and_append_employment_evidence(db: Session) -> None:
    client, user = login(db)
    row = placement(db, user)
    follow = client.post(
        "/api/v1/follow-ups",
        json={
            "placement_id": str(row.id),
            "follow_up_type": "EMPLOYMENT_VERIFICATION",
            "scheduled_for": "2026-10-10",
        },
    ).json()
    complete = client.post(
        f"/api/v1/follow-ups/{follow['id']}/complete",
        json={
            "version": follow["version"],
            "contact_result": "REACHED",
            "notes": "Participant reached and interviewed.",
        },
    )
    assert complete.status_code == 200
    outcome = client.post(
        "/api/v1/outcomes",
        json={
            "placement_id": str(row.id),
            "follow_up_id": follow["id"],
            "as_of_date": "2026-10-10",
            "currently_working": True,
            "current_employer": "Synthetic MERL Employer",
            "current_role": "Synthetic role",
            "job_satisfaction": 4,
            "progress_text": "Settling into the role.",
            "impact_story_potential": True,
        },
    )
    assert outcome.status_code == 201, outcome.text
    duplicate = client.post(
        "/api/v1/outcomes",
        json={
            "placement_id": str(row.id),
            "follow_up_id": follow["id"],
            "as_of_date": "2026-10-10",
            "currently_working": True,
        },
    )
    assert duplicate.status_code == 409
    second = client.post(
        "/api/v1/outcomes",
        json={
            "placement_id": str(row.id),
            "as_of_date": "2026-10-11",
            "currently_working": False,
            "support_needed_text": "Job search support.",
        },
    )
    assert second.status_code == 201
    assert (
        db.scalar(select(func.count()).select_from(Outcome).where(Outcome.placement_id == row.id))
        == 2
    )
    history = list(
        db.scalars(
            select(EmploymentStatusHistory).where(EmploymentStatusHistory.placement_id == row.id)
        )
    )
    assert [item.status for item in history] == ["WORKING", "ENDED"]
    dashboard = client.get("/api/v1/merl/dashboard").json()
    assert dashboard["latest_verified_working"] == 0
    assert dashboard["impact_story_candidates"] == 1
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "outcome.created"))


def test_sensitive_income_is_permission_gated_and_conflict_opens_quality_issue(db: Session) -> None:
    client, user = login(db)
    row = placement(db, user, ended=True)
    forbidden = client.post(
        "/api/v1/outcomes",
        json={
            "placement_id": str(row.id),
            "as_of_date": "2026-10-10",
            "currently_working": True,
            "current_income_amount": "2000",
            "income_frequency": "MONTHLY",
        },
    )
    assert forbidden.status_code == 403
    permission = db.scalar(
        select(Permission).where(Permission.code == "participant_sensitive:edit")
    )
    assert permission
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="ALLOW"))
    db.commit()
    db.expire_all()
    allowed = client.post(
        "/api/v1/outcomes",
        json={
            "placement_id": str(row.id),
            "as_of_date": "2026-10-10",
            "currently_working": True,
            "current_income_amount": "2000",
            "income_frequency": "MONTHLY",
        },
    )
    assert allowed.status_code == 201, allowed.text
    issue = db.scalar(
        select(DataQualityIssue).where(DataQualityIssue.entity_id == UUID(allowed.json()["id"]))
    )
    assert issue and issue.issue_type == "EMPLOYMENT_STATE_CONFLICT" and issue.status == "OPEN"
    management, _ = login(db, "MANAGEMENT")
    assert management.get("/api/v1/data-quality/issues").status_code == 200
    assert management.post("/api/v1/data-quality/issues", json={}).status_code == 403


def test_outcome_correction_preserves_append_only_revision(db: Session) -> None:
    client, user = login(db)
    row = placement(db, user)
    created = client.post(
        "/api/v1/outcomes",
        json={"placement_id": str(row.id), "as_of_date": "2026-10-10", "currently_working": True},
    ).json()
    corrected = client.patch(
        f"/api/v1/outcomes/{created['id']}",
        json={
            "version": created["version"],
            "reason": "Participant clarified their status.",
            "as_of_date": "2026-10-10",
            "currently_working": False,
        },
    )
    assert corrected.status_code == 200, corrected.text
    revision = db.scalar(
        select(OutcomeRevision).where(OutcomeRevision.outcome_id == UUID(created["id"]))
    )
    assert revision and revision.previous_json["currently_working"] is True
    with pytest.raises(DBAPIError):
        db.execute(
            text("UPDATE outcome_revisions SET reason='rewritten' WHERE id=:id"),
            {"id": revision.id},
        )
        db.flush()
    db.rollback()

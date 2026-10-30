import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Organization, Vacancy
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, Role, User
from app.modules.iam.security import hasher
from app.modules.matching.models import (
    CandidateHistory,
    CandidateVacancy,
    EmployerDecision,
    InterviewHistory,
    Screening,
)
from app.modules.placement.models import Placement, PlacementHistory
from app.modules.supply.models import Consent, Participant, Person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic matching password 123"
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
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-NOTICE")
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(
        settings, "supply_required_sections", ["basic", "contact", "consent", "review"]
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()


def login(db: Session, code: str = "MATCHING") -> tuple[TestClient, User]:
    role = db.scalar(select(Role).where(Role.code == code))
    assert role
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic " + code.title(),
        password_hash=hasher.hash(PASSWORD),
        roles=[role],
        primary_role_id=role.id,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    client.headers.update({**ORIGIN, "X-CSRF-Token": client.cookies.get("happy_csrf")})
    return client, user


def parents(db: Session, user: User, *, complete: bool = False) -> tuple[Participant, Vacancy]:
    token = uuid4().hex[:10]
    person = Person(
        first_name="Synthetic",
        surname="Candidate",
        normalized_name="synthetic candidate " + token,
        phone_raw="0241234567",
        phone_normalized="+23324" + token[:7],
        community="Accra",
        government_id_type="GHANA_CARD",
        government_id_ciphertext="synthetic-protected-identity-fixture",
        created_by=user.id,
    )
    db.add(person)
    db.flush()
    participant = Participant(
        participant_code="HAPPY-" + token.upper(),
        person_id=person.id,
        onboarding_status="COMPLETE" if complete else "IN_PROGRESS",
        completed_sections=["basic", "contact", "consent", "review"] if complete else ["basic"],
        created_by=user.id,
    )
    organization = Organization(
        organization_code="ORG-" + token.upper(),
        name="Synthetic Employer " + token,
        normalized_name="synthetic employer " + token,
        organization_type="EMPLOYER",
        created_by=user.id,
    )
    db.add_all([participant, organization])
    db.flush()
    vacancy = Vacancy(
        vacancy_code="VAC-" + token.upper(),
        organization_id=organization.id,
        title="Operations Associate",
        status="ACTIVE",
        required_headcount=2,
        created_by=user.id,
    )
    db.add(vacancy)
    if complete:
        db.add(
            Consent(
                participant_id=participant.id,
                consent_type="PROGRAMME",
                status="ACTIVE",
                consented_at=datetime.now(UTC),
                method="STAFF_RECORDED",
                privacy_notice_version="SYNTHETIC-NOTICE",
                created_by=user.id,
            )
        )
    db.commit()
    return participant, vacancy


def create_candidate(
    client: TestClient, participant: Participant, vacancy: Vacancy, owner: User
) -> dict[str, object]:
    response = client.post(
        "/api/v1/candidate-vacancies",
        json={
            "participant_id": str(participant.id),
            "vacancy_id": str(vacancy.id),
            "owner_id": str(owner.id),
            "next_action": "Review profile",
            "next_action_due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def transition(client: TestClient, row: dict[str, object], status: str, reason: str | None = None):
    response = client.post(
        f"/api/v1/candidate-vacancies/{row['id']}/transition",
        json={"version": row["version"], "to_status": status, "reason": reason},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_full_human_matching_workflow_and_submission_gate(db: Session) -> None:
    client, user = login(db)
    incomplete, vacancy = parents(db, user)
    row = create_candidate(client, incomplete, vacancy, user)
    duplicate = client.post(
        "/api/v1/candidate-vacancies",
        json={"participant_id": str(incomplete.id), "vacancy_id": str(vacancy.id)},
    )
    assert duplicate.status_code == 409
    row = transition(client, row, "RECRUITER_REVIEW")
    row = transition(client, row, "PRE_SCREEN")
    screened = client.post(
        f"/api/v1/candidate-vacancies/{row['id']}/pre-screen",
        json={
            "version": row["version"],
            "result": "QUALIFIED",
            "participant_interested": True,
            "availability_confirmed": True,
            "salary_accepted": True,
            "location_accepted": True,
            "notes": "Human screening completed",
        },
    )
    assert screened.status_code == 200
    row = screened.json()
    blocked = client.post(
        f"/api/v1/candidate-vacancies/{row['id']}/submit", json={"version": row["version"]}
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "ONBOARDING_INCOMPLETE"

    incomplete.onboarding_status = "COMPLETE"
    incomplete.completed_sections = ["basic", "contact", "consent", "review"]
    db.add(
        Consent(
            participant_id=incomplete.id,
            consent_type="PROGRAMME",
            status="ACTIVE",
            consented_at=datetime.now(UTC),
            method="STAFF_RECORDED",
            privacy_notice_version="SYNTHETIC-NOTICE",
            created_by=user.id,
        )
    )
    db.commit()
    submitted = client.post(
        f"/api/v1/candidate-vacancies/{row['id']}/submit", json={"version": row["version"]}
    )
    assert submitted.status_code == 200, submitted.text
    row = submitted.json()
    scheduled = client.post(
        "/api/v1/interviews",
        json={
            "candidate_vacancy_id": row["id"],
            "candidate_version": row["version"],
            "scheduled_at": "2026-10-12T10:00:00Z",
            "format": "VIDEO",
            "location_or_link": "https://meet.example.test/interview",
        },
    )
    assert scheduled.status_code == 201, scheduled.text
    interview = scheduled.json()
    attended = client.post(
        f"/api/v1/interviews/{interview['id']}/attend",
        json={"version": interview["version"], "reason": "Candidate attended"},
    )
    assert attended.status_code == 200
    interview = attended.json()
    completed = client.post(
        f"/api/v1/interviews/{interview['id']}/outcome",
        json={"version": interview["version"], "outcome": "PASSED", "reason": "Passed"},
    )
    assert completed.status_code == 200, completed.text
    row = client.get(f"/api/v1/candidate-vacancies/{row['id']}").json()
    assert row["status"] == "EMPLOYER_DECISION"
    selected = client.post(
        f"/api/v1/candidate-vacancies/{row['id']}/employer-decision",
        json={"version": row["version"], "decision": "SELECTED", "reason": "Offer made"},
    )
    assert selected.status_code == 200
    row = selected.json()
    assert row["status"] == "SELECTED" and row["selected_at"]
    placement = client.post(
        f"/api/v1/candidate-vacancies/{row['id']}/transition",
        json={"version": row["version"], "to_status": "STARTED"},
    )
    assert placement.status_code == 422
    assert placement.json()["error"]["code"] == "PLACEMENT_WORKFLOW_REQUIRED"
    history = client.get(f"/api/v1/candidate-vacancies/{row['id']}/history").json()["items"]
    assert [item["to_status"] for item in history] == [
        "POTENTIAL_MATCH",
        "RECRUITER_REVIEW",
        "PRE_SCREEN",
        "QUALIFIED",
        "SUBMITTED",
        "INTERVIEW",
        "EMPLOYER_DECISION",
        "SELECTED",
    ]
    events = {
        event.event_code
        for event in db.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == UUID(str(row["id"])))
        )
    }
    assert {"candidate_vacancy.created", "candidate_vacancy.submitted"} <= events


def test_decline_is_vacancy_specific_and_bulk_write_is_atomic(db: Session) -> None:
    client, user = login(db)
    participant, first = parents(db, user, complete=True)
    row = create_candidate(client, participant, first, user)
    row = transition(client, row, "NOT_INTERESTED", "Declined this location")
    assert db.get(Participant, participant.id).onboarding_status == "COMPLETE"

    token = uuid4().hex[:10]
    second = Vacancy(
        vacancy_code="VAC-" + token.upper(),
        organization_id=first.organization_id,
        title="Second role",
        status="ACTIVE",
        required_headcount=1,
        created_by=user.id,
    )
    db.add(second)
    db.commit()
    another = create_candidate(client, participant, second, user)
    stale = client.post(
        "/api/v1/candidate-vacancies/bulk-transition",
        json={
            "candidates": [
                {"id": row["id"], "version": row["version"]},
                {"id": another["id"], "version": 999},
            ],
            "to_status": "RECRUITER_REVIEW",
        },
    )
    assert stale.status_code in {409, 422}
    assert (
        client.get(f"/api/v1/candidate-vacancies/{another['id']}").json()["status"]
        == "POTENTIAL_MATCH"
    )


def test_authorization_database_guards_and_advisory_suggestions(db: Session) -> None:
    client, user = login(db)
    participant, vacancy = parents(db, user, complete=True)
    row = create_candidate(client, participant, vacancy, user)
    demand, _ = login(db, "DEMAND")
    assert demand.get("/api/v1/candidate-vacancies").status_code == 403
    suggestions = client.post(f"/api/v1/vacancies/{vacancy.id}/match-suggestions").json()
    assert suggestions["advisory_only"] is True
    assert suggestions["items"] == []

    edit_permission = db.scalar(
        select(Permission).where(Permission.code == "candidate_pipeline:edit")
    )
    assert edit_permission
    db.add(PermissionOverride(user_id=user.id, permission_id=edit_permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    assert client.get(f"/api/v1/candidate-vacancies/{row['id']}").status_code == 200
    denied = client.patch(
        f"/api/v1/candidate-vacancies/{row['id']}",
        json={
            "version": row["version"],
            "owner_id": str(user.id),
            "priority": "HIGH",
            "next_action": "Should not be accepted",
            "reason": "Synthetic denied mutation",
        },
    )
    assert denied.status_code == 403

    history = db.scalar(
        select(CandidateHistory).where(
            CandidateHistory.candidate_vacancy_id == UUID(str(row["id"]))
        )
    )
    with pytest.raises(DBAPIError):
        db.execute(
            update(CandidateHistory)
            .where(CandidateHistory.id == history.id)
            .values(reason="rewritten")
        )
        db.flush()
    db.rollback()
    with pytest.raises(IntegrityError):
        db.add(
            CandidateVacancy(
                participant_id=participant.id,
                vacancy_id=vacancy.id,
                status="POTENTIAL_MATCH",
                source="STAFF",
                priority="NORMAL",
            )
        )
        db.flush()
    db.rollback()
    for model in (Screening, EmployerDecision, InterviewHistory):
        assert model.__table__.c.get("id") is not None
    assert db.scalar(text("SELECT count(*) FROM candidate_status_history")) >= 1


def test_placement_start_first_income_confirmation_and_later_exit(db: Session) -> None:
    client, user = login(db)
    participant, vacancy = parents(db, user, complete=True)
    candidate = CandidateVacancy(
        participant_id=participant.id,
        vacancy_id=vacancy.id,
        status="SELECTED",
        owner_id=user.id,
        source="STAFF",
        priority="NORMAL",
        submitted_at=datetime.now(UTC),
        selected_at=datetime.now(UTC),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(candidate)
    permission = db.scalar(select(Permission).where(Permission.code == "placement:confirm"))
    assert permission
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="ALLOW"))
    db.commit()
    db.expire_all()

    created = client.post(
        "/api/v1/placements",
        json={
            "candidate_vacancy_id": str(candidate.id),
            "candidate_version": candidate.version,
            "expected_start_date": "2026-10-10",
            "salary_amount": "2400.00",
            "salary_frequency": "MONTHLY",
            "payroll_frequency": "MONTHLY",
            "payday_rule_json": {"day": 25, "cutoff_day": 15},
        },
    )
    assert created.status_code == 201, created.text
    placement = created.json()
    assert placement["status"] == "START_PENDING"
    assert placement["salary_amount"] is None
    duplicate = client.post(
        "/api/v1/placements",
        json={"candidate_vacancy_id": str(candidate.id)},
    )
    assert duplicate.status_code == 409

    started = client.post(
        f"/api/v1/placements/{placement['id']}/confirm-start",
        json={
            "version": placement["version"],
            "actual_start_date": "2026-10-10",
            "notes": "Start verified with employer and participant",
        },
    )
    assert started.status_code == 200, started.text
    placement = started.json()
    assert placement["status"] == "AWAITING_FIRST_INCOME"
    assert placement["expected_first_income_date"] == "2026-10-25"
    assert placement["candidate_status"] == "AWAITING_FIRST_INCOME"

    income = placement["first_income"]
    confirmed = client.post(
        f"/api/v1/placements/{placement['id']}/first-income/confirm",
        json={
            "version": income["version"],
            "actual_income_received_date": "2026-10-25",
            "amount_received": "2400.00",
            "notes": "Participant and payslip verified",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    placement = confirmed.json()
    confirmed_at = placement["confirmed_at"]
    assert placement["status"] == "CONFIRMED"
    assert placement["candidate_status"] == "CONFIRMED_PLACEMENT"

    repeated = client.post(
        f"/api/v1/placements/{placement['id']}/first-income/confirm",
        json={
            "version": income["version"],
            "actual_income_received_date": "2026-10-25",
            "amount_received": "2400.00",
            "notes": "Participant and payslip verified",
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["confirmed_at"] == confirmed_at

    ended = client.post(
        f"/api/v1/placements/{placement['id']}/employment-end",
        json={
            "version": placement["version"],
            "employment_end_date": "2026-12-15",
            "reason": "Contract completed",
        },
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ENDED"
    assert ended.json()["confirmed_at"] == confirmed_at
    persisted = db.scalar(select(Placement).where(Placement.id == UUID(placement["id"])))
    assert persisted and persisted.salary_amount == 2400

    forbidden = client.post(
        f"/api/v1/placements/{placement['id']}/correct-confirmation",
        json={
            "version": ended.json()["version"],
            "confirmed": False,
            "reason": "Synthetic correction",
        },
    )
    assert forbidden.status_code == 403
    admin, _ = login(db, "ADMIN")
    corrected = admin.post(
        f"/api/v1/placements/{placement['id']}/correct-confirmation",
        json={
            "version": ended.json()["version"],
            "confirmed": False,
            "reason": "Duplicate verification evidence",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status"] == "ENDED"
    assert corrected.json()["confirmed_at"] is None
    restored = admin.post(
        f"/api/v1/placements/{placement['id']}/correct-confirmation",
        json={
            "version": corrected.json()["version"],
            "confirmed": True,
            "actual_income_received_date": "2026-10-25",
            "amount_received": "2400.00",
            "reason": "Evidence independently reverified",
        },
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "ENDED"
    assert restored.json()["confirmed_at"]
    events = {
        event.event_code
        for event in db.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == UUID(placement["id"]))
        )
    }
    assert {
        "placement.created",
        "placement.start_confirmed",
        "placement.first_income_confirmed",
        "placement.employment_ended",
        "placement.confirmation_corrected",
    } <= events
    history = db.scalar(
        select(PlacementHistory).where(PlacementHistory.placement_id == UUID(placement["id"]))
    )
    assert history
    with pytest.raises(DBAPIError):
        db.execute(
            update(PlacementHistory)
            .where(PlacementHistory.id == history.id)
            .values(reason="rewritten")
        )
        db.flush()
    db.rollback()

import os
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Organization, Vacancy
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher
from app.modules.marketing.models import CampaignAsset, ImpactStory
from app.modules.matching.models import CandidateVacancy
from app.modules.merl.models import Outcome
from app.modules.placement.models import Placement
from app.modules.supply.models import Consent, Participant, Person
from app.modules.training.models import Training

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic Marketing password 123"
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


def vacancy(db: Session, user: User) -> Vacancy:
    token = uuid4().hex[:10]
    organization = Organization(
        organization_code="ORG-" + token.upper(),
        name="Synthetic Marketing Employer",
        normalized_name="synthetic marketing employer " + token,
        organization_type="EMPLOYER",
        created_by=user.id,
    )
    db.add(organization)
    db.flush()
    row = Vacancy(
        vacancy_code="VAC-" + token.upper(),
        organization_id=organization.id,
        title="Synthetic campaign role",
        status="ACTIVE",
        required_headcount=2,
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    return row


def training(db: Session, user: User, title: str) -> Training:
    row = Training(
        training_code="TRN-" + uuid4().hex.upper(),
        title=title,
        training_type="EMPLOYABILITY",
        trainer_type="INTERNAL",
        mode="IN_PERSON",
        start_date=date(2026, 10, 15),
        modules_json=["JOB_SEARCH"],
        status="PLANNED",
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    return row


def story_outcome(db: Session, user: User) -> tuple[Outcome, Participant]:
    token = uuid4().hex[:10]
    person = Person(
        first_name="Adwoa",
        surname="Story Candidate",
        normalized_name="adwoa story candidate " + token,
        phone_raw="0241234567",
        phone_normalized="+233241234567",
        community="Accra",
        government_id_ciphertext="must-never-project",
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
        organization_code="ORG-STORY-" + token.upper(),
        name="Synthetic Story Employer",
        normalized_name="synthetic story employer " + token,
        organization_type="EMPLOYER",
        created_by=user.id,
    )
    db.add_all([participant, organization])
    db.flush()
    vacancy_row = Vacancy(
        vacancy_code="VAC-STORY-" + token.upper(),
        organization_id=organization.id,
        title="Story role",
        status="ACTIVE",
        required_headcount=1,
        created_by=user.id,
    )
    db.add(vacancy_row)
    db.flush()
    candidate = CandidateVacancy(
        participant_id=participant.id,
        vacancy_id=vacancy_row.id,
        status="CONFIRMED_PLACEMENT",
        source="STAFF",
        priority="NORMAL",
        submitted_at=datetime(2026, 9, 1, tzinfo=UTC),
        selected_at=datetime(2026, 9, 5, tzinfo=UTC),
        created_by=user.id,
    )
    db.add(candidate)
    db.flush()
    placement = Placement(
        placement_code="PLC-STORY-" + token.upper(),
        participant_id=participant.id,
        candidate_vacancy_id=candidate.id,
        organization_id=organization.id,
        vacancy_id=vacancy_row.id,
        status="CONFIRMED",
        actual_start_date=date(2026, 9, 10),
        confirmed_at=datetime(2026, 10, 1, tzinfo=UTC),
        currently_working=True,
        created_by=user.id,
    )
    db.add(placement)
    db.flush()
    outcome = Outcome(
        participant_id=participant.id,
        placement_id=placement.id,
        as_of_date=date(2026, 10, 10),
        currently_working=True,
        current_role="Story role",
        progress_text="Promoted after strong performance.",
        skills_gained_text="Customer service",
        impact_story_potential=True,
        verified_by=user.id,
        created_by=user.id,
    )
    db.add(outcome)
    db.commit()
    return outcome, participant


def test_request_lineage_and_requester_visibility(db: Session) -> None:
    demand, demand_user = login(db, "DEMAND")
    row = vacancy(db, demand_user)
    created = demand.post(
        "/api/v1/marketing/requests",
        json={
            "request_type": "VACANCY_PROMOTION",
            "vacancy_id": str(row.id),
            "reason": "Increase qualified applications.",
            "priority": "HIGH",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["requesting_workstream"] == "DEMAND"
    assert created.json()["requesting_user_id"] == str(demand_user.id)
    other, _ = login(db, "DEMAND")
    assert other.get(f"/api/v1/marketing/requests/{created.json()['id']}").status_code == 404
    marketing, _ = login(db, "MARKETING")
    assert marketing.get(f"/api/v1/marketing/requests/{created.json()['id']}").status_code == 200
    accepted = marketing.post(
        f"/api/v1/marketing/requests/{created.json()['id']}/transition",
        json={"version": created.json()["version"], "status": "ACCEPTED", "reason": "Scoped."},
    )
    assert accepted.status_code == 200
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "marketing_request.created"))


def test_campaign_state_assets_and_metrics(db: Session) -> None:
    marketing, user = login(db, "MARKETING")
    row = vacancy(db, user)
    created = marketing.post(
        "/api/v1/campaigns",
        json={
            "title": "Synthetic recruitment campaign",
            "campaign_type": "RECRUITMENT",
            "vacancy_id": str(row.id),
            "audience": "Qualified jobseekers in Accra",
            "channels_json": ["APPROVED_CHANNEL_PENDING_POLICY"],
        },
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    asset = marketing.post(
        f"/api/v1/campaigns/{campaign['id']}/assets",
        json={"asset_type": "SOCIAL_COPY", "title": "Draft copy", "content_text": "Apply now."},
    )
    assert asset.status_code == 201
    reviewed = marketing.post(
        f"/api/v1/campaign-assets/{asset.json()['id']}/review",
        json={
            "version": asset.json()["version"],
            "approval_status": "APPROVED",
            "reason": "Reviewed.",
        },
    )
    assert reviewed.status_code == 200
    assert db.get(CampaignAsset, asset.json()["id"]).approval_status == "APPROVED"
    for status in ("IN_PRODUCTION", "AWAITING_REVIEW", "APPROVED"):
        response = marketing.post(
            f"/api/v1/campaigns/{campaign['id']}/transition",
            json={"version": campaign["version"], "status": status, "reason": "Progressed."},
        )
        assert response.status_code == 200, response.text
        campaign = response.json()
    assert (
        marketing.post(
            f"/api/v1/campaigns/{campaign['id']}/transition",
            json={"version": campaign["version"], "status": "SCHEDULED", "reason": "Schedule."},
        ).status_code
        == 422
    )
    published = marketing.post(
        f"/api/v1/campaigns/{campaign['id']}/transition",
        json={"version": campaign["version"], "status": "PUBLISHED", "reason": "Published."},
    )
    assert published.status_code == 200
    metrics = marketing.post(
        f"/api/v1/campaigns/{campaign['id']}/metrics",
        json={"version": published.json()["version"], "metrics": {"leads": 12, "source": "manual"}},
    )
    assert metrics.status_code == 200 and metrics.json()["metrics_json"]["leads"] == 12


def test_training_request_and_campaign_preserve_lineage(db: Session) -> None:
    marketing, user = login(db, "MARKETING")
    first = training(db, user, "Synthetic employability cohort")
    second = training(db, user, "Different training cohort")
    request = marketing.post(
        "/api/v1/marketing/requests",
        json={
            "request_type": "TRAINING_PROMOTION",
            "training_id": str(first.id),
            "reason": "Recruit participants for the cohort.",
            "priority": "NORMAL",
        },
    )
    assert request.status_code == 201, request.text
    assert request.json()["training_id"] == str(first.id)
    campaign = marketing.post(
        "/api/v1/campaigns",
        json={
            "title": "Training recruitment campaign",
            "campaign_type": "TRAINING",
            "marketing_request_id": request.json()["id"],
            "training_id": str(first.id),
            "audience": "Eligible programme participants",
            "channels_json": [],
        },
    )
    assert campaign.status_code == 201, campaign.text
    assert campaign.json()["training_id"] == str(first.id)
    mismatch = marketing.post(
        "/api/v1/campaigns",
        json={
            "title": "Mismatched training campaign",
            "campaign_type": "TRAINING",
            "marketing_request_id": request.json()["id"],
            "training_id": str(second.id),
            "audience": "Eligible programme participants",
            "channels_json": [],
        },
    )
    assert mismatch.status_code == 422
    invalid = marketing.post(
        "/api/v1/marketing/requests",
        json={
            "request_type": "PROGRAMME_AWARENESS",
            "training_id": str(first.id),
            "reason": "Invalid mixed linkage.",
        },
    )
    assert invalid.status_code == 422


def test_impact_story_requires_active_consent_and_projects_only_approved_facts(db: Session) -> None:
    marketing, user = login(db, "MARKETING")
    outcome, participant = story_outcome(db, user)
    created = marketing.post("/api/v1/impact-stories", json={"source_outcome_id": str(outcome.id)})
    assert created.status_code == 201, created.text
    story = created.json()
    assert story["participant_name"] is None
    assert set(story["approved_facts"]) == {
        "as_of_date",
        "currently_working",
        "current_role",
        "skills_gained",
        "progress",
    }
    assert "government_id" not in str(story)
    denied = marketing.post(
        f"/api/v1/impact-stories/{story['id']}/transition",
        json={"version": story["version"], "status": "READY_FOR_MARKETING", "reason": "Ready."},
    )
    assert denied.status_code == 422
    consent = Consent(
        participant_id=participant.id,
        consent_type="PUBLICATION",
        status="ACTIVE",
        consented_at=datetime.now(UTC),
        method="STAFF_RECORDED",
        privacy_notice_version="SYNTHETIC-MARKETING-CONSENT",
        created_by=user.id,
    )
    db.add(consent)
    db.commit()
    updated = marketing.patch(
        f"/api/v1/impact-stories/{story['id']}",
        json={"version": story["version"], "marketing_consent_id": str(consent.id)},
    )
    assert updated.status_code == 200
    assert updated.json()["participant_name"] == "Adwoa Story Candidate"
    ready = marketing.post(
        f"/api/v1/impact-stories/{story['id']}/transition",
        json={
            "version": updated.json()["version"],
            "status": "READY_FOR_MARKETING",
            "reason": "Consent verified.",
        },
    )
    assert ready.status_code == 200
    assert db.get(ImpactStory, story["id"]).status == "READY_FOR_MARKETING"


def test_management_has_read_only_marketing_projection(db: Session) -> None:
    management, _ = login(db, "MANAGEMENT")
    assert management.get("/api/v1/campaigns").status_code == 200
    assert management.get("/api/v1/impact-stories").status_code == 200
    assert management.post("/api/v1/campaigns", json={}).status_code == 403
    assert management.post("/api/v1/impact-stories", json={}).status_code == 403

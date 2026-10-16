import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.integrations.cv_parser import ParserOutput, ParserSuggestion, get_cv_parser
from app.main import app
from app.modules.cv_parser import service
from app.modules.cv_parser.models import ParserJob, ParserResult, ParserReview
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher
from app.modules.supply.models import Document, Participant, Person, Skill

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic parser password 123"
ORIGIN = {"Origin": "http://localhost:3000"}


class FakeParser:
    def parse(self, content: bytes, mime_type: str, filename: str) -> ParserOutput:
        assert content == b"synthetic private cv"
        assert mime_type == "application/pdf" and filename == "candidate.pdf"
        return ParserOutput(
            provider="SYNTHETIC_TEST_PARSER",
            model="test-v1",
            suggestions=(
                ParserSuggestion("first_name", "Ama", 0.98),
                ParserSuggestion("email", "parsed@example.org", 0.91),
                ParserSuggestion("skills", ["Customer service", "Excel"], 0.83),
            ),
        )


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
    monkeypatch.setattr(service, "verified_bytes", lambda document: b"synthetic private cv")
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()


def login(db: Session, code: str = "SUPPLY") -> tuple[TestClient, User]:
    role = db.scalar(select(Role).where(Role.code == code))
    assert role
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic Parser Reviewer",
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


def cv(db: Session, user: User) -> tuple[Participant, Person, Document]:
    token = uuid4().hex[:10]
    person = Person(
        first_name="Original",
        surname="Candidate",
        normalized_name="original candidate " + token,
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
        onboarding_status="IN_PROGRESS",
        cv_status="UPLOADED",
        created_by=user.id,
    )
    db.add(participant)
    db.flush()
    document = Document(
        participant_id=participant.id,
        document_code="DOC-" + token.upper(),
        storage_key="synthetic/" + token,
        original_filename="candidate.pdf",
        mime_type="application/pdf",
        size_bytes=20,
        sha256="0" * 64,
        version_number=1,
        scan_status="AVAILABLE",
        created_by=user.id,
    )
    db.add(document)
    db.commit()
    return participant, person, document


def test_parser_output_is_advisory_until_explicit_human_review(db: Session) -> None:
    client, user = login(db)
    participant, person, document = cv(db, user)
    app.dependency_overrides[get_cv_parser] = lambda: FakeParser()

    response = client.post(f"/api/v1/cv/{document.id}/parse")
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "SUCCEEDED"
    assert job["result"]["review_status"] == "PENDING_REVIEW"
    db.refresh(person)
    db.refresh(participant)
    assert person.first_name == "Original"
    assert person.email is None
    assert participant.current_cv_id is None
    assert participant.cv_status == "REVIEW_REQUIRED"

    result_id = job["result"]["id"]
    stale = client.post(
        f"/api/v1/cv-parser/results/{result_id}/review",
        json={
            "participant_version": participant.version - 1,
            "decisions": [{"field": "first_name", "decision": "APPROVE"}],
        },
    )
    assert stale.status_code == 409
    response = client.post(
        f"/api/v1/cv-parser/results/{result_id}/review",
        json={
            "participant_version": participant.version,
            "decisions": [
                {"field": "first_name", "decision": "APPROVE"},
                {
                    "field": "email",
                    "decision": "EDIT",
                    "value": "reviewed@example.org",
                    "reason": "Candidate confirmed the preferred address.",
                },
                {"field": "skills", "decision": "APPROVE"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "APPROVED"
    db.refresh(person)
    db.refresh(participant)
    assert person.first_name == "Ama" and person.email == "reviewed@example.org"
    assert participant.current_cv_id == document.id and participant.cv_status == "READY"
    assert set(
        db.scalars(select(Skill.skill_name).where(Skill.participant_id == participant.id))
    ) == {"Customer service", "Excel"}
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "cv_parser.reviewed", AuditEvent.entity_id == result_id
        )
    )
    assert event and event.actor_type == "USER"


def test_unconfigured_parser_fails_without_blocking_existing_cv_workflow(db: Session) -> None:
    client, user = login(db)
    participant, _, document = cv(db, user)
    response = client.post(f"/api/v1/cv/{document.id}/parse")
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert response.json()["error_code"] == "PARSER_UNAVAILABLE"
    db.refresh(participant)
    assert participant.cv_status == "UPLOADED"
    assert (
        db.scalar(select(ParserResult).where(ParserResult.job_id == response.json()["id"])) is None
    )


def test_parser_execution_and_review_are_server_authorized(db: Session) -> None:
    matching_client, matching_user = login(db, "MATCHING")
    _, _, document = cv(db, matching_user)
    assert matching_client.get(f"/api/v1/cv/{document.id}/parser-jobs").status_code == 200
    assert matching_client.post(f"/api/v1/cv/{document.id}/parse").status_code == 403


def test_review_history_is_append_only(db: Session) -> None:
    client, user = login(db)
    participant, _, document = cv(db, user)
    app.dependency_overrides[get_cv_parser] = lambda: FakeParser()
    job = client.post(f"/api/v1/cv/{document.id}/parse").json()
    result = db.get(ParserResult, job["result"]["id"])
    assert result
    review = ParserReview(
        result_id=result.id,
        field="first_name",
        decision="REJECT",
        original_value_json="Ama",
        reviewed_by=user.id,
    )
    db.add(review)
    db.commit()
    with pytest.raises(DBAPIError):
        db.execute(
            text("UPDATE cv_parser_results SET suggestions_json='[]'::json WHERE id=:id"),
            {"id": result.id},
        )
        db.flush()
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(
            text("UPDATE cv_parser_reviews SET reason='changed' WHERE id=:id"),
            {"id": review.id},
        )
        db.flush()
    db.rollback()
    assert db.get(ParserJob, job["id"]) is not None

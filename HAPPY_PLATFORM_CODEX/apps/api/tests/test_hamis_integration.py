import os
from contextlib import nullcontext
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.integrations.hamis import service
from app.integrations.hamis import worker as hamis_worker
from app.integrations.hamis.models import HamisInboundEvent
from app.main import app
from app.modules.external_references.models import ExternalReference
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher
from app.modules.supply.models import Participant, Person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
TOKEN = "hamis-test-token-with-more-than-thirty-two-characters"
PASSWORD = "Synthetic HAMIS password 123"
ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture(scope="module")
def engine():
    schema, url = create_test_schema()
    instance = create_engine(url)
    old_token = settings.hamis_integration_token
    old_encryption_key = settings.identity_encryption_key
    settings.hamis_integration_token = SecretStr(TOKEN)
    settings.identity_encryption_key = SecretStr(Fernet.generate_key().decode())
    try:
        yield instance
    finally:
        settings.hamis_integration_token = old_token
        settings.identity_encryption_key = old_encryption_key
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


def machine() -> TestClient:
    client = TestClient(app)
    client.headers.update({"Authorization": "Bearer " + TOKEN})
    return client


def login(db: Session, code: str) -> TestClient:
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
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    client.headers.update({**ORIGIN, "X-CSRF-Token": client.cookies.get("happy_csrf")})
    return client


def participant_payload(token: str = "001") -> dict:
    return {
        "participantId": "HAPPY-2026-" + token,
        "hamisId": "HAMIS-GA-" + token,
        "firstName": "Akosua",
        "surname": "Mensah " + token,
        "telephone": "0241000" + token,
        "consentEmail": f"akosua.{token}@example.org",
        "region": "GREATER_ACCRA",
        "district": "ACCRA_METROPOLITAN",
        "community": "Accra",
        "implementingPartner": "HAPPY",
    }


def event(event_id: str, payload: dict, event_type: str = "PARTICIPANT_UPSERT") -> dict:
    return {"event_id": event_id, "event_type": event_type, "payload": payload}


def process_received(db: Session, event_id: str) -> HamisInboundEvent:
    row = db.scalar(
        select(HamisInboundEvent).where(HamisInboundEvent.external_event_id == event_id)
    )
    assert row and row.status == "RECEIVED"
    service.process_event(db, row)
    db.commit()
    return row


def test_machine_auth_idempotency_provenance_and_update_review(db: Session) -> None:
    unauthenticated = TestClient(app).post(
        "/api/v1/integrations/hamis/events",
        json=event("evt-no-auth", participant_payload("010")),
    )
    assert unauthenticated.status_code == 401

    client = machine()
    payload = participant_payload()
    response = client.post(
        "/api/v1/integrations/hamis/events", json=event("queue-device-001", payload)
    )
    assert response.status_code == 202
    result = response.json()
    assert result["status"] == "RECEIVED"
    stored_event = process_received(db, "queue-device-001")
    assert stored_event.status == "APPLIED"
    participant_id = stored_event.participant_id
    assert participant_id
    assert payload["telephone"] not in stored_event.payload_ciphertext
    assert payload["hamisId"] not in stored_event.payload_ciphertext

    participant = db.get(Participant, participant_id)
    assert participant
    person = db.get(Person, participant.person_id)
    assert person
    assert participant.source_system == "HAMIS"
    assert participant.created_via == "INTEGRATION"
    assert person.source_system == "HAMIS"
    assert participant.participant_code != payload["participantId"]

    reference = db.scalar(
        select(ExternalReference).where(
            ExternalReference.external_system == "HAMIS",
            ExternalReference.external_id == payload["hamisId"],
        )
    )
    assert reference and reference.entity_id == participant_id

    replay = client.post(
        "/api/v1/integrations/hamis/events", json=event("queue-device-001", payload)
    )
    assert replay.status_code == 202
    assert replay.json()["replayed"] is True
    assert db.scalar(select(func.count()).select_from(Participant)) == 1

    conflict = client.post(
        "/api/v1/integrations/hamis/events",
        json=event("queue-device-001", payload | {"community": "Tema"}),
    )
    assert conflict.status_code == 409

    update = client.post(
        "/api/v1/integrations/hamis/events",
        json=event("queue-device-002", payload | {"community": "Tema"}),
    )
    assert update.status_code == 202
    assert update.json()["status"] == "RECEIVED"
    assert process_received(db, "queue-device-002").status == "NEEDS_REVIEW"
    db.refresh(person)
    assert person.community == "Accra"

    audit_event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "hamis.event_received",
            AuditEvent.actor_type == "INTEGRATION",
            AuditEvent.actor_id == "HAMIS",
        )
    )
    assert audit_event


def test_duplicate_and_domain_activity_require_review(db: Session) -> None:
    client = machine()
    first = client.post(
        "/api/v1/integrations/hamis/events",
        json=event("duplicate-source", participant_payload("020")),
    )
    assert first.status_code == 202
    assert process_received(db, "duplicate-source").status == "APPLIED"
    duplicate_payload = participant_payload("021") | {
        "telephone": participant_payload("020")["telephone"]
    }
    duplicate = client.post(
        "/api/v1/integrations/hamis/events",
        json=event("duplicate-candidate", duplicate_payload),
    )
    assert duplicate.status_code == 202
    assert process_received(db, "duplicate-candidate").status == "NEEDS_REVIEW"

    training = client.post(
        "/api/v1/integrations/hamis/events",
        json=event(
            "capacity-001",
            {"participantId": "HAPPY-2026-020", "modules": "Digital Skills"},
            "TRAINING_RECORDED",
        ),
    )
    assert training.status_code == 202
    assert process_received(db, "capacity-001").status == "NEEDS_REVIEW"


def test_only_admin_can_review_events(db: Session) -> None:
    created = machine().post(
        "/api/v1/integrations/hamis/events",
        json=event(
            "review-capacity-001",
            {"participantId": "HAPPY-2026-999", "modules": "Digital Skills"},
            "TRAINING_RECORDED",
        ),
    )
    assert created.status_code == 202
    assert process_received(db, "review-capacity-001").status == "NEEDS_REVIEW"
    event_row = db.scalar(
        select(HamisInboundEvent).where(HamisInboundEvent.status == "NEEDS_REVIEW")
    )
    assert event_row
    supply = login(db, "SUPPLY")
    assert supply.get("/api/v1/integrations/hamis/events").status_code == 403

    admin = login(db, "ADMIN")
    listing = admin.get("/api/v1/integrations/hamis/events?status=NEEDS_REVIEW")
    assert listing.status_code == 200
    rejected = admin.post(
        f"/api/v1/integrations/hamis/events/{event_row.id}/review",
        json={"version": event_row.version, "decision": "REJECT", "reason": "Invalid source"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"


def test_worker_claims_committed_event_and_records_integration_actor(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = machine().post(
        "/api/v1/integrations/hamis/events",
        json=event("worker-participant-001", participant_payload("031")),
    )
    assert response.status_code == 202
    assert response.json()["status"] == "RECEIVED"
    monkeypatch.setattr(
        hamis_worker,
        "get_session_factory",
        lambda: lambda: nullcontext(db),
    )
    assert hamis_worker.run_once() is True
    row = db.scalar(
        select(HamisInboundEvent).where(
            HamisInboundEvent.external_event_id == "worker-participant-001"
        )
    )
    assert row and row.status == "APPLIED" and row.attempt_count == 1
    assert row.lease_owner is None and row.participant_id
    assert db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "hamis.event_processed",
            AuditEvent.actor_type == "INTEGRATION",
            AuditEvent.actor_id == "HAMIS",
            AuditEvent.entity_id == row.id,
        )
    )

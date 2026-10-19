import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher
from app.modules.supply.models import Participant, Person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic Training password 123"
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


def login(db: Session, role_code: str) -> tuple[TestClient, User]:
    role = db.scalar(select(Role).where(Role.code == role_code))
    assert role
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic " + role_code,
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


def participant(db: Session, user: User) -> Participant:
    token = uuid4().hex[:10]
    person = Person(
        first_name="Ama",
        surname="Training",
        normalized_name="ama training " + token,
        phone_raw="024" + token[:7],
        phone_normalized="+23324" + token[:7],
        community="Accra",
        created_by=user.id,
    )
    db.add(person)
    db.flush()
    row = Participant(
        participant_code="HAPPY-" + token.upper(),
        person_id=person.id,
        onboarding_status="IN_PROGRESS",
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    return row


def payload() -> dict:
    return {
        "title": "Digital employability",
        "training_type": "EMPLOYABILITY",
        "trainer_type": "INTERNAL",
        "mode": "IN_PERSON",
        "start_date": "2026-10-20",
        "end_date": "2026-10-22",
        "location_region_code": "GREATER_ACCRA",
        "location_community": "Accra",
        "modules_json": ["CV writing", "Interview preparation"],
        "status": "PLANNED",
    }


def test_training_attendance_permissions_uniqueness_and_audit(db: Session) -> None:
    supply, user = login(db, "SUPPLY")
    person = participant(db, user)
    created = supply.post("/api/v1/trainings", json=payload())
    assert created.status_code == 201
    training = created.json()
    assert training["source_system"] == "INTERNAL"

    enrolled = supply.post(
        f"/api/v1/trainings/{training['id']}/participants",
        json={"participant_ids": [str(person.id)], "attendance_status": "PRESENT"},
    )
    assert enrolled.status_code == 201
    attendance = enrolled.json()["items"][0]
    assert attendance["participant_id"] == str(person.id)

    updated = supply.patch(
        f"/api/v1/training-attendance/{attendance['id']}",
        json={
            "version": attendance["version"],
            "attendance_status": "PRESENT",
            "completion_status": "COMPLETED",
            "notes": "Completed all modules",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["completion_status"] == "COMPLETED"

    management, _ = login(db, "MANAGEMENT")
    assert management.get("/api/v1/trainings").status_code == 200
    assert management.post("/api/v1/trainings", json=payload()).status_code == 403

    actions = set(
        db.scalars(
            select(AuditEvent.action).where(
                AuditEvent.entity_type.in_(["training", "training_attendance"])
            )
        )
    )
    assert {
        "training.created",
        "training.participants_added",
        "training_attendance.updated",
    } <= actions

    duplicate = supply.post(
        f"/api/v1/trainings/{training['id']}/participants",
        json={"participant_ids": [str(person.id)]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "TRAINING_ATTENDANCE_EXISTS"


def test_training_validation(db: Session) -> None:
    client, _ = login(db, "SUPPLY")
    invalid = payload() | {
        "trainer_type": "EXTERNAL_PARTNER",
        "mode": "VIRTUAL",
        "end_date": "2026-10-19",
    }
    response = client.post("/api/v1/trainings", json=invalid)
    assert response.status_code == 422

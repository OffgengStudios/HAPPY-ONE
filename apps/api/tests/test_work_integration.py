import os
from datetime import UTC, datetime, timedelta
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
from app.modules.work.models import Handoff, Notification, Task

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic work password 123"
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


def test_task_scope_transitions_notification_version_and_audit(db: Session) -> None:
    demand, creator = login(db, "DEMAND")
    supply, assignee = login(db, "SUPPLY")
    matching, _ = login(db, "MATCHING")
    response = demand.post(
        "/api/v1/tasks",
        json={
            "title": "Complete participant intake",
            "description": "Review the consent and CV.",
            "priority": "HIGH",
            "owner_user_id": str(assignee.id),
            "owner_team": "SUPPLY",
            "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["task_code"].startswith("TSK-") and task["status"] == "OPEN"
    assert supply.get("/api/v1/tasks").json()["items"][0]["id"] == task["id"]
    assert matching.get("/api/v1/tasks").json()["items"] == []

    notices = supply.get("/api/v1/notifications").json()["items"]
    assert len(notices) == 1 and notices[0]["kind"] == "TASK_ASSIGNED"
    assert demand.get("/api/v1/notifications").json()["items"] == []
    assert (
        demand.post(
            f"/api/v1/notifications/{notices[0]['id']}/read", json={"version": 1}
        ).status_code
        == 404
    )
    read = supply.post(f"/api/v1/notifications/{notices[0]['id']}/read", json={"version": 1})
    assert read.status_code == 200 and read.json()["read_at"]

    claimed = supply.post(f"/api/v1/tasks/{task['id']}/claim", json={"version": 1})
    assert claimed.status_code == 200 and claimed.json()["status"] == "IN_PROGRESS"
    stale = supply.post(f"/api/v1/tasks/{task['id']}/complete", json={"version": 1})
    assert stale.status_code == 409
    completed = supply.post(f"/api/v1/tasks/{task['id']}/complete", json={"version": 2})
    assert completed.status_code == 200 and completed.json()["completed_at"]
    row = db.get(Task, task["id"])
    assert row and row.created_by == creator.id
    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == row.id)))
    assert {"task.created", "task.claimed", "task.completed"} <= actions


def test_cross_workstream_handoff_lifecycle_is_server_scoped(db: Session) -> None:
    demand, _ = login(db, "DEMAND")
    supply, supply_user = login(db, "SUPPLY")
    marketing, _ = login(db, "MARKETING")
    entity_id = uuid4()
    response = demand.post(
        "/api/v1/handoffs",
        json={
            "from_workstream": "DEMAND",
            "to_workstream": "SUPPLY",
            "entity_type": "ORGANIZATION",
            "entity_id": str(entity_id),
            "reason": "Confirm participant pipeline for this employer.",
            "assigned_to": str(supply_user.id),
        },
    )
    assert response.status_code == 201, response.text
    handoff = response.json()
    assert handoff["status"] == "SENT"
    assert marketing.get("/api/v1/handoffs").json()["items"] == []
    assert supply.get("/api/v1/handoffs").json()["items"][0]["id"] == handoff["id"]
    accepted = supply.post(f"/api/v1/handoffs/{handoff['id']}/accept", json={"version": 1})
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED"
    completed = supply.post(f"/api/v1/handoffs/{handoff['id']}/complete", json={"version": 2})
    assert completed.status_code == 200 and completed.json()["status"] == "COMPLETED"
    row = db.get(Handoff, handoff["id"])
    assert row and row.completed_at
    assert db.scalar(
        select(Notification).where(
            Notification.recipient_user_id == supply_user.id,
            Notification.entity_id == row.id,
        )
    )


def test_handoff_rejects_unknown_or_same_workstream(db: Session) -> None:
    client, _ = login(db, "DEMAND")
    base = {
        "from_workstream": "DEMAND",
        "to_workstream": "DEMAND",
        "entity_type": "VACANCY",
        "entity_id": str(uuid4()),
        "reason": "Synthetic invalid handoff.",
    }
    assert client.post("/api/v1/handoffs", json=base).status_code == 422
    assert (
        client.post("/api/v1/handoffs", json={**base, "to_workstream": "UNKNOWN"}).status_code
        == 422
    )

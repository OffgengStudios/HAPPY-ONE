import os
import subprocess
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import API_ROOT, settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Organization
from app.modules.external_references.models import ExternalReference
from app.modules.iam.actors import AuditActor
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, Role, User, now
from app.modules.iam.security import hasher
from app.modules.iam.service import audit
from app.modules.supply.models import Participant, Person

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires local PostgreSQL."
    ),
]
PASSWORD = "Synthetic readiness password 123"
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
    previous = settings.api_cors_origins
    settings.api_cors_origins = ["http://localhost:3000"]
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        settings.api_cors_origins = previous
        session.close()
        transaction.rollback()
        connection.close()


def login(db, role_code="ADMIN"):
    role = db.scalar(select(Role).where(Role.code == role_code))
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic Staff",
        password_hash=hasher.hash(PASSWORD),
        roles=[role],
        primary_role_id=role.id,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}, headers=ORIGIN
        ).status_code
        == 200
    )
    client.headers.update({**ORIGIN, "X-CSRF-Token": client.cookies.get("happy_csrf")})
    return client, user


def employer(db):
    row = Organization(
        organization_code="EMP-" + uuid4().hex[:12],
        name="Synthetic Employer",
        normalized_name="synthetic employer",
        organization_type="EMPLOYER",
    )
    db.add(row)
    db.commit()
    return row


def reference(client, row, system="EMPLOYER_PORTAL", external_id="EMP-000438", **values):
    return client.post(
        "/api/v1/external-references",
        json={
            "entity_type": "ORGANIZATION",
            "entity_id": str(row.id),
            "external_system": system,
            "external_id": external_id,
            **values,
        },
    )


def test_references_bind_uuid_without_mutating_domain_identity(db):
    client, _ = login(db)
    row = employer(db)
    internal, code = row.id, row.organization_code
    first = reference(client, row)
    assert first.status_code == 201, first.text
    assert first.json()["entity_id"] == str(internal)
    assert first.json()["external_id"] != str(internal)
    second = reference(client, row, "PARTNER_CRM", "OTHER-1")
    assert second.status_code == 201
    records = client.get(
        "/api/v1/external-references",
        params={"entity_type": "ORGANIZATION", "entity_id": str(row.id), "limit": 1},
    )
    assert len(records.json()["items"]) == 1
    assert records.json()["next_cursor"]
    assert records.headers["Cache-Control"] == "no-store"
    assert db.get(Organization, internal).organization_code == code
    assert row.source_system == "INTERNAL" and row.created_via == "STAFF"


def test_duplicate_key_rejected_even_for_another_entity(db):
    client, _ = login(db)
    first, second = employer(db), employer(db)
    assert reference(client, first).status_code == 201
    assert reference(client, second).status_code == 409
    db.rollback()
    assert db.scalar(select(ExternalReference.entity_id)) == first.id


def test_duplicate_key_enforced_by_database(db):
    row = employer(db)
    values = {
        "entity_type": "ORGANIZATION",
        "entity_id": row.id,
        "external_system": "EMPLOYER_PORTAL",
        "external_id": "DUPLICATE",
        "external_metadata": {},
    }
    db.add(ExternalReference(**values))
    db.commit()
    with pytest.raises(IntegrityError, match="uq_external_reference_key"), db.begin_nested():
        db.add(ExternalReference(**values))
        db.flush()


def test_metadata_is_passive_and_does_not_grant_access(db):
    admin, _ = login(db)
    ordinary, user = login(db, "MARKETING")
    row = employer(db)
    result = reference(
        admin,
        row,
        external_metadata={
            "user_id": str(user.id),
            "permissions": ["user:manage", "organization:view"],
            "source_system": "HAMIS",
            "actor_type": "INTEGRATION",
        },
    )
    assert result.status_code == 201
    assert ordinary.get("/api/v1/external-references/" + result.json()["id"]).status_code == 403
    assert ordinary.get("/api/v1/organizations/" + str(row.id)).status_code == 403
    assert ordinary.get("/api/v1/users").status_code == 403
    assert "user:manage" not in ordinary.get("/api/v1/auth/me").json()["permissions"]
    assert row.source_system == "INTERNAL"


@pytest.mark.parametrize(
    "denied",
    [
        "organization:view",
        "organization:edit",
        "external_reference:view",
        "external_reference:manage",
    ],
)
def test_reference_management_cannot_bypass_explicit_denies(db, denied):
    client, user = login(db)
    row = employer(db)
    permission = db.scalar(select(Permission).where(Permission.code == denied))
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    assert reference(client, row).status_code == 403
    if denied.endswith(":view"):
        assert (
            client.get(
                "/api/v1/external-references",
                params={"entity_type": "ORGANIZATION", "entity_id": str(row.id)},
            ).status_code
            == 403
        )


def test_missing_archived_unknown_targets_and_csrf(db):
    client, _ = login(db)
    row = employer(db)
    assert reference(client, row, entity_id=str(uuid4())).status_code == 404
    assert reference(client, row, entity_type="USER").status_code == 422
    client.headers.pop("X-CSRF-Token")
    assert reference(client, row).status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies.get("happy_csrf")
    from app.modules.iam.models import now

    row.archived_at = now()
    db.commit()
    assert reference(client, row).status_code == 409


def test_metadata_update_stale_and_rebinding_denied(db):
    client, _ = login(db)
    row = employer(db)
    created = reference(client, row).json()
    path = "/api/v1/external-references/" + created["id"]
    assert (
        client.patch(
            path, json={"version": 1, "external_metadata": {"label": "Reviewed"}}
        ).status_code
        == 200
    )
    assert client.patch(path, json={"version": 1, "external_metadata": {}}).status_code == 409
    assert (
        client.patch(
            path, json={"version": 2, "external_metadata": {}, "entity_id": str(uuid4())}
        ).status_code
        == 422
    )
    assert client.get(path).json()["entity_id"] == str(row.id)


@pytest.mark.parametrize("source", ["INTERNAL", "HAMIS", "EMPLOYER_PORTAL", "API"])
def test_controlled_provenance_at_database_boundary(db, source):
    row = employer(db)
    row.source_system = source
    row.created_via = "INTEGRATION" if source != "INTERNAL" else "STAFF"
    db.flush()
    with pytest.raises(IntegrityError, match="ck_source_system"), db.begin_nested():
        db.execute(
            text("UPDATE organizations SET source_system='spreadsheet' WHERE id=:id"),
            {"id": row.id},
        )
    with pytest.raises(IntegrityError, match="ck_created_via"), db.begin_nested():
        db.execute(
            text("UPDATE organizations SET created_via='someone' WHERE id=:id"), {"id": row.id}
        )


def test_staff_provenance_defaults_and_mass_assignment(db):
    client, _ = login(db)
    response = client.post(
        "/api/v1/organizations",
        json={
            "name": "Synthetic Staff Employer",
            "organization_type": "EMPLOYER",
            "mou_required": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["source_system"] == "INTERNAL"
    assert response.json()["created_via"] == "STAFF"
    assert (
        client.post(
            "/api/v1/organizations",
            json={
                "name": "Spoofed",
                "organization_type": "EMPLOYER",
                "mou_required": True,
                "source_system": "HAMIS",
            },
        ).status_code
        == 422
    )


def test_user_system_and_future_integration_audit_preserve_append_only_behavior(db):
    client, user = login(db)
    for actor in (
        user.id,
        None,
        AuditActor("SYSTEM", "WORKER"),
        AuditActor("INTEGRATION", "HAMIS"),
        AuditActor("INTEGRATION", "EMPLOYER_PORTAL"),
        AuditActor("PARTICIPANT", str(uuid4())),
        AuditActor("EMPLOYER", str(uuid4())),
    ):
        audit(db, "readiness.test_actor", actor)
    db.commit()
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.event_code == "readiness.test_actor")
    ).all()
    assert len(events) == 7
    assert any(e.actor_type == "USER" and e.actor_id == str(user.id) for e in events)
    assert any(e.actor_type == "INTEGRATION" and e.actor_id == "HAMIS" for e in events)
    assert len(db.scalars(select(User)).all()) == 1
    assert client.get("/api/v1/audit-events").status_code == 200
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM audit_events WHERE event_code='readiness.test_actor'"))
    with pytest.raises(IntegrityError, match="ck_audit_actor"), db.begin_nested():
        db.add(
            AuditEvent(
                event_code="invalid",
                action="invalid",
                actor_type="INTEGRATION",
                actor_id=None,
                entity_type="system",
            )
        )
        db.flush()


def test_participant_mapping_is_generic_not_a_hamis_column(db):
    client, _ = login(db)
    person = Person(
        first_name="Synthetic",
        surname="Participant",
        normalized_name="synthetic participant",
        phone_raw="0241234567",
        phone_normalized="+233241234567",
        community="Accra",
    )
    db.add(person)
    db.flush()
    row = Participant(person_id=person.id, participant_code="HAPPY-" + uuid4().hex[:16])
    db.add(row)
    db.commit()
    response = client.post(
        "/api/v1/external-references",
        json={
            "entity_type": "PARTICIPANT",
            "entity_id": str(row.id),
            "external_system": "HAMIS",
            "external_id": "HAPPY-2026-001284",
        },
    )
    assert response.status_code == 201
    assert response.json()["entity_id"] == str(row.id)
    assert "hamis_id" not in Participant.__table__.columns
    assert not any("hamis" in str(column.name) for column in Participant.__table__.columns)
    assert row.source_system == "INTERNAL"


def test_forward_migration_preserves_local_references_and_user_audit():
    # Only this disposable synthetic schema ever moves back to the legacy revision.
    schema, url = create_test_schema()
    instance = create_engine(url)

    def migrate(direction, revision):
        return subprocess.run(
            [sys.executable, "-m", "alembic", direction, revision],
            cwd=API_ROOT,
            env={**os.environ, "DATABASE_URL": url, "APP_ENV": "test"},
            capture_output=True,
            text=True,
            timeout=60,
        )

    try:
        previous = migrate("downgrade", "0008_supply_permissions")
        assert previous.returncode == 0, previous.stderr
        metadata = MetaData()
        people = Table("people", metadata, autoload_with=instance)
        participants = Table("participants", metadata, autoload_with=instance)
        events = Table("audit_events", metadata, autoload_with=instance)
        person_id, participant_id, actor_id, event_id = (uuid4() for _ in range(4))
        common = {"created_at": now(), "updated_at": now(), "version": 1}
        with instance.begin() as connection:
            connection.execute(
                people.insert().values(
                    id=person_id,
                    first_name="Synthetic",
                    surname="Legacy",
                    normalized_name="synthetic legacy",
                    phone_raw="0241234567",
                    phone_normalized="+233241234567",
                    community="Accra",
                    **common,
                )
            )
            connection.execute(
                participants.insert().values(
                    id=participant_id,
                    person_id=person_id,
                    participant_code="HAPPY-LOCAL-TEST",
                    programme_code="HAPPY",
                    hamis_id="HAPPY-LEGACY-TEST",
                    onboarding_status="NOT_STARTED",
                    readiness_status="NOT_ASSESSED",
                    availability_status="UNKNOWN",
                    cv_status="MISSING",
                    priority="NORMAL",
                    completed_sections=[],
                    **common,
                )
            )
            connection.execute(
                events.insert().values(
                    id=event_id,
                    event_code="readiness.legacy_audit",
                    actor_type="USER",
                    actor_id=actor_id,
                    action="readiness.legacy_audit",
                    entity_type="participant",
                    entity_id=participant_id,
                    result="SUCCESS",
                    metadata_json={},
                    occurred_at=common["created_at"],
                )
            )
        upgraded = migrate("upgrade", "head")
        assert upgraded.returncode == 0, upgraded.stderr
        assert "hamis_id" not in {c["name"] for c in inspect(instance).get_columns("participants")}
        with Session(instance) as session:
            participant = session.get(Participant, participant_id)
            assert participant.participant_code == "HAPPY-LOCAL-TEST"
            assert participant.source_system == "INTERNAL" and participant.created_via == "STAFF"
            reference_row = session.scalar(select(ExternalReference))
            assert reference_row.entity_id == participant_id
            assert reference_row.external_system == "HAMIS"
            assert reference_row.external_id == "HAPPY-LEGACY-TEST"
            event = session.get(AuditEvent, event_id)
            assert event.actor_id == str(actor_id) and event.entity_id == participant_id
            audit(session, "readiness.test_actor", AuditActor("INTEGRATION", "HAMIS"))
            session.commit()
        refused = migrate("downgrade", "0008_supply_permissions")
        assert refused.returncode != 0
        assert "non-UUID audit actors must be preserved" in refused.stderr
        with Session(instance) as session:
            assert (
                session.scalar(
                    select(AuditEvent.actor_id).where(
                        AuditEvent.event_code == "readiness.test_actor"
                    )
                )
                == "HAMIS"
            )
            assert session.scalar(select(ExternalReference.entity_id)) == participant_id
    finally:
        instance.dispose()
        drop_test_schema(schema)

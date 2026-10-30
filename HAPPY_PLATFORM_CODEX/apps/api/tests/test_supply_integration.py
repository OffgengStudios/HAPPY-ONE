import io
import os
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, Role, User, now
from app.modules.iam.security import hasher
from app.modules.supply import files, routes, service
from app.modules.supply.models import Consent, Document, Education, Participant, Person
from app.storage.s3 import get_storage_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1",
        reason="Requires PostgreSQL and private storage.",
    ),
]
PASSWORD = "Synthetic supply password 123"


@pytest.fixture(scope="module")
def engine():
    schema, url = create_test_schema()
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        drop_test_schema(schema)


@pytest.fixture
def db(engine, monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-NOTICE")
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(
        settings, "supply_required_sections", ["basic", "contact", "consent", "review"]
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])
    try:
        yield db
    finally:
        for document in db.scalars(select(Document)):
            if document.scan_status != "REJECTED":
                get_storage_client().delete_object(
                    Bucket=settings.s3_bucket, Key=document.storage_key
                )
        app.dependency_overrides.clear()
        db.close()
        transaction.rollback()
        connection.close()


def login(db, code="SUPPLY"):
    role = db.scalar(select(Role).where(Role.code == code))
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic Supply",
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
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    client.headers.update(
        {"Origin": "http://localhost:3000", "X-CSRF-Token": client.cookies.get("happy_csrf")}
    )
    return client, user


def create(client, **extra):
    response = client.post(
        "/api/v1/participants",
        json={
            "first_name": "Synthetic",
            "surname": "Participant",
            "phone_raw": "0241234567",
            "community": "Accra",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def consent(client, row):
    response = client.post(
        "/api/v1/participants/" + row["id"] + "/consents",
        json={
            "version": row["version"],
            "consent_type": "PROGRAMME",
            "method": "STAFF_RECORDED",
            "consented_at": "2026-01-01T09:00:00Z",
            "privacy_notice_version": "SYNTHETIC-NOTICE",
            "participant_agreed": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_intake_duplicates_versions_progressive_sections_and_archive(db):
    client, user = login(db)
    row = create(client, assigned_user_id=str(user.id))
    path = "/api/v1/participants/" + row["id"]
    assert row["source_system"] == "INTERNAL" and row["created_via"] == "STAFF"
    assert row["phone_normalized"] == "+233241234567"
    assert row["id"] != row["person_id"] and row["participant_code"].startswith("HAPPY-")
    duplicate = client.post(
        "/api/v1/participants",
        json={
            "first_name": "Other",
            "surname": "Person",
            "phone_raw": "0241234567",
            "community": "Other",
        },
    )
    assert duplicate.status_code == 409
    distinct = create(client, first_name="Other", duplicate_acknowledged=True)
    assert distinct["id"] != row["id"]
    body = {
        "version": row["version"],
        "items": [{"education_level": "Secondary", "is_highest": True}],
    }
    assert client.patch(path + "/onboarding/education", json=body).status_code == 200
    assert client.patch(path + "/onboarding/education", json=body).status_code == 409
    body["version"] += 1
    body["items"][0]["education_level"] = "Tertiary"
    assert client.patch(path + "/onboarding/education", json=body).status_code == 200
    assert len(db.scalars(select(Education)).all()) == 2
    assert [
        item["education_level"] for item in client.get(path + "/onboarding").json()["education"]
    ] == ["Tertiary"]
    current = client.get(path).json()
    assert (
        client.post(
            path + "/archive", json={"version": current["version"], "reason": "Duplicate reviewed"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            path + "/onboarding/review", json={"version": current["version"] + 1, "reviewed": True}
        ).status_code
        == 409
    )
    assert len(client.get("/api/v1/participants?archived=true").json()["items"]) == 1


def test_consent_completion_withdrawal_and_policy_changes_gate_submission(db, monkeypatch):
    client, user = login(db)
    row = create(client)
    # This consent-policy fixture satisfies the separately tested Ghana Card gate.
    person = db.get(Person, UUID(row["person_id"]))
    person.government_id_type = "GHANA_CARD"
    person.government_id_ciphertext = "synthetic-protected-identity-fixture"
    db.commit()
    path = "/api/v1/participants/" + row["id"]
    assert (
        client.post(
            path + "/onboarding/complete", json={"version": 1, "completion_mode": "STAFF_ASSISTED"}
        ).status_code
        == 422
    )
    first = consent(client, row)
    row = client.get(path).json()
    second = consent(client, row)
    row = client.get(path).json()
    row = client.patch(
        path + "/onboarding/review", json={"version": row["version"], "reviewed": True}
    ).json()
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", False)
    assert (
        client.post(
            path + "/onboarding/complete",
            json={"version": row["version"], "completion_mode": "STAFF_ASSISTED"},
        ).json()["error"]["code"]
        == "ONBOARDING_POLICY_REQUIRED"
    )
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(settings, "supply_required_fields", ["date_of_birth"])
    assert client.get(path).json()["missing_fields"] == ["date_of_birth"]
    assert (
        client.post(
            path + "/onboarding/complete",
            json={"version": row["version"], "completion_mode": "STAFF_ASSISTED"},
        ).status_code
        == 422
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])
    response = client.post(
        path + "/onboarding/complete",
        json={"version": row["version"], "completion_mode": "STAFF_ASSISTED"},
    )
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["submission_eligible"] and row["assisted_by"] == str(user.id) and row["completed_at"]
    participant = db.get(Participant, UUID(row["id"]))
    service.assert_submission_eligible(db, participant)
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "NEW-SYNTHETIC-NOTICE")
    assert not client.get(path).json()["submission_eligible"]
    with pytest.raises(ApiError):
        service.assert_submission_eligible(db, participant)
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-NOTICE")
    response = client.post(
        "/consents/" + first["id"] + "/withdraw",
        json={"version": row["version"], "reason": "Synthetic withdrawal"},
    )
    # All public routes are versioned, including consent withdrawal.
    assert response.status_code == 404
    response = client.post(
        "/api/v1/consents/" + first["id"] + "/withdraw",
        json={"version": row["version"], "reason": "Synthetic withdrawal"},
    )
    assert response.status_code == 200
    assert (
        response.json()["onboarding_status"] == "BLOCKED"
        and not response.json()["submission_eligible"]
    )
    assert {grant.status for grant in db.scalars(select(Consent))} == {"WITHDRAWN"}
    assert first["id"] != second["id"]


@pytest.mark.parametrize(
    "code", ["ADMIN", "SUPPLY", "DEMAND", "MATCHING", "MERL", "MARKETING", "MANAGEMENT"]
)
def test_participant_permissions_and_sensitive_projections(db, code):
    writer, _ = login(db, "ADMIN")
    row = create(writer)
    path = "/api/v1/participants/" + row["id"]
    assert (
        writer.patch(
            path + "/sensitive",
            json={
                "version": 1,
                "disability_status": "SYNTHETIC",
                "current_income_amount": 100,
                "income_frequency": "MONTHLY",
            },
        ).status_code
        == 200
    )
    client, user = login(db, code)
    response = client.get(path)
    if response.status_code == 200:
        assert (
            not {
                "disability_status",
                "current_income_amount",
                "date_of_birth",
                "government_id_hash",
                "government_id_ciphertext",
            }
            & response.json().keys()
        )
    else:
        assert response.status_code == 403
    allowed = {p.code for role in user.roles for p in role.permissions}
    assert client.get(path + "/sensitive").status_code == (
        200 if {"participant:view", "participant_sensitive:view"} <= allowed else 403
    )
    permission = db.scalar(select(Permission).where(Permission.code == "participant:view"))
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    assert client.get(path).status_code == 403
    assert client.get(path + "/sensitive").status_code == 403
    assert (
        client.patch(path + "/onboarding/review", json={"version": 2, "reviewed": True}).status_code
        == 403
    )


def test_identity_encryption_hash_and_audit_minimization(db, monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(
        settings, "identity_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(
        settings, "identity_lookup_key", SecretStr("synthetic-lookup-secret-only-for-tests")
    )
    client, _ = login(db, "ADMIN")
    row = create(client)
    path = "/api/v1/participants/" + row["id"]
    raw = "GHA-TEST-123456"
    response = client.patch(
        path + "/identity",
        json={"version": 1, "government_id_type": "GHANA_CARD", "government_id": raw},
    )
    assert response.status_code == 200
    assert raw not in response.text and response.json()["has_government_id"]
    person = db.get(Person, UUID(row["person_id"]))
    assert raw not in person.government_id_ciphertext
    assert (
        Fernet(settings.identity_encryption_key.get_secret_value())
        .decrypt(person.government_id_ciphertext)
        .decode()
        == raw
    )
    other = create(client, phone_raw="0247654321", first_name="Different", community="Kumasi")
    assert (
        client.patch(
            "/api/v1/participants/" + other["id"] + "/identity",
            json={
                "version": 1,
                "government_id_type": "GHANA_CARD",
                "government_id": "GHA TEST 123456",
            },
        ).status_code
        == 409
    )
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == row["id"])).all()
    assert raw not in str([event.after_json for event in events])
    assert person.government_id_hash not in client.get(path).text


def test_private_cv_versions_scan_gate_approval_download_and_archive(db, monkeypatch):
    client, _ = login(db)
    row = create(client)
    path = "/api/v1/participants/" + row["id"]
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    content = output.getvalue()
    monkeypatch.setattr(settings, "file_scan_host", "")
    response = client.post(
        path + "/cv", data={"version": 1}, files={"file": ("cv.pdf", content, files.PDF)}
    )
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["scan_status"] == "SCANNING"
    assert not {"storage_key", "sha256", "scan_details"} & first.keys()
    assert client.get("/api/v1/files/" + first["id"] + "/download").status_code == 409
    assert (
        client.post("/api/v1/cv/" + first["id"] + "/approve", json={"version": 2}).status_code
        == 409
    )
    monkeypatch.setattr(files, "scan", lambda content: "AVAILABLE")
    assert (
        client.post("/api/v1/files/" + first["id"] + "/rescan", json={"version": 2}).status_code
        == 200
    )
    response = client.post("/api/v1/cv/" + first["id"] + "/approve", json={"version": 3})
    assert response.status_code == 200 and response.json()["current_cv_id"] == first["id"]
    downloaded = client.get("/api/v1/files/" + first["id"] + "/download")
    assert downloaded.status_code == 200 and downloaded.content == content
    assert downloaded.headers["cache-control"] == "no-store"
    stored = db.get(Document, UUID(first["id"]))
    storage = get_storage_client()
    storage.put_object(Bucket=settings.s3_bucket, Key=stored.storage_key, Body=b"Synthetic tamper")
    assert client.get("/api/v1/files/" + first["id"] + "/download").status_code == 503
    storage.put_object(Bucket=settings.s3_bucket, Key=stored.storage_key, Body=content)
    response = client.post(
        path + "/cv", data={"version": 4}, files={"file": ("revised.pdf", content, files.PDF)}
    )
    assert response.status_code == 201 and response.json()["version_number"] == 2
    assert client.get(path).json()["current_cv_id"] == first["id"]
    assert client.get(path).json()["cv_status"] == "READY"
    assert (
        client.post(
            "/api/v1/files/" + first["id"] + "/archive", json={"version": 5, "reason": "Superseded"}
        ).status_code
        == 200
    )
    assert client.get(path).json()["current_cv_id"] is None
    assert client.get("/api/v1/files/" + first["id"] + "/download").status_code == 409
    assert len(client.get(path + "/cv/versions").json()["items"]) == 2


def test_intake_creator_with_edit_denied_cannot_be_assigned_or_edit(db):
    client, user = login(db)
    _, eligible = login(db)
    permission = db.scalar(select(Permission).where(Permission.code == "participant:edit"))
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    owners = client.get("/api/v1/supply/owners")
    assert owners.status_code == 200
    ids = {owner["id"] for owner in owners.json()}
    assert str(user.id) not in ids and str(eligible.id) in ids
    response = client.post(
        "/api/v1/participants",
        json={
            "first_name": "Synthetic",
            "surname": "Participant",
            "phone_raw": "0241234567",
            "community": "Accra",
            "assigned_user_id": str(user.id),
        },
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_OWNER"
    assert db.scalar(select(Participant)) is None
    assert db.scalar(select(Person)) is None
    row = create(client)
    assert row["assigned_user_id"] is None
    path = "/api/v1/participants/" + row["id"]
    assert (
        client.patch(
            path,
            json={"version": row["version"], "assigned_user_id": str(user.id)},
        ).status_code
        == 403
    )
    assert client.get(path).json()["version"] == row["version"]
    assigned = create(
        client,
        phone_raw="0241234568",
        assigned_user_id=str(eligible.id),
        duplicate_acknowledged=True,
    )
    assert assigned["assigned_user_id"] == str(eligible.id)


def test_my_work_dashboard_filters_withdrawn_and_archived(db):
    client, user = login(db)
    row = create(client, assigned_user_id=str(user.id))
    path = "/api/v1/participants/" + row["id"]
    response = client.patch(
        path,
        json={
            "version": 1,
            "assigned_user_id": str(user.id),
            "priority": "URGENT",
            "next_action": "Follow up",
            "next_action_due_at": "2026-01-01T09:00:00Z",
            "reason": "Synthetic assignment",
        },
    )
    assert response.status_code == 200
    work = client.get("/api/v1/supply/my-work").json()["items"]
    assert len(work) == 1 and work[0]["recently_assigned"] and work[0]["due_state"] == "OVERDUE"
    other, _ = login(db)
    assert not other.get("/api/v1/supply/my-work").json()["items"]
    metrics = client.get("/api/v1/supply/dashboard").json()["metrics"]
    assert [item["value"] for item in metrics] == [1, 0, 0, 1]
    for metric in metrics:
        assert (
            len(client.get("/api/v1/participants", params=metric["filters"]).json()["items"])
            == metric["value"]
        )
    assert (
        client.post(
            path + "/onboarding/transition",
            json={"version": 2, "to_status": "WITHDRAWN", "reason": "Synthetic withdrawal"},
        ).status_code
        == 200
    )
    assert not client.get("/api/v1/supply/my-work").json()["items"]
    assert (
        client.post(
            path + "/readiness",
            json={
                "version": 3,
                "readiness_status": "JOB_READY",
                "availability_status": "AVAILABLE",
                "reason": "Cannot bypass withdrawal",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            path + "/archive", json={"version": 3, "reason": "Synthetic archive"}
        ).status_code
        == 200
    )
    assert all(
        item["value"] == 0 for item in client.get("/api/v1/supply/dashboard").json()["metrics"]
    )


@pytest.mark.parametrize(
    "setting,value",
    [
        ("supply_required_sections", ["unknown"]),
        ("supply_required_fields", ["government_id_ciphertext"]),
    ],
)
def test_unknown_policy_configuration_fails_closed(db, monkeypatch, setting, value):
    client, _ = login(db)
    row = create(client)
    monkeypatch.setattr(settings, setting, value)
    response = client.get("/api/v1/participants/" + row["id"])
    assert (
        response.status_code == 503
        and response.json()["error"]["code"] == "ONBOARDING_POLICY_INVALID"
    )


def test_normalized_name_location_duplicates_and_profile_edits_invalidate_review(db):
    client, _ = login(db)
    row = create(client, community="New   Accra")
    match = client.post(
        "/api/v1/participants/duplicate-check",
        json={
            "first_name": "Synthetic",
            "surname": "Participant",
            "phone_raw": "0247654321",
            "community": " new accra ",
        },
    )
    assert match.status_code == 200 and match.json()["matches"][0]["reasons"] == ["NAME_LOCATION"]
    path = "/api/v1/participants/" + row["id"]
    assert (
        client.patch(path + "/onboarding/review", json={"version": 1, "reviewed": True}).status_code
        == 200
    )
    response = client.patch(
        path + "/onboarding/training",
        json={"version": 2, "training_summary": "Staff updated profile"},
    )
    assert response.status_code == 200 and "review" not in response.json()["completed_sections"]
    client.headers.pop("X-CSRF-Token")
    assert (
        client.patch(path + "/onboarding/review", json={"version": 3, "reviewed": True}).status_code
        == 403
    )


@pytest.mark.parametrize(
    "action,status", [("approve", "AVAILABLE"), ("rescan", "SCANNING"), ("archive", "AVAILABLE")]
)
def test_document_read_is_refreshed_after_parent_lock(db, monkeypatch, action, status):
    client, user = login(db)
    row = create(client)
    document = Document(
        participant_id=UUID(row["id"]),
        document_code="DOC-SYNTHETIC",
        storage_key="tests/" + uuid4().hex,
        original_filename="synthetic.pdf",
        mime_type=files.PDF,
        size_bytes=1,
        sha256="a" * 64,
        version_number=1,
        scan_status=status,
        created_by=user.id,
    )
    db.add(document)
    db.commit()
    original_lock = service.lock

    def lock_then_archive(session, identifier, version):
        participant = original_lock(session, identifier, version)
        # Reproduce a committed newer document state while its ORM snapshot is stale.
        session.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(scan_status="ARCHIVED", archived_at=now())
            .execution_options(synchronize_session=False)
        )
        return participant

    monkeypatch.setattr(routes.s, "lock", lock_then_archive)
    path = (
        ("/api/v1/cv/" if action == "approve" else "/api/v1/files/")
        + str(document.id)
        + "/"
        + action
    )
    response = client.post(
        path,
        json={"version": 1, **({"reason": "Synthetic archive"} if action == "archive" else {})},
    )
    assert response.status_code == 409
    assert db.get(Participant, UUID(row["id"])).current_cv_id is None


def test_database_rejects_duplicate_identity_hashes(db):
    client, _ = login(db)
    first = create(client)
    second = create(client, phone_raw="0247654321", first_name="Other", community="Kumasi")
    people = [db.get(Person, UUID(row["person_id"])) for row in (first, second)]
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            for person in people:
                person.government_id_hash = "synthetic-hash"
            db.flush()

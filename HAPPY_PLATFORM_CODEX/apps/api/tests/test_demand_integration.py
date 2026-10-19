import io
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand import files as demand_files
from app.modules.demand.models import (
    Contact,
    JobDescriptionVersion,
    Partnership,
    PartnershipDocument,
    VacancyChange,
)
from app.modules.iam.actors import AuditActor
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, Role, User
from app.modules.iam.security import hasher
from app.modules.iam.service import audit
from app.modules.supply import files as supply_files
from app.storage.s3 import get_storage_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic demand password 123"
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
    original = settings.api_cors_origins
    settings.api_cors_origins = ["http://localhost:3000"]
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        settings.api_cors_origins = original
        session.close()
        transaction.rollback()
        connection.close()


def login(db, role_code="DEMAND"):
    role = db.scalar(select(Role).where(Role.code == role_code))
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic Demand",
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


def create_employer(client, **extra):
    response = client.post(
        "/api/v1/organizations",
        json={
            "name": "Synthetic Logistics",
            "organization_type": "EMPLOYER",
            "mou_required": True,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_vacancy(client, employer, **extra):
    response = client.post(
        "/api/v1/vacancies",
        json={
            "organization_id": employer["id"],
            "title": "Driver",
            "required_headcount": 4,
            "salary_min": 1500,
            "salary_max": 2000,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def move(client, path, row, target, **extra):
    response = client.post(
        path + "/transition", json={"version": row["version"], "to_status": target, **extra}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_employer_duplicates_pagination_version_archive_and_audit(db):
    client, user = login(db)
    employer = create_employer(client, relationship_owner_id=str(user.id))
    assert employer["status"] == "LEAD"
    duplicate = client.post(
        "/api/v1/organizations",
        json={
            "name": " synthetic   logistics ",
            "organization_type": "EMPLOYER",
            "mou_required": True,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "POSSIBLE_DUPLICATE"
    create_employer(client, duplicate_acknowledged=True)
    first = client.get("/api/v1/organizations?limit=1").json()
    second = client.get(
        "/api/v1/organizations", params={"limit": 1, "cursor": first["next_cursor"]}
    ).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert client.get("/api/v1/organizations?cursor=bad").status_code == 422
    path = "/api/v1/organizations/" + employer["id"]
    update = {"name": "Updated Logistics", "organization_type": "EMPLOYER", "version": 1}
    assert client.patch(path, json=update).status_code == 200
    assert client.patch(path, json=update).json()["error"]["code"] == "RECORD_VERSION_CONFLICT"
    assert client.patch(path, json={**update, "normalized_name": "tamper"}).status_code == 422
    assert (
        client.post(
            path + "/archive", json={"version": 2, "reason": "Duplicate closed"}
        ).status_code
        == 200
    )
    assert client.patch(path, json={**update, "version": 3}).status_code == 409
    assert not client.get("/api/v1/organizations?q=Updated").json()["items"]
    assert client.get("/api/v1/organizations?archived=true").json()["items"]
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == employer["id"])).all()
    assert {e.event_code for e in events} == {
        "organization.created",
        "organization.updated",
        "organization.archived",
    }
    assert events[-1].after_json["reason"] == "Duplicate closed"


def test_contact_validation_primary_constraint_and_reassignment(db):
    client, _ = login(db)
    employer = create_employer(client)
    path = "/api/v1/organizations/" + employer["id"] + "/contacts"
    body = {
        "full_name": "Synthetic Contact",
        "phone_raw": "0241234567",
        "email": "CONTACT@example.org",
        "is_primary": True,
    }
    first = client.post(path, json=body)
    assert first.status_code == 201
    contact = first.json()
    assert contact["phone_normalized"] == "+233241234567"
    assert contact["email"] == "contact@example.org"
    assert client.post(path, json=body).status_code == 409
    assert client.post(path, json={**body, "phone_raw": "123"}).status_code == 422
    assert client.post(path, json={**body, "phone_normalized": "+233000000000"}).status_code == 422
    with pytest.raises(IntegrityError, match="uq_active_primary_contact"), db.begin_nested():
        db.add(
            Contact(
                organization_id=UUID(employer["id"]),
                full_name="Second primary",
                is_primary=True,
                is_active=True,
            )
        )
        db.flush()
    edited = client.patch(
        "/api/v1/organization-contacts/" + contact["id"],
        json={**body, "version": 1, "is_active": False},
    )
    assert edited.status_code == 200
    assert client.post(path, json=body).status_code == 201


def test_partnership_full_path_and_waiver_audit(db):
    client, user = login(db)
    employer = create_employer(client)
    row = client.get("/api/v1/organizations/" + employer["id"] + "/partnership").json()
    path = "/api/v1/partnerships/" + row["id"]
    assert (
        client.post(path + "/transition", json={"version": 1, "to_status": "ACTIVE"}).status_code
        == 422
    )
    for target in ("CONTACTED", "ENGAGED", "INTERESTED", "MOU_PENDING"):
        row = move(client, path, row, target)
    assert (
        client.post(
            path + "/transition", json={"version": row["version"], "to_status": "MOU_SIGNED"}
        ).status_code
        == 409
    )
    patch = {
        "version": row["version"],
        "mou_required": True,
        "mou_sent_at": "2026-10-01T09:00:00Z",
        "mou_signed_at": "2026-10-02T09:00:00Z",
        "owner_id": str(user.id),
        "next_action": "Call employer",
        "next_action_due_at": "2026-10-03T09:00:00Z",
    }
    result = client.patch(path, json=patch)
    assert result.status_code == 200, result.text
    row = move(client, path, result.json(), "MOU_SIGNED")
    row = move(client, path, row, "ACTIVE")
    assert client.get("/api/v1/organizations/" + employer["id"]).json()["status"] == "ACTIVE"
    assert client.get("/api/v1/demand/my-work").json()["items"][0]["title"] == "Call employer"
    assert client.get("/api/v1/demand/dashboard").json()["metrics"][0]["value"] == 1
    row = move(client, path, row, "INACTIVE")
    assert (
        client.post(
            path + "/transition", json={"version": row["version"], "to_status": "ACTIVE"}
        ).status_code
        == 422
    )
    row = move(client, path, row, "ACTIVE", reason="Recruiting again")
    assert (
        client.patch(
            path, json={**patch, "version": row["version"], "mou_signed_at": None}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            path, json={**patch, "version": row["version"], "mou_required": False}
        ).status_code
        == 422
    )
    result = client.patch(
        path,
        json={
            **patch,
            "version": row["version"],
            "mou_required": False,
            "reason": "Explicit employer exemption",
        },
    )
    assert result.status_code == 200
    audit = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_code == "partnership.updated")
        .order_by(AuditEvent.occurred_at.desc())
    )
    assert audit.after_json["reason"] == "Explicit employer exemption"


def test_partnership_history_and_private_document_versions(db, monkeypatch):
    client, _ = login(db)
    employer = create_employer(client)
    collection = "/api/v1/organizations/" + employer["id"] + "/partnerships"
    created = client.post(
        "/api/v1/organizations/" + employer["id"] + "/partnership",
        json={
            "partnership_type": "TRAINING",
            "start_date": "2027-01-01",
            "end_date": "2027-12-31",
            "mou_required": False,
        },
    )
    assert created.status_code == 201, created.text
    period = created.json()
    assert period["partnership_type"] == "TRAINING"
    assert period["partnership_code"].startswith("PAR-")
    assert len(client.get(collection).json()["items"]) == 2
    assert (
        client.post(
            "/api/v1/organizations/" + employer["id"] + "/partnership",
            json={
                "partnership_type": "COMBINED",
                "start_date": "2027-03-01",
                "end_date": "2027-02-01",
                "mou_required": True,
            },
        ).status_code
        == 422
    )

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    content = output.getvalue()
    monkeypatch.setattr(settings, "file_scan_host", "")
    upload = client.post(
        f"/api/v1/partnerships/{period['id']}/documents",
        data={"version": period["version"]},
        files={"file": ("agreement.pdf", content, supply_files.PDF)},
    )
    assert upload.status_code == 201, upload.text
    agreement = upload.json()
    assert agreement["scan_status"] == "SCANNING"
    assert not {"storage_key", "sha256", "scan_details"} & agreement.keys()
    assert (
        client.get(f"/api/v1/partnership-documents/{agreement['id']}/download").status_code == 409
    )
    monkeypatch.setattr(demand_files, "scan", lambda content: "AVAILABLE")
    rescanned = client.post(
        f"/api/v1/partnership-documents/{agreement['id']}/rescan",
        json={"version": agreement["version"]},
    )
    assert rescanned.status_code == 200
    downloaded = client.get(f"/api/v1/partnership-documents/{agreement['id']}/download")
    assert downloaded.status_code == 200 and downloaded.content == content
    assert downloaded.headers["cache-control"] == "no-store"

    vacancy = create_vacancy(client, employer)
    job_path = f"/api/v1/vacancies/{vacancy['id']}/job-descriptions"
    first = client.post(
        job_path,
        data={"version": vacancy["version"]},
        files={"file": ("driver-jd.pdf", content, supply_files.PDF)},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        job_path,
        data={"version": vacancy["version"] + 1},
        files={"file": ("driver-jd-v2.pdf", content, supply_files.PDF)},
    )
    assert second.status_code == 201, second.text
    assert sorted(item["version_number"] for item in client.get(job_path).json()["items"]) == [1, 2]
    assert client.get(f"/api/v1/job-descriptions/{second.json()['id']}/download").content == content

    restricted, _ = login(db, "MARKETING")
    assert restricted.get(collection).status_code == 403
    assert restricted.get(job_path).status_code == 403

    storage = get_storage_client()
    for document in db.scalars(select(PartnershipDocument)).all():
        storage.delete_object(Bucket=settings.s3_bucket, Key=document.storage_key)
    for document in db.scalars(select(JobDescriptionVersion)).all():
        storage.delete_object(Bucket=settings.s3_bucket, Key=document.storage_key)


def test_vacancy_lifecycle_requirement_history_and_headcount(db):
    client, _ = login(db)
    employer = create_employer(client)
    vacancy = create_vacancy(client, employer)
    path = "/api/v1/vacancies/" + vacancy["id"]
    assert (
        client.post(path + "/transition", json={"version": 1, "to_status": "ACTIVE"}).status_code
        == 422
    )
    requirement = {
        "version": 1,
        "criterion_type": "SKILL",
        "criterion_key": "manual_driving",
        "operator": "EQ",
        "value_json": True,
        "display_order": 0,
        "reason": "Employer request",
    }
    result = client.post(path + "/requirements", json=requirement)
    assert result.status_code == 201, result.text
    req = result.json()
    vacancy = client.get(path).json()
    assert vacancy["version"] == 2
    assert client.post(path + "/requirements", json=requirement).status_code == 409
    result = client.patch(
        "/api/v1/vacancy-requirements/" + req["id"],
        json={**requirement, "version": 2, "value_json": False},
    )
    assert result.status_code == 200, result.text
    result = client.post(
        "/api/v1/vacancy-requirements/" + req["id"] + "/archive",
        json={"version": 3, "reason": "Removed by employer"},
    )
    assert result.status_code == 200
    assert not client.get(path + "/requirements").json()["items"]
    vacancy = client.get(path).json()
    vacancy = move(client, path, vacancy, "PENDING_CONFIRMATION")
    vacancy = move(client, path, vacancy, "ACTIVE")
    assert vacancy["opened_at"]
    assert client.get(path + "/headcount").json() == {
        "required": 4,
        "started": 0,
        "confirmed_placements": 0,
        "outstanding": 4,
    }
    assert (
        client.post(
            path + "/transition",
            json={"version": vacancy["version"], "to_status": "PARTIALLY_FILLED"},
        ).status_code
        == 409
    )
    patch = {
        "version": vacancy["version"],
        "title": "Driver",
        "required_headcount": 6,
        "salary_min": 1800,
        "salary_max": 2400,
        "reason": "Revised demand",
    }
    result = client.patch(path, json=patch)
    assert result.status_code == 200, result.text
    vacancy = result.json()
    history = client.get(path + "/changes").json()["items"]
    fields = {row["field_name"] for row in history}
    assert {"required_headcount", "salary_min", "salary_max"} <= fields
    dashboard = client.get("/api/v1/demand/dashboard").json()["metrics"]
    assert dashboard[2]["value"] == dashboard[3]["value"] == 6
    assert (
        client.post(
            path + "/close", json={"version": vacancy["version"], "to_status": "CLOSED"}
        ).status_code
        == 422
    )
    vacancy = move(client, path, vacancy, "CLOSED", closure_reason="EMPLOYER_CANCELLED")
    assert vacancy["closed_at"]
    assert client.get("/api/v1/demand/dashboard").json()["metrics"][2]["value"] == 0
    assert (
        client.post(
            "/api/v1/organizations/" + employer["id"] + "/archive",
            json={"version": 1, "reason": "Employer closed"},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "code", ["ADMIN", "DEMAND", "SUPPLY", "MATCHING", "MERL", "MARKETING", "MANAGEMENT"]
)
def test_role_projections_and_permission_denial(db, code):
    writer, _ = login(db)
    employer = create_employer(writer)
    vacancy = create_vacancy(writer, employer)
    client, user = login(db, code)
    assert client.get("/api/v1/vacancies/" + vacancy["id"]).status_code == 200
    org_expected = 403 if code in {"SUPPLY", "MARKETING"} else 200
    assert client.get("/api/v1/organizations/" + employer["id"]).status_code == org_expected
    private_expected = 200 if code in {"ADMIN", "DEMAND"} else 403
    assert (
        client.get("/api/v1/organizations/" + employer["id"] + "/contacts").status_code
        == private_expected
    )
    assert client.get("/api/v1/demand/dashboard").status_code == private_expected
    assert "phone_raw" not in client.get("/api/v1/vacancies/" + vacancy["id"]).text
    created = client.post(
        "/api/v1/vacancies",
        json={
            "organization_id": employer["id"],
            "title": "Role-scoped vacancy",
            "required_headcount": 2,
        },
    )
    assert created.status_code == (201 if code in {"ADMIN", "DEMAND", "MATCHING"} else 403)
    permission = db.scalar(select(Permission).where(Permission.code == "vacancy:view"))
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    assert client.get("/api/v1/vacancies/" + vacancy["id"]).status_code == 403
    assert (
        client.patch(
            "/api/v1/vacancies/" + vacancy["id"],
            json={
                "version": vacancy["version"],
                "title": "Blocked edit",
                "required_headcount": 2,
                "reason": "Read denial must not be bypassed by mutation responses",
            },
        ).status_code
        == 403
    )


def test_my_work_owner_filter_csrf_archive_guard_and_validation(db):
    client, user = login(db)
    other, _ = login(db)
    employer = create_employer(client, relationship_owner_id=str(user.id))
    create_vacancy(client, employer)
    partner = client.get("/api/v1/organizations/" + employer["id"] + "/partnership").json()
    response = client.patch(
        "/api/v1/partnerships/" + partner["id"],
        json={
            "version": 1,
            "mou_required": True,
            "owner_id": str(user.id),
            "next_action": "Follow up",
            "next_action_due_at": "2026-10-01T08:00:00Z",
        },
    )
    assert response.status_code == 200
    assert len(client.get("/api/v1/demand/my-work").json()["items"]) == 1
    assert not other.get("/api/v1/demand/my-work").json()["items"]
    assert (
        client.post(
            "/api/v1/organizations/" + employer["id"] + "/archive",
            json={"version": 1, "reason": "Closing"},
        ).status_code
        == 409
    )


def test_input_validation_and_csrf_requirements(db):
    client, _ = login(db)
    employer = create_employer(client)
    vacancy = create_vacancy(client, employer)
    assert (
        client.post(
            "/api/v1/vacancies",
            json={
                "title": "Test",
                "organization_id": employer["id"],
                "required_headcount": 0,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/vacancies",
            json={
                "title": "Test",
                "organization_id": employer["id"],
                "required_headcount": 1,
                "status": "ACTIVE",
            },
        ).status_code
        == 422
    )
    assert (
        client.get("/api/v1/vacancies?organization_id=" + employer["id"]).json()["items"][0]["id"]
        == vacancy["id"]
    )
    del client.headers["X-CSRF-Token"]
    assert (
        client.post(
            "/api/v1/organizations",
            json={
                "name": "Denied",
                "organization_type": "EMPLOYER",
                "mou_required": True,
            },
        ).status_code
        == 403
    )


def test_reference_options_priority_and_safe_activity_pagination(db):
    client, user = login(db)
    employer = create_employer(client, relationship_owner_id=str(user.id))
    partner = client.get("/api/v1/organizations/" + employer["id"] + "/partnership").json()
    assert partner["owner_assigned_at"]
    patch = {
        "version": 1,
        "mou_required": True,
        "owner_id": str(user.id),
        "next_action": "Urgent employer follow-up",
        "priority": "URGENT",
    }
    response = client.patch("/api/v1/partnerships/" + partner["id"], json=patch)
    assert response.status_code == 200
    work = client.get("/api/v1/demand/my-work").json()["items"][0]
    assert work["priority"] == "URGENT" and work["recently_assigned"]
    assert work["owner_name"] == user.full_name
    assert work["assigned_at"] == partner["owner_assigned_at"]
    refs = client.get("/api/v1/demand/reference-data").json()
    assert {item["value"] for item in refs["priority"]} == {"NORMAL", "HIGH", "URGENT"}
    assert "EMPLOYER_CANCELLED" in {item["value"] for item in refs["closure_reason"]}
    path = "/api/v1/organizations/" + employer["id"] + "/activity"
    first = client.get(path, params={"limit": 1}).json()
    second = client.get(path, params={"limit": 1, "cursor": first["next_cursor"]}).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert {first["items"][0]["event_code"], second["items"][0]["event_code"]} == {
        "organization.created",
        "partnership.updated",
    }
    assert employer["id"] in {
        row["id"] for row in client.get("/api/v1/organizations?pipeline_only=true").json()["items"]
    }


@pytest.mark.parametrize(
    "contact_access,partnership_access",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_organization_activity_filters_related_events_before_pagination(
    db, contact_access, partnership_access
):
    writer, _ = login(db)
    employer = create_employer(writer)
    path = "/api/v1/organizations/" + employer["id"]
    assert (
        writer.post(path + "/contacts", json={"full_name": "Synthetic Contact"}).status_code == 201
    )
    partner = writer.get(path + "/partnership").json()
    assert (
        writer.patch(
            "/api/v1/partnerships/" + partner["id"],
            json={"version": 1, "mou_required": True, "next_action": "Restricted follow-up"},
        ).status_code
        == 200
    )
    reader, user = login(db)
    for code, allowed in [
        ("organization_contact:view", contact_access),
        ("partnership:view", partnership_access),
    ]:
        if not allowed:
            permission = db.scalar(select(Permission).where(Permission.code == code))
            db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    assert reader.get(path + "/contacts").status_code == (200 if contact_access else 403)
    assert reader.get(path + "/partnership").status_code == (200 if partnership_access else 403)
    expected = {"organization.created"}
    if contact_access:
        expected.add("organization_contact.created")
    if partnership_access:
        expected.add("partnership.updated")
    events = []
    params = {"limit": 1}
    while True:
        response = reader.get(path + "/activity", params=params)
        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) == 1
        events.extend(page["items"])
        if not page["next_cursor"]:
            break
        params["cursor"] = page["next_cursor"]
        assert len(events) <= len(expected)
    assert {item["event_code"] for item in events} == expected
    assert len(events) == len(expected)
    permission = db.scalar(select(Permission).where(Permission.code == "organization:view"))
    db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
    db.commit()
    db.expire_all()
    assert reader.get(path + "/activity").status_code == 403


@pytest.mark.parametrize("entity", ["organizations", "vacancies"])
def test_activity_preserves_user_and_non_user_actor_types(db, entity):
    client, user = login(db)
    employer = create_employer(client)
    record = employer if entity == "organizations" else create_vacancy(client, employer)
    identifier = UUID(record["id"])
    audit(db, "synthetic.system", AuditActor("SYSTEM"), entity, identifier)
    audit(
        db, "synthetic.integration", AuditActor("INTEGRATION", "TEST_ADAPTER"), entity, identifier
    )
    db.commit()
    response = client.get("/api/v1/" + entity + "/" + record["id"] + "/activity")
    assert response.status_code == 200
    events = {item["event_code"]: item for item in response.json()["items"]}
    created = events["organization.created" if entity == "organizations" else "vacancy.created"]
    assert (created["actor_type"], created["actor_id"]) == ("USER", str(user.id))
    system = events["synthetic.system"]
    assert (system["actor_type"], system["actor_id"]) == ("SYSTEM", None)
    integration = events["synthetic.integration"]
    assert (integration["actor_type"], integration["actor_id"]) == ("INTEGRATION", "TEST_ADAPTER")


def test_vacancy_history_is_append_only_and_catalogued_events_are_emitted(db):
    client, _ = login(db)
    employer = create_employer(client)
    row = create_vacancy(client, employer)
    path = "/api/v1/vacancies/" + row["id"]
    result = client.patch(
        path,
        json={
            "version": 1,
            "title": "Revised role",
            "required_headcount": 5,
            "reason": "Employer revision",
        },
    )
    assert result.status_code == 200
    changed_row = db.scalar(
        select(VacancyChange).where(VacancyChange.vacancy_id == UUID(row["id"]))
    )
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(
            update(VacancyChange)
            .where(VacancyChange.id == changed_row.id)
            .values(reason="Tampered")
        )
    updated = result.json()
    move(client, path, updated, "CANCELLED", closure_reason="EMPLOYER_CANCELLED")
    codes = {item["event_code"] for item in client.get(path + "/activity").json()["items"]}
    assert {
        "vacancy.created",
        "vacancy.updated_material",
        "vacancy.closed",
        "vacancy.status_changed",
    } <= codes


def test_optional_mou_skip_and_signed_date_database_guard(db):
    client, _ = login(db)
    employer = create_employer(client, mou_required=False)
    row = client.get("/api/v1/organizations/" + employer["id"] + "/partnership").json()
    with pytest.raises(IntegrityError, match="ck_partnership_signed_date"), db.begin_nested():
        db.execute(
            update(Partnership)
            .where(Partnership.id == UUID(row["id"]))
            .values(
                status="MOU_SIGNED",
                mou_signed_at=None,
            )
        )
    path = "/api/v1/partnerships/" + row["id"]
    for target in ("CONTACTED", "ENGAGED", "INTERESTED", "ACTIVE"):
        row = move(client, path, row, target)
    assert row["status"] == "ACTIVE" and row["mou_signed_at"] is None
    audit_event = db.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.entity_id == UUID(row["id"]),
            AuditEvent.event_code == "partnership.status_changed",
        )
        .order_by(AuditEvent.occurred_at.desc())
    )
    assert audit_event.after_json["from_status"] == "INTERESTED"
    assert audit_event.after_json["to_status"] == "ACTIVE"


def test_concurrent_material_edits_have_one_winner(engine):
    from concurrent.futures import ThreadPoolExecutor

    original_origins = settings.api_cors_origins
    settings.api_cors_origins = ["http://localhost:3000"]

    def request_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = request_db
    try:
        with Session(engine, expire_on_commit=False) as seed:
            first, user = login(seed)
            second = TestClient(app)
            response = second.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": PASSWORD},
                headers=ORIGIN,
            )
            assert response.status_code == 200
            second.headers.update({**ORIGIN, "X-CSRF-Token": second.cookies.get("happy_csrf")})
            employer = create_employer(first, name="Concurrent Employer")
            row = create_vacancy(first, employer)

        def save(client):
            return client.patch(
                "/api/v1/vacancies/" + row["id"],
                json={
                    "version": 1,
                    "title": "Concurrent edit",
                    "required_headcount": 8,
                    "reason": "Simultaneous staff edit",
                },
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(save, (first, second)))
        assert statuses == [200, 409]
        assert first.get("/api/v1/vacancies/" + row["id"]).json()["version"] == 2
    finally:
        app.dependency_overrides.clear()
        settings.api_cors_origins = original_origins

import os
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
from app.integrations.employer_portal.models import EmployerSubmission
from app.main import app
from app.modules.demand.models import Contact, Organization, Partnership, Requirement, Vacancy
from app.modules.external_references.models import ExternalReference
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
TOKEN = "employer-portal-test-token-over-thirty-two-characters"
PASSWORD = "Synthetic Portal password 123"
ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture(scope="module")
def engine():
    schema, url = create_test_schema()
    instance = create_engine(url)
    old_token = settings.employer_portal_integration_token
    old_key = settings.identity_encryption_key
    settings.employer_portal_integration_token = SecretStr(TOKEN)
    settings.identity_encryption_key = SecretStr(Fernet.generate_key().decode())
    try:
        yield instance
    finally:
        settings.employer_portal_integration_token = old_token
        settings.identity_encryption_key = old_key
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


def payload(identifier: str = "PS-PORTAL001", company: str = "Portal Foods Ltd") -> dict:
    return {
        "submissionId": identifier,
        "referenceNumber": "HP-EMP-2026-00001",
        "companyName": company,
        "sector": "AGRICULTURE",
        "companySize": "51-200",
        "region": "GREATER_ACCRA",
        "city": "Accra",
        "contactName": "Kwame Owusu",
        "contactRole": "HR Manager",
        "contactPhone": "0241234567",
        "contactEmail": "hr@portal-foods.example",
        "consentAgreement": True,
        "consentContact": True,
        "signatureFileId": "drive-signature-001",
        "documentIds": ["PD-001"],
        "vacancies": [
            {
                "vacancyId": "PV-001",
                "jobTitle": "Warehouse Assistant",
                "location": "Tema",
                "employmentType": "FULL_TIME",
                "openings": 4,
                "description": "Support warehouse operations.",
            },
            {
                "vacancyId": "PV-002",
                "jobTitle": "Sales Associate",
                "location": "Accra",
                "employmentType": "FULL_TIME",
                "openings": 2,
            },
        ],
    }


def test_auth_idempotency_encryption_and_conversion(db: Session) -> None:
    path = "/api/v1/integrations/employer-portal/submissions"
    assert TestClient(app).post(path, json=payload()).status_code == 401

    source = payload()
    received = machine().post(path, json=source)
    assert received.status_code == 202
    result = received.json()
    assert result["status"] == "NEW"
    row = db.get(EmployerSubmission, result["id"])
    assert row
    assert source["contactEmail"] not in row.payload_ciphertext
    assert source["contactPhone"] not in row.payload_ciphertext

    replay = machine().post(path, json=source)
    assert replay.status_code == 202
    assert replay.json()["replayed"] is True
    conflict = machine().post(path, json=source | {"city": "Tema"})
    assert conflict.status_code == 409

    demand = login(db, "DEMAND")
    detail = demand.get(f"{path}/{row.id}")
    assert detail.status_code == 200
    assert detail.json()["submission"]["contact_email"] == source["contactEmail"]
    converted = demand.post(
        f"{path}/{row.id}/convert",
        json={"version": row.version, "mou_required": True, "reason": "Reviewed by Demand"},
    )
    assert converted.status_code == 200
    assert converted.json()["status"] == "CONVERTED"

    organization_id = converted.json()["organization_id"]
    organization = db.get(Organization, organization_id)
    assert organization
    assert organization.source_system == "EMPLOYER_PORTAL"
    assert organization.created_via == "INTEGRATION"
    assert (
        db.scalar(
            select(func.count())
            .select_from(Contact)
            .where(Contact.organization_id == organization.id)
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(Partnership)
            .where(Partnership.organization_id == organization.id)
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(Vacancy)
            .where(Vacancy.organization_id == organization.id)
        )
        == 2
    )
    assert db.scalar(select(func.count()).select_from(Requirement)) == 2
    assert set(
        db.scalars(select(Vacancy.status).where(Vacancy.organization_id == organization.id))
    ) == {"DRAFT"}
    reference = db.scalar(
        select(ExternalReference).where(
            ExternalReference.external_system == "EMPLOYER_PORTAL",
            ExternalReference.external_id == source["submissionId"],
        )
    )
    assert reference and reference.entity_id == organization.id
    event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "employer_portal.submission_received",
            AuditEvent.actor_type == "INTEGRATION",
            AuditEvent.actor_id == "EMPLOYER_PORTAL",
        )
    )
    assert event


def test_duplicate_requires_existing_organization_selection(db: Session) -> None:
    demand = login(db, "DEMAND")
    existing = Organization(
        organization_code="EMP-EXISTING",
        name="Existing Employer Ltd",
        normalized_name="existing employer ltd",
        organization_type="EMPLOYER",
    )
    db.add(existing)
    db.commit()
    path = "/api/v1/integrations/employer-portal/submissions"
    received = machine().post(path, json=payload("PS-DUPLICATE", existing.name))
    assert received.status_code == 202
    identifier = received.json()["id"]
    rejected = demand.post(
        f"{path}/{identifier}/convert",
        json={"version": 1, "reason": "Initial review", "mou_required": True},
    )
    assert rejected.status_code == 409
    row = db.get(EmployerSubmission, identifier)
    assert row and row.status == "NEEDS_REVIEW"

    converted = demand.post(
        f"{path}/{identifier}/convert",
        json={
            "version": row.version,
            "existing_organization_id": str(existing.id),
            "reason": "Linked to reviewed employer",
            "mou_required": True,
        },
    )
    assert converted.status_code == 200
    assert converted.json()["organization_id"] == str(existing.id)
    assert db.scalar(select(func.count()).select_from(Organization)) == 1


def test_non_demand_user_cannot_read_submission(db: Session) -> None:
    response = machine().post(
        "/api/v1/integrations/employer-portal/submissions",
        json=payload("PS-NO-ACCESS", "Restricted Employer"),
    )
    assert response.status_code == 202
    supply = login(db, "SUPPLY")
    assert supply.get("/api/v1/integrations/employer-portal/submissions").status_code == 403

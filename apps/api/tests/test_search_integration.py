import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Contact, Organization, Vacancy
from app.modules.iam.catalog import ROLE_GRANTS
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, Role, User, now
from app.modules.iam.security import hasher
from app.modules.marketing.models import Campaign
from app.modules.supply.models import Participant, Person, SensitiveProfile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]
PASSWORD = "Synthetic search password 123"
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
    monkeypatch.setattr(settings, "api_cors_origins", [ORIGIN["Origin"]])
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()


def login(db, code="ADMIN", denied=None):
    role = db.scalar(select(Role).where(Role.code == code))
    user = User(
        email=uuid4().hex + "@example.org",
        full_name="Synthetic Search",
        password_hash=hasher.hash(PASSWORD),
        roles=[role],
        primary_role_id=role.id,
    )
    if denied:
        permission = db.scalar(select(Permission).where(Permission.code == denied))
        user.overrides.append(PermissionOverride(permission_id=permission.id, effect="DENY"))
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
    return client


def records(db, count=3):
    organization = Organization(
        name="Lookup Employer",
        normalized_name="lookup employer",
        organization_code="EMP-LOOKUP",
        organization_type="EMPLOYER",
        community="Accra",
    )
    db.add(organization)
    db.flush()
    vacancy = Vacancy(
        title="Lookup Vacancy",
        vacancy_code="VAC-LOOKUP",
        organization_id=organization.id,
        required_headcount=2,
    )
    db.add(vacancy)
    db.add(
        Campaign(
            campaign_code="CMP-LOOKUP",
            title="Lookup Campaign",
            campaign_type="RECRUITMENT",
            audience="Lookup audience",
        )
    )
    db.add(
        Contact(
            organization_id=organization.id,
            full_name="Private contact",
            email="private-contact@example.org",
            phone_raw="0247777777",
        )
    )
    participants = []
    for index in range(count):
        person = Person(
            first_name="Lookup",
            surname=f"Person {index}",
            normalized_name=f"lookup person {index}",
            phone_raw=f"024123456{index}",
            phone_normalized=f"+23324123456{index}",
            community="Accra",
            email=f"private-person-{index}@example.org",
            government_id_ciphertext="PRIVATE-IDENTITY",
        )
        db.add(person)
        db.flush()
        participant = Participant(person_id=person.id, participant_code=f"HAPPY-LOOKUP-{index}")
        db.add(participant)
        db.flush()
        db.add(
            SensitiveProfile(
                participant_id=participant.id,
                disability_specify="PRIVATE-DISABILITY",
                current_income_amount=9999,
            )
        )
        participants.append(participant)
    db.commit()
    return organization, vacancy, participants


@pytest.mark.parametrize("code", list(ROLE_GRANTS))
def test_search_projects_each_role_permissions_without_sensitive_fields(db, code):
    records(db)
    client = login(db, code)
    response = client.post("/api/v1/search", json={"q": "Lookup"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    groups = response.json()["groups"]
    expected = {
        entity
        for entity, permission in {
            "PARTICIPANT": "participant:view",
            "ORGANIZATION": "organization:view",
            "VACANCY": "vacancy:view",
            "PLACEMENT": "placement:view",
            "CAMPAIGN": "campaign:view",
        }.items()
        if permission in ROLE_GRANTS[code]
    }
    assert set(groups) == expected
    for entity, page in groups.items():
        assert page["items"] or entity == "PLACEMENT"
        if not page["items"]:
            continue
        assert set(page["items"][0]) == {"entity_type", "id", "code", "label", "context"}
        assert all(item["entity_type"] == entity for item in page["items"])
    for private in (
        "PRIVATE-IDENTITY",
        "PRIVATE-DISABILITY",
        "private-contact",
        "private-person",
        "9999",
        "024123456",
    ):
        assert private not in response.text


def test_explicit_deny_and_requested_groups_cannot_bypass_authorization(db):
    records(db)
    client = login(db, denied="participant:view")
    assert "PARTICIPANT" not in client.post("/api/v1/search", json={"q": "Lookup"}).json()["groups"]
    assert (
        client.post("/api/v1/search", json={"q": "Lookup", "entities": ["PARTICIPANT"]}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/search", json={"q": "Lookup", "cursors": {"PARTICIPANT": "ignored"}}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/search", json={"q": "Lookup", "permissions": ["participant:view"]}
        ).status_code
        == 422
    )


def test_authentication_origin_and_csrf_are_required(db):
    assert TestClient(app).post("/api/v1/search", json={"q": "Lookup"}).status_code == 401
    client = login(db)
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/search", json={"q": "Lookup"}).status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies.get("happy_csrf")
    client.headers["Origin"] = "https://untrusted.example.org"
    assert client.post("/api/v1/search", json={"q": "Lookup"}).status_code == 403


def test_group_cursor_pagination_is_bounded_and_does_not_repeat_rows(db):
    _, _, rows = records(db, 8)
    client = login(db)
    ids = []
    cursor = None
    while True:
        response = client.post(
            "/api/v1/search",
            json={
                "q": "Lookup",
                "limit": 2,
                "entities": ["PARTICIPANT"],
                "cursors": {"PARTICIPANT": cursor} if cursor else {},
            },
        )
        assert response.status_code == 200
        groups = response.json()["groups"]
        assert set(groups) == {"PARTICIPANT"}
        page = groups["PARTICIPANT"]
        assert len(page["items"]) <= 2
        ids.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(ids) == len(set(ids)) == 8
    assert set(ids) == {str(row.id) for row in rows}
    invalid = client.post(
        "/api/v1/search", json={"q": "Lookup", "cursors": {"PARTICIPANT": "not-a-cursor"}}
    )
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "INVALID_CURSOR"


def test_archived_records_and_private_fields_are_not_searchable(db):
    organization, vacancy, rows = records(db)
    organization.archived_at = now()
    vacancy.archived_at = now()
    rows[0].archived_at = now()
    db.commit()
    client = login(db)
    groups = client.post("/api/v1/search", json={"q": "Lookup"}).json()["groups"]
    assert not groups["ORGANIZATION"]["items"] and not groups["VACANCY"]["items"]
    assert len(groups["PARTICIPANT"]["items"]) == 2
    for query in ("PRIVATE-IDENTITY", "PRIVATE-DISABILITY", "private-person", "private-contact"):
        response = client.post("/api/v1/search", json={"q": query})
        assert not any(page["items"] for page in response.json()["groups"].values())


def test_like_patterns_are_literals_and_public_codes_and_phones_are_searchable(db):
    _, _, rows = records(db)
    client = login(db)
    for query in ("%_", "\\\\", "';--"):
        response = client.post("/api/v1/search", json={"q": query})
        assert response.status_code == 200
        assert not any(page["items"] for page in response.json()["groups"].values())
    for query in ("HAPPY-LOOKUP-0", "+233241234560", "0241234560", "LOOKUP PERSON 0"):
        page = client.post("/api/v1/search", json={"q": query}).json()["groups"]["PARTICIPANT"]
        assert [item["id"] for item in page["items"]] == [str(rows[0].id)]


def test_query_count_is_constant_and_search_text_is_not_audited(db):
    records(db, 8)
    client = login(db)
    before = db.scalar(select(func.count(AuditEvent.id)))
    statements = []

    def collect(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", collect)
    try:
        assert client.post("/api/v1/search", json={"q": "Lookup", "limit": 100}).status_code == 200
    finally:
        event.remove(bind, "before_cursor_execute", collect)
    domain = [
        query
        for query in statements
        if any(
            "FROM " + table in query
            for table in ("participants", "people", "organizations", "vacancies")
        )
    ]
    assert len(domain) == 4
    assert not any(
        "government_id_ciphertext" in query
        or "participant_sensitive_profiles" in query
        or "organization_contacts" in query
        for query in domain
    )
    assert db.scalar(select(func.count(AuditEvent.id))) == before

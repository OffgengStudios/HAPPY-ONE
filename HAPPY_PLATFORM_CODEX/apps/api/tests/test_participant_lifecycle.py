import io
import os
from datetime import date
from uuid import UUID
from xml.etree.ElementTree import fromstring
from zipfile import ZipFile

import pytest
import test_supply_integration as supply_tests
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_supply_integration import consent, create, login

from app.core.config import settings
from app.modules.merl.models import Outcome
from app.modules.reporting import programme
from app.modules.supply.ages import event_age
from app.modules.supply.models import Participant, SensitiveProfile


@pytest.mark.parametrize(
    "birth,reference,expected",
    [
        (date(2000, 6, 14), date(2026, 6, 13), 25),
        (date(2000, 6, 14), date(2026, 6, 14), 26),
        (date(2000, 2, 29), date(2025, 2, 28), 24),
        (date(2000, 2, 29), date(2025, 3, 1), 25),
        (None, date(2026, 1, 1), None),
        (date(2000, 1, 1), None, None),
        (date(2000, 1, 1), date(1999, 1, 1), None),
    ],
)
def test_calendar_age(birth, reference, expected):
    assert event_age(birth, reference) == expected


def test_income_availability_preserves_zero_and_unknown():
    assert programme.monthly(0, "MONTHLY", status="KNOWN") == 0
    assert programme.monthly(None, None, status="UNKNOWN") == "Unknown"
    assert programme.monthly(None, None, status="NOT_APPLICABLE") == "Not applicable"
    assert programme.monthly(None, None, status="NOT_RECORDED") is None
    assert programme.monthly(100, "WEEKLY") is None


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Local PostgreSQL required"
)
def test_ids_baseline_events_outcomes_reports_and_permissions(lifecycle_db, monkeypatch):
    db = lifecycle_db
    # Settings SecretStr fields retain their runtime type when patched.
    from pydantic import SecretStr

    monkeypatch.setattr(
        settings, "identity_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "identity_lookup_key", SecretStr("synthetic-lifecycle-key-" * 3))
    client, _ = login(db, "ADMIN")
    row = create(client, onboarding_date="2026-01-02", support_type="Individual")
    path = "/api/v1/participants/" + row["id"]

    def current():
        return client.get(path).json()

    def patch(suffix, **values):
        response = client.patch(path + suffix, json={"version": current()["version"], **values})
        assert response.status_code == 200, response.text
        return response.json()

    patch("/onboarding/demographics", date_of_birth="2000-06-14", sex="Female")
    patch("/identity", government_id_type="VOTER_ID", government_id="SYNTHETIC-VOTER-001")
    assert "ghana_card" in current()["missing_fields"]
    patch("/identity", government_id_type="GHANA_CARD", government_id="SYNTHETIC-GHANA-001")
    restricted = client.get(path + "/sensitive").json()
    assert restricted["has_voter_id"] and restricted["has_ghana_card"]
    assert restricted["age_at_onboarding"] == 25
    assert "SYNTHETIC-GHANA-001" not in str(restricted)
    patch("/onboarding/employment", employment_status="NO", current_occupation="Student")
    patch("/sensitive", current_income_amount=0, income_frequency="MONTHLY")
    consent(client, current())
    patch("/onboarding/review", reviewed=True)
    response = client.post(
        path + "/onboarding/complete",
        json={"version": current()["version"], "completion_mode": "STAFF_ASSISTED"},
    )
    assert response.status_code == 200, response.text
    baseline = db.scalar(
        select(SensitiveProfile).where(SensitiveProfile.participant_id == UUID(row["id"]))
    )
    assert baseline.baseline_income_amount == 0
    assert baseline.baseline_captured_at
    patch("/sensitive", current_income_amount=2000, income_frequency="MONTHLY")
    assert baseline.baseline_income_amount == 0
    for start in ["2026-06-13", "2026-06-14"]:
        training = client.post(
            "/api/v1/trainings",
            json={
                "title": "Synthetic lifecycle course",
                "training_type": "SOFT_SKILLS",
                "trainer_type": "INTERNAL",
                "mode": "IN_PERSON",
                "start_date": start,
                "modules_json": ["Soft Skills", "IT Skills"],
            },
        ).json()
        response = client.post(
            f"/api/v1/trainings/{training['id']}/participants",
            json={"participant_ids": [row["id"]]},
        )
        assert response.status_code == 201, response.text
        attendance = response.json()["items"][0]
        response = client.patch(
            f"/api/v1/training-attendance/{attendance['id']}",
            json={
                "version": attendance["version"],
                "attendance_status": "PRESENT",
                "completion_status": "COMPLETED",
                "received_modules": ["Soft Skills"],
                "completed_modules": ["Soft Skills"],
            },
        )
        assert response.status_code == 200, response.text
    history = client.get(path + "/capacity-building").json()["items"]
    assert sorted(item["age_at_training_start"] for item in history) == [25, 26]
    assert all(item["completed_modules"] == ["Soft Skills"] for item in history)
    response = client.post(
        path + "/employment-outcomes",
        json={
            "employment_start_date": "2026-07-01",
            "as_of_date": "2026-08-01",
            "currently_working": True,
            "employment_type": "SELF",
            "employment_category": "NEW",
            "current_role": "Synthetic business owner",
            "current_income_amount": 1500,
            "income_frequency": "MONTHLY",
            "verification_notes": "Synthetic verification only",
        },
    )
    assert response.status_code == 201, response.text
    outcome = db.get(Outcome, UUID(response.json()["id"]))
    assert outcome.placement_id is None
    assert db.get(Participant, UUID(row["id"])).baseline_employment_status == "NO"
    report = programme.build(db, date(2026, 1, 1), date(2026, 12, 31), True)
    assert report["counts"]["distinct_participants"] == 1
    assert report["counts"]["training_enrolments"] == 2
    assert report["counts"]["placement_records"] == 0
    assert all(
        values[19] == "Yes" and values[20] == "Soft Skills" and values[21] is None
        for values in report["sheets"]["2. Capacity Building"]
    )
    for name, rows in report["sheets"].items():
        assert all(len(values) == len(programme.HEADERS[name]) for values in rows)
    exported = programme.workbook(report)
    with ZipFile(io.BytesIO(exported)) as archive:
        for name in archive.namelist():
            fromstring(archive.read(name))
        assert b"SYNTHETIC-GHANA-001" not in archive.read("xl/worksheets/sheet1.xml")
    export_path = "/api/v1/reports/programme/export?date_from=2026-01-01&date_to=2026-12-31"
    assert client.get(export_path + "&include_identity_numbers=true").status_code == 422
    assert client.get(export_path + "&include_sensitive=true").status_code == 422
    full = client.get(
        export_path
        + "&include_sensitive=true&privacy_acknowledged=true&include_identity_numbers=true"
    )
    assert full.status_code == 200
    with ZipFile(io.BytesIO(full.content)) as archive:
        assert b"SYNTHETIC-GHANA-001" in archive.read("xl/worksheets/sheet1.xml")
        assert b"SYNTHETIC-VOTER-001" in archive.read("xl/worksheets/sheet1.xml")
    limited, _ = login(db, "SUPPLY")
    assert limited.get(path + "/sensitive").status_code == 403
    limited_history = limited.get(path + "/capacity-building")
    assert limited_history.status_code == 200
    assert all(item["age_at_training_start"] is None for item in limited_history.json()["items"])
    assert (
        limited.post(
            path + "/employment-outcomes",
            json={
                "as_of_date": "2026-08-01",
                "currently_working": True,
                "verification_notes": "Synthetic",
            },
        ).status_code
        == 403
    )
    assert (
        limited.get(
            "/api/v1/reports/programme/export?date_from=2026-01-01&date_to=2026-12-31"
        ).status_code
        == 403
    )


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Local PostgreSQL required"
)
def test_date_and_conditional_validation(lifecycle_db):
    db = lifecycle_db
    client, _ = login(db, "ADMIN")
    row = create(client, onboarding_date="1999-01-01")
    path = "/api/v1/participants/" + row["id"]
    assert (
        client.patch(
            path + "/onboarding/demographics",
            json={"version": row["version"], "date_of_birth": "2000-01-01"},
        ).status_code
        == 422
    )
    response = client.patch(
        path + "/sensitive",
        json={"version": row["version"], "refugee_status": "YES", "disability_status": "YES"},
    )
    assert response.status_code == 200
    missing = client.get(path).json()["missing_fields"]
    assert {"ghana_card", "nationality", "disability_specify"} <= set(missing)
    from app.modules.supply.ages import programme_today

    future = date(programme_today().year + 2, 12, 31)
    current = client.get(path).json()
    response = client.patch(
        path + "/onboarding/basic",
        json={
            "version": current["version"],
            "first_name": current["first_name"],
            "surname": current["surname"],
            "onboarding_date": str(future),
        },
    )
    assert response.status_code == 200, response.text
    assert client.get(path + "/sensitive").json()["onboarding_age_projected"] is True


@pytest.fixture(scope="module")
def lifecycle_engine():
    yield from supply_tests.engine.__wrapped__()


@pytest.fixture
def lifecycle_db(lifecycle_engine, monkeypatch):
    from sqlalchemy.orm import Session

    from app.db.session import get_db
    from app.main import app

    connection = lifecycle_engine.connect()
    transaction = connection.begin()
    session = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: session
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-NOTICE")
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(
        settings, "supply_required_sections", ["basic", "contact", "consent", "review"]
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        try:
            session.close()
        finally:
            transaction.rollback()
            connection.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Local PostgreSQL required"
)
def test_placement_fields_start_age_verification_and_export(lifecycle_db):
    from test_matching_integration import parents

    from app.modules.iam.models import now
    from app.modules.matching.models import CandidateVacancy
    from app.modules.supply.models import Person

    db = lifecycle_db
    client, user = login(db, "ADMIN")
    participant, vacancy = parents(db, user, complete=True)
    person = db.get(Person, participant.person_id)
    person.date_of_birth = date(2000, 6, 14)
    participant.onboarding_date = date(2026, 1, 2)
    candidate = CandidateVacancy(
        participant_id=participant.id,
        vacancy_id=vacancy.id,
        status="SELECTED",
        source="STAFF",
        priority="NORMAL",
        created_by=user.id,
        submitted_at=now(),
        selected_at=now(),
    )
    db.add(candidate)
    db.commit()
    details = {
        "placed_by_partner": "Synthetic placing partner",
        "placement_region": "GREATER_ACCRA",
        "placement_district": "ACCRA",
        "placement_community": "Synthetic work location",
        "sector": "SERVICES",
        "industry": "TECHNOLOGY",
        "job_type": "ASSOCIATE",
        "job_role": "Synthetic analyst",
        "employment_type": "WAGE",
        "employment_category": "NEW",
        "employer_name": "Synthetic employer name",
        "contract_type": "FIXED_TERM",
        "work_hours": "40.00",
        "work_hours_period": "WEEK",
    }
    response = client.post(
        "/api/v1/placements",
        json={
            "candidate_vacancy_id": str(candidate.id),
            **details,
            "salary_amount": "1200.00",
            "salary_currency": "GHS",
            "salary_frequency": "MONTHLY",
            "payroll_frequency": "MONTHLY",
            "payday_rule_json": {"day": 25},
        },
    )
    assert response.status_code == 201, response.text
    placement = response.json()
    assert all(placement[key] == value for key, value in details.items())
    path = "/api/v1/placements/" + placement["id"]
    assert (
        client.post(
            path + "/first-income/confirm",
            json={
                "version": placement["first_income"]["version"],
                "actual_income_received_date": "2026-06-25",
                "amount_received": "1200.00",
                "notes": "Synthetic evidence",
            },
        ).status_code
        == 422
    )
    response = client.post(
        path + "/confirm-start",
        json={
            "version": placement["version"],
            "actual_start_date": "2026-06-14",
            "notes": "Synthetic start verified",
        },
    )
    assert response.status_code == 200, response.text
    placement = response.json()
    assert placement["age_at_placement_start"] == 26
    assert placement["confirmed_at"] is None and placement["status"] == "AWAITING_FIRST_INCOME"
    assert person.community == "Accra"
    response = client.post(
        path + "/first-income/confirm",
        json={
            "version": placement["first_income"]["version"],
            "actual_income_received_date": "2026-06-25",
            "amount_received": "1200.00",
            "notes": "Synthetic first monthly income verified",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CONFIRMED"
    report = programme.build(db, date(2026, 1, 1), date(2026, 12, 31), True)
    values = report["sheets"]["Placements"][0]
    assert len(values) == 16 and values[0] == details["placed_by_partner"]
    assert values[1] == date(2026, 6, 14) and values[4] == details["placement_community"]
    assert values[13] == details["employer_name"] and str(values[15]) == "40.00"
    assert report["sheets"]["3. Employment"][0][13] == 26

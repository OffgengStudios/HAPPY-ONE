"""Confirmation boundaries use real routes and rollback-only synthetic fixtures."""

import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_matching_integration import login, parents
from test_participant_lifecycle import lifecycle_db as lifecycle_db
from test_participant_lifecycle import lifecycle_engine as lifecycle_engine

from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, now
from app.modules.matching.models import CandidateVacancy
from app.modules.merl.models import Outcome
from app.modules.placement import service
from app.modules.placement.models import FirstIncomeVerification, Placement
from app.modules.supply.models import Document

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Local DB required"),
]


@pytest.fixture
def started(lifecycle_db, monkeypatch):
    db = lifecycle_db
    monkeypatch.setattr(service, "programme_today", lambda: date(2026, 10, 30))
    client, user = login(db, "ADMIN")
    participant, vacancy = parents(db, user, complete=True)
    candidate = CandidateVacancy(
        participant_id=participant.id,
        vacancy_id=vacancy.id,
        status="SELECTED",
        source="STAFF",
        priority="NORMAL",
        submitted_at=now(),
        selected_at=now(),
        created_by=user.id,
    )
    db.add(candidate)
    db.commit()
    response = client.post(
        "/api/v1/placements",
        json={
            "candidate_vacancy_id": str(candidate.id),
            "payroll_frequency": "MONTHLY",
            "payday_rule_json": {"day": 25},
        },
    )
    assert response.status_code == 201, response.text
    row = response.json()
    path = "/api/v1/placements/" + row["id"]
    response = client.post(
        path + "/confirm-start",
        json={
            "version": row["version"],
            "actual_start_date": "2026-10-01",
            "notes": "Synthetic actual start",
        },
    )
    assert response.status_code == 200, response.text
    return db, client, user, participant, path, response.json()


def kpi(client):
    response = client.get("/api/v1/reports/kpis?date_from=2026-01-01&date_to=2027-12-31")
    assert response.status_code == 200
    return next(v["value"] for v in response.json()["items"] if v["code"] == "KPI-PLC-001")


@pytest.mark.parametrize("correction", [False, True])
@pytest.mark.parametrize(
    "received,accepted",
    [
        ("2026-10-31", False),
        ("2027-10-30", False),
        ("2026-09-30", False),
        ("2026-10-01", True),
        ("2026-10-30", True),
        ("2026-10-15", True),
    ],
)
def test_received_date_bounds_have_no_rejected_achievement(started, correction, received, accepted):
    db, client, _, _, path, row = started
    before = kpi(client)
    response = client.post(
        path + ("/correct-confirmation" if correction else "/first-income/confirm"),
        json={
            "version": row["version"] if correction else row["first_income"]["version"],
            "actual_income_received_date": received,
            "amount_received": "100.00",
            **(
                {"confirmed": True, "reason": "Synthetic correction"}
                if correction
                else {"notes": "Synthetic verification"}
            ),
        },
    )
    assert response.status_code == (200 if accepted else 422), response.text
    db.expire_all()
    if not accepted:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Placement)
                .where(Placement.confirmed_at.is_not(None))
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.event_code.in_(
                        ["placement.first_income_confirmed", "placement.confirmation_corrected"]
                    )
                )
            )
            == 0
        )
        assert db.scalar(select(func.count()).select_from(Outcome)) == 0
        assert kpi(client) == before
    else:
        assert response.json()["status"] == "CONFIRMED"


def test_replay_is_one_achievement_and_invalid_correction_preserves_confirmation(started):
    db, client, _, _, path, row = started
    body = {
        "version": row["first_income"]["version"],
        "actual_income_received_date": "2026-10-30",
        "amount_received": "100.00",
        "notes": "Synthetic verified income",
    }
    first = client.post(path + "/first-income/confirm", json=body)
    replay = client.post(path + "/first-income/confirm", json=body)
    assert first.status_code == replay.status_code == 200
    assert first.json()["confirmed_at"] == replay.json()["confirmed_at"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_code == "placement.first_income_confirmed")
        )
        == 1
    )
    response = client.post(
        path + "/correct-confirmation",
        json={
            "version": first.json()["version"],
            "confirmed": True,
            "actual_income_received_date": "2027-10-30",
            "reason": "Synthetic invalid correction",
        },
    )
    assert response.status_code == 422
    db.expire_all()
    assert db.scalar(select(FirstIncomeVerification.actual_income_received_date)) == date(
        2026, 10, 30
    )


def test_correction_cannot_confirm_without_actual_start(started):
    db, client, _, _, path, row = started
    # Simulate a legacy incomplete start, without changing the verification under test.
    placement = db.get(Placement, row["id"])
    placement.actual_start_date = None
    placement.status = "START_PENDING"
    db.commit()
    response = client.post(
        path + "/correct-confirmation",
        json={
            "version": row["version"],
            "confirmed": True,
            "actual_income_received_date": "2026-10-30",
            "reason": "Synthetic no-start correction",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "correction,case,expected",
    [
        (correction, case, expected)
        for correction in (False, True)
        for case, expected in (
            ("FOREIGN", 404),
            ("REJECTED", 422),
            ("SCANNING", 422),
            ("ARCHIVED", 404),
            ("MISSING", 404),
            ("UNAUTHORIZED", 403),
            ("AVAILABLE", 200),
            ("NOTES_ONLY", 200),
        )
        # FK integrity prevents an existing correction from retaining a missing document.
        if not (correction and case == "MISSING")
    ],
)
def test_evidence_eligibility_on_every_confirmation_path(started, correction, case, expected):
    db, client, user, participant, path, row = started
    identifier = None
    if case != "NOTES_ONLY":
        identifier = uuid4()
        if case != "MISSING":
            owner = parents(db, user, complete=True)[0] if case == "FOREIGN" else participant
            db.add(
                Document(
                    id=identifier,
                    participant_id=owner.id,
                    document_code="REG-" + uuid4().hex,
                    storage_key="synthetic/" + uuid4().hex,
                    original_filename="synthetic.pdf",
                    mime_type="application/pdf",
                    size_bytes=1,
                    sha256="0" * 64,
                    version_number=1,
                    scan_status=case
                    if case in {"SCANNING", "REJECTED", "ARCHIVED"}
                    else "AVAILABLE",
                    archived_at=now() if case == "ARCHIVED" else None,
                    created_by=user.id,
                )
            )
        if case == "UNAUTHORIZED":
            permission = db.scalar(select(Permission).where(Permission.code == "cv:download"))
            db.add(PermissionOverride(user_id=user.id, permission_id=permission.id, effect="DENY"))
        # A missing FK cannot be retained by a legacy correction record.
        if correction and case != "MISSING":
            db.scalar(select(FirstIncomeVerification)).evidence_document_id = identifier
        db.commit()
        db.expire(user, ["overrides"])
    before = kpi(client)
    response = client.post(
        path + ("/correct-confirmation" if correction else "/first-income/confirm"),
        json={
            "version": row["version"] if correction else row["first_income"]["version"],
            "actual_income_received_date": "2026-10-30",
            "amount_received": "100.00",
            **(
                {"confirmed": True, "reason": "Synthetic correction"}
                if correction
                else {
                    "notes": "Synthetic verification",
                    "evidence_document_id": str(identifier) if identifier else None,
                }
            ),
        },
    )
    assert response.status_code == expected, response.text
    if expected != 200:
        assert kpi(client) == before
        db.expire_all()
        assert db.scalar(select(Placement.confirmed_at)) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.event_code.in_(
                        ["placement.first_income_confirmed", "placement.confirmation_corrected"]
                    )
                )
            )
            == 0
        )


def test_replay_cannot_substitute_ineligible_evidence(started):
    _, client, _, _, path, row = started
    body = {
        "version": row["first_income"]["version"],
        "actual_income_received_date": "2026-10-30",
        "notes": "Synthetic verification",
    }
    first = client.post(path + "/first-income/confirm", json=body)
    assert first.status_code == 200
    response = client.post(
        path + "/first-income/confirm", json={**body, "evidence_document_id": str(uuid4())}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("correction", [False, True])
def test_client_cannot_supply_a_verification_timestamp(started, correction):
    _, client, _, _, path, row = started
    response = client.post(
        path + ("/correct-confirmation" if correction else "/first-income/confirm"),
        json={
            "version": row["version"] if correction else row["first_income"]["version"],
            "actual_income_received_date": "2026-10-30",
            "verified_at": "2027-10-30T00:00:00Z",
            **(
                {"confirmed": True, "reason": "Synthetic correction"}
                if correction
                else {"notes": "Synthetic verification"}
            ),
        },
    )
    assert response.status_code == 422

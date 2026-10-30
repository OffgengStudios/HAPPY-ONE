"""Independent PostgreSQL sessions exercise capacity and income races."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_matching_integration import login, parents

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.iam.models import AuditEvent, Permission, PermissionOverride, now
from app.modules.matching.models import CandidateVacancy
from app.modules.placement import service
from app.modules.placement.models import Placement

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]


def test_concurrent_starts_respect_capacity_and_income_replay_counts_once(monkeypatch):
    schema, url = create_test_schema()
    engine = create_engine(url)
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-NOTICE")
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(
        settings, "supply_required_sections", ["basic", "contact", "consent", "review"]
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])

    def database():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = database
    original = service.headcount

    def measured_headcount(vacancy, session):
        counts = original(vacancy, session)
        # Widen the real read/write race window without fabricating query results.
        time.sleep(0.2)
        return counts

    monkeypatch.setattr(service, "headcount", measured_headcount)
    try:
        with Session(engine, expire_on_commit=False) as seed:
            client, user = login(seed)
            permission = seed.scalar(
                select(Permission).where(Permission.code == "placement:confirm")
            )
            seed.add(
                PermissionOverride(user_id=user.id, permission_id=permission.id, effect="ALLOW")
            )
            first, vacancy = parents(seed, user, complete=True)
            second, _ = parents(seed, user, complete=True)
            vacancy.required_headcount = 1
            candidates = []
            for participant in (first, second):
                candidate = CandidateVacancy(
                    participant_id=participant.id,
                    vacancy_id=vacancy.id,
                    status="SELECTED",
                    source="STAFF",
                    priority="NORMAL",
                    submitted_at=now(),
                    selected_at=now(),
                    created_by=user.id,
                    updated_by=user.id,
                )
                seed.add(candidate)
                candidates.append(candidate)
            seed.commit()
            vacancy_id = vacancy.id
            assert "vacancy:overfill_override" not in service.permissions_for(user)
            placements = []
            for candidate in candidates:
                response = client.post(
                    "/api/v1/placements",
                    json={
                        "candidate_vacancy_id": str(candidate.id),
                        "candidate_version": candidate.version,
                        "expected_start_date": "2026-10-10",
                        "salary_amount": "2400.00",
                        "salary_frequency": "MONTHLY",
                        "payroll_frequency": "MONTHLY",
                        "payday_rule_json": {"day": 25, "cutoff_day": 15},
                    },
                )
                assert response.status_code == 201, response.text
                placements.append(response.json())

        barrier = Barrier(2)

        def start(placement):
            barrier.wait(timeout=10)
            return client.post(
                f"/api/v1/placements/{placement['id']}/confirm-start",
                json={
                    "version": placement["version"],
                    "actual_start_date": "2026-10-10",
                    "notes": "Synthetic concurrent actual start",
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(start, placements))
        assert sorted(response.status_code for response in responses) == [200, 409], [
            response.text for response in responses
        ]
        started = next(response.json() for response in responses if response.status_code == 200)
        assert started["status"] == "AWAITING_FIRST_INCOME" and not started["confirmed_at"]
        with Session(engine) as check:
            assert (
                check.scalar(
                    select(func.count())
                    .select_from(Placement)
                    .where(
                        Placement.vacancy_id == vacancy_id, Placement.actual_start_date.is_not(None)
                    )
                )
                == 1
            )
        barrier = Barrier(2)

        def confirm(_):
            barrier.wait(timeout=10)
            return client.post(
                f"/api/v1/placements/{started['id']}/first-income/confirm",
                json={
                    "version": started["first_income"]["version"],
                    "actual_income_received_date": "2026-10-25",
                    "amount_received": "2400.00",
                    "notes": "Synthetic first income verified",
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            confirmations = list(pool.map(confirm, range(2)))
        assert [response.status_code for response in confirmations] == [200, 200]
        assert confirmations[0].json()["confirmed_at"] == confirmations[1].json()["confirmed_at"]
        with Session(engine) as check:
            assert (
                check.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.entity_id == UUID(started["id"]),
                        AuditEvent.event_code == "placement.first_income_confirmed",
                    )
                )
                == 1
            )
            assert (
                check.scalar(
                    select(func.count())
                    .select_from(Placement)
                    .where(Placement.vacancy_id == vacancy_id, Placement.confirmed_at.is_not(None))
                )
                == 1
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        drop_test_schema(schema)

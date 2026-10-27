"""Simultaneous HTTP submissions use independent real PostgreSQL transactions."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_public_intake_integration import ORIGIN, payload, submit

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.integrations.intake.models import PublicIntake
from app.main import app
from app.modules.supply.models import Participant

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1",
        reason="Requires isolated PostgreSQL.",
    ),
]


def test_simultaneous_replays_and_distinct_duplicate_submissions(monkeypatch):
    schema, url = create_test_schema()
    engine = create_engine(url)
    monkeypatch.setattr(
        settings, "identity_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "supply_privacy_notice_version", "SYNTHETIC-1")
    monkeypatch.setattr(settings, "supply_privacy_notice_text", "Synthetic test notice.")
    monkeypatch.setattr(settings, "supply_onboarding_policy_approved", True)
    monkeypatch.setattr(
        settings, "supply_required_sections", ["basic", "contact", "consent", "review"]
    )
    monkeypatch.setattr(settings, "supply_required_fields", [])
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])

    def independent_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = independent_session
    try:
        for replay in (True, False):
            first = payload()
            first["basic"]["surname"] = "ReplayCase" if replay else "ConcurrentCase"
            first["contact"]["phone_raw"] = "0241234501" if replay else "0241234502"
            second = first if replay else {**first, "submission_id": payload()["submission_id"]}
            barrier = Barrier(2)

            def request(data, barrier=barrier):
                with TestClient(app, headers=ORIGIN) as client:
                    barrier.wait(timeout=10)
                    return submit(client, data)

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(request, data) for data in (first, second)]
                responses = [future.result(timeout=30) for future in futures]
            assert all(response.status_code == 202 for response in responses), [
                response.text for response in responses
            ]
            if replay:
                assert responses[0].json() == responses[1].json()
            else:
                assert responses[0].json()["receipt_id"] != responses[1].json()["receipt_id"]
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(Participant)) == 2
            assert session.scalar(select(func.count()).select_from(PublicIntake)) == 3
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(PublicIntake)
                    .where(PublicIntake.status == "NEEDS_REVIEW")
                )
                == 1
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        drop_test_schema(schema)

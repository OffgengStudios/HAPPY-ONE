"""Simultaneous HTTP submissions use independent real PostgreSQL transactions."""

import io
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pypdf import PdfWriter
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_public_intake_integration import ORIGIN, payload, staff_login, submit

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.integrations.intake.models import PublicIntake
from app.main import app
from app.modules.external_references.models import ExternalReference
from app.modules.iam.models import AuditEvent
from app.modules.supply.models import Document, Participant, Person
from app.storage.s3 import get_storage_client

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
        with Session(engine, expire_on_commit=False) as session:
            staff = staff_login(session, "ADMIN")
            pending = session.scalar(
                select(PublicIntake).where(PublicIntake.status == "NEEDS_REVIEW")
            )
            target = session.scalar(
                select(Participant).join(Person).where(Person.surname == "ConcurrentCase")
            )
            pending_id, target_id = pending.id, target.id

        def simultaneous(send):
            gate = Barrier(2)

            def operation(_):
                gate.wait(timeout=10)
                return send()

            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(operation, range(2)))

        resolutions = simultaneous(
            lambda: staff.post(
                f"/api/v1/intake-operations/{pending_id}/resolve",
                json={
                    "existing_participant_id": str(target_id),
                    "reason": "Synthetic human duplicate review",
                },
            )
        )
        assert sorted(response.status_code for response in resolutions) == [200, 409]
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(Participant)) == 2
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ExternalReference)
                    .where(ExternalReference.external_id == str(pending.submission_id))
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.entity_id == pending_id,
                        AuditEvent.event_code == "participant_intake.duplicate_resolved",
                    )
                )
                == 1
            )
            version = session.get(Participant, target_id).version
        output = io.BytesIO()
        pdf = PdfWriter()
        pdf.add_blank_page(width=100, height=100)
        pdf.write(output)
        versions = simultaneous(
            lambda: staff.post(
                f"/api/v1/participants/{target_id}/cv",
                data={"version": version},
                files={"file": ("synthetic-concurrent.pdf", output.getvalue(), "application/pdf")},
            )
        )
        assert sorted(response.status_code for response in versions) == [201, 409], [
            response.text for response in versions
        ]
        with Session(engine) as session:
            documents = list(
                session.scalars(select(Document).where(Document.participant_id == target_id))
            )
            assert len(documents) == 1 and documents[0].version_number == 1
    finally:
        with Session(engine) as session:
            for document in session.scalars(select(Document)):
                get_storage_client().delete_object(
                    Bucket=settings.s3_bucket, Key=document.storage_key
                )
        app.dependency_overrides.clear()
        engine.dispose()
        drop_test_schema(schema)

"""Actual process death, PostgreSQL leases, authorized retry and private output."""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from uuid import uuid4

import psutil
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import API_ROOT, settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.integrations.hamis import service as hamis
from app.integrations.hamis import worker as hamis_worker
from app.integrations.hamis.models import HamisInboundEvent
from app.main import app
from app.modules.iam.models import AuditEvent, Role, User
from app.modules.iam.security import hasher
from app.modules.reporting import worker as reports
from app.modules.reporting.models import ReportExportJob
from app.modules.supply.models import Participant
from app.storage.s3 import get_storage_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1", reason="Requires PostgreSQL."
    ),
]


def test_real_final_claim_process_death_restart_retry_and_concurrent_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema, url = create_test_schema()
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "identity_encryption_key", SecretStr(key))
    monkeypatch.setattr(settings, "background_job_max_attempts", 1)
    monkeypatch.setattr(settings, "api_cors_origins", ["http://localhost:3000"])
    monkeypatch.setattr(reports, "get_session_factory", lambda: factory)
    monkeypatch.setattr(hamis_worker, "get_session_factory", lambda: factory)

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database
    process = None
    actual_pid = None
    marker = tmp_path / "claimed.json"
    password = "Synthetic worker recovery password 42"
    try:
        with factory() as db:
            role = db.scalar(select(Role).where(Role.code == "ADMIN"))
            user = User(
                email="worker-test@example.org",
                full_name="Synthetic Worker Operator",
                password_hash=hasher.hash(password),
                roles=[role],
                primary_role_id=role.id,
            )
            db.add(user)
            db.flush()
            job = ReportExportJob(
                requested_by=user.id,
                kpi_code="KPI-SUP-001",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
            payload = {
                "hamisId": "worker-recovery-synthetic",
                "firstName": "Synthetic",
                "surname": "Recovery",
                "telephone": "0241234567",
                "community": "Accra",
            }
            event = HamisInboundEvent(
                external_event_id="worker-recovery-" + uuid4().hex,
                event_type="PARTICIPANT_UPSERT",
                payload_hash=hamis.canonical_hash(payload),
                payload_ciphertext=hamis.encrypt_payload(payload),
            )
            db.add_all([job, event])
            db.commit()
            job_id, event_id, user_id = job.id, event.id, user.id
        code = """
import json,os,time
from pathlib import Path
from app.db.session import get_session_factory
from app.modules.reporting.worker import claim as report_claim
from app.integrations.hamis.worker import claim as hamis_claim
with get_session_factory()() as db:
    report,hamis = report_claim(db),hamis_claim(db)
Path(os.environ['CLAIM_MARKER']).write_text(json.dumps({'pid':os.getpid(),'report':str(report),'hamis':str(hamis)}))
while True: time.sleep(1)
"""
        environment = {
            **os.environ,
            "DATABASE_URL": url,
            "APP_ENV": "test",
            "IDENTITY_ENCRYPTION_KEY": key,
            "BACKGROUND_JOB_MAX_ATTEMPTS": "1",
            "BACKGROUND_JOB_LEASE_SECONDS": "30",
            "CLAIM_MARKER": str(marker),
        }
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=API_ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 30
        while not marker.exists():
            assert process.poll() is None and time.monotonic() < deadline, (
                "Claim worker did not start"
            )
            time.sleep(0.1)
        claimed = json.loads(marker.read_text())
        assert claimed["report"] == str(job_id) and claimed["hamis"] == str(event_id)
        actual_pid = claimed["pid"]
        actual = psutil.Process(actual_pid)
        assert actual.cwd() == str(API_ROOT) and "-c" in actual.cmdline()
        actual.terminate()
        actual.wait(timeout=10)
        # Verify valid final leases are preserved even though the process is dead.
        assert reports.run_once() is False and hamis_worker.run_once() is False
        time.sleep(31)
        # A fresh interpreter reconciles, rather than manufacturing an expired timestamp.
        restarted = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.workers.operations import run_once; "
                "assert run_once(); assert run_once(); assert not run_once()",
            ],
            cwd=API_ROOT,
            env=environment,
            capture_output=True,
            timeout=30,
        )
        assert restarted.returncode == 0, "Restarted reconciler failed"
        with factory() as db:
            job, event = db.get(ReportExportJob, job_id), db.get(HamisInboundEvent, event_id)
            assert job.status == event.status == "FAILED"
            assert job.error_code == event.error_code == "RETRY_LIMIT_EXCEEDED"
            assert job.completed_at and event.processed_at
            assert job.lease_owner is None and event.lease_owner is None
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action.in_(["report.export_failed", "hamis.event_failed"]))
                )
                == 2
            )
            versions = job.version, event.version
        client = TestClient(app, headers={"Origin": "http://localhost:3000"})
        assert (
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "worker-test@example.org",
                    "password": password,
                },
            ).status_code
            == 200
        )
        client.headers["X-CSRF-Token"] = client.cookies.get("happy_csrf")
        for path, version in [
            (f"/reports/export-jobs/{job_id}/retry", versions[0]),
            (f"/integrations/hamis/events/{event_id}/retry", versions[1]),
        ]:
            response = client.post(
                "/api/v1" + path,
                json={
                    "version": version,
                    "reason": "Synthetic operator confirmed dependency recovery",
                },
            )
            assert response.status_code == 202, response.text
            assert (
                client.post(
                    "/api/v1" + path,
                    json={
                        "version": version,
                        "reason": "Duplicate retry",
                    },
                ).status_code
                == 409
            )
        assert reports.run_once() and hamis_worker.run_once()
        assert not reports.run_once() and not hamis_worker.run_once()
        download = client.get(f"/api/v1/reports/export-jobs/{job_id}/download")
        assert download.status_code == 200
        with factory() as db:
            assert db.get(ReportExportJob, job_id).status == "SUCCEEDED"
            assert db.get(HamisInboundEvent, event_id).status == "APPLIED"
            assert db.scalar(select(func.count()).select_from(Participant)) == 1
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action == "report.export_completed")
                )
                == 1
            )
            pending = [
                ReportExportJob(
                    requested_by=user_id,
                    kpi_code="KPI-SUP-001",
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                )
                for _ in range(2)
            ]
            db.add_all(pending)
            db.commit()
            pending_ids = {r.id for r in pending}

        def independent_claim(_):
            with factory() as db:
                return reports.claim(db)

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert set(pool.map(independent_claim, range(2))) == pending_ids
        objects = (
            get_storage_client()
            .list_objects_v2(Bucket=settings.s3_bucket, Prefix=f"reports/exports/{user_id}/")
            .get("Contents", [])
        )
        assert len(objects) == 1
    finally:
        if actual_pid:
            try:
                child = psutil.Process(actual_pid)
                if child.cwd() == str(API_ROOT) and "-c" in child.cmdline():
                    child.terminate()
                    child.wait(timeout=10)
            except psutil.NoSuchProcess:
                pass
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        with factory() as db:
            for job in db.scalars(
                select(ReportExportJob).where(ReportExportJob.storage_key.is_not(None))
            ):
                assert job.storage_key.startswith(f"reports/exports/{job.requested_by}/")
                get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=job.storage_key)
        app.dependency_overrides.clear()
        engine.dispose()
        drop_test_schema(schema)

import json
import os
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_public_intake_integration import staff_login

from app.core import operational_health as operations
from app.db.operational import OperationalState
from app.main import app
from app.workers import operations as worker

pytest_plugins = ["test_public_intake_integration"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1",
        reason="Requires isolated PostgreSQL.",
    ),
]


def test_poll_failure_and_recovery_preserve_last_success_and_history(db, monkeypatch, caplog):
    previous = datetime.now(UTC) - timedelta(minutes=5)
    operations.record_state(db, "WORKER", succeeded=True, current=previous)
    operations.record_state(db, "WORKER", heartbeat=True)
    db.commit()
    monkeypatch.setattr(operations, "get_session_factory", lambda: lambda: nullcontext(db))
    monkeypatch.setattr(
        worker, "run_report_once", Mock(side_effect=RuntimeError("SENTINEL-private-error"))
    )
    with pytest.raises(RuntimeError):
        worker.run_once()
    row = db.get(OperationalState, "WORKER", populate_existing=True)
    assert row.last_success_at == previous and row.last_failure_at and row.heartbeat_at
    assert row.consecutive_failures == 1
    monkeypatch.setattr(worker, "run_report_once", lambda: False)
    monkeypatch.setattr(worker, "run_parser_once", lambda: False)
    monkeypatch.setattr(worker.settings, "enable_legacy_integrations", False)
    monkeypatch.setattr(worker, "_last_poll_checkpoint", 0)
    assert worker.run_once() is False
    db.refresh(row)
    assert row.last_success_at > previous and row.last_failure_at
    assert row.consecutive_failures == 0
    assert "SENTINEL-private-error" not in caplog.text


def test_backup_restore_outcomes_and_snapshot_are_private_and_authorized(db):
    for component in ("BACKUP", "RESTORE"):
        operations.record_state(db, component, succeeded=False)
        operations.record_state(db, component, succeeded=False)
        assert db.get(OperationalState, component, populate_existing=True).consecutive_failures == 2
        operations.record_state(db, component, succeeded=True)
    db.commit()
    public = TestClient(app)
    assert public.get("/api/v1/health/operations").status_code == 401
    marketing = staff_login(db, "MARKETING")
    assert marketing.get("/api/v1/health/operations").status_code == 403
    admin = staff_login(db, "ADMIN")
    response = admin.get("/api/v1/health/operations")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["components"]["BACKUP"]["last_success_timestamp"] > 0
    assert data["components"]["RESTORE"]["consecutive_failures"] == 0
    assert data["queues"]["PARSER"]["queued"] == 0
    assert data["scan_backlog"] == 0
    assert not any(
        value in json.dumps(data)
        for value in ("email", "storage_key", "government_id", "lease_owner")
    )
    assert list(db.scalars(select(OperationalState)))

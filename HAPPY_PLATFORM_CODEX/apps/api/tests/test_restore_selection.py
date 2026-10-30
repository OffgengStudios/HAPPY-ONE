"""Exercise real SDK pagination and checksum selection without a live restore."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.stub import Stubber
from pydantic import SecretStr

from app.db import backup


@pytest.fixture
def selection(monkeypatch):
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="synthetic",
        aws_secret_access_key="synthetic",
    )
    monkeypatch.setattr(backup.settings, "backup_s3_bucket", "synthetic-backups")
    monkeypatch.setattr(backup.settings, "backup_s3_prefix", "database/")
    monkeypatch.setattr(
        backup.settings,
        "restore_admin_url",
        SecretStr("postgresql://synthetic:sentinel@localhost/postgres"),
    )
    monkeypatch.setattr(backup, "get_storage_client", lambda: client)
    monkeypatch.setattr(
        backup, "run", MagicMock(return_value=MagicMock(stdout="TABLE alembic_version"))
    )
    restored = MagicMock(return_value="0041_income_availability")
    alerts = MagicMock()
    monkeypatch.setattr(backup, "restore_test", restored)
    monkeypatch.setattr(backup, "alert", alerts)
    payloads = {}

    def download(bucket, key, target):
        Path(target).write_bytes(payloads[key])

    monkeypatch.setattr(client, "download_file", download)
    return client, restored, alerts, payloads


def pair(payloads, name, age=60, corrupt=False):
    timestamp = datetime.now(UTC) - timedelta(seconds=age)
    key = "database/" + name + ".dump"
    payloads[key] = b"damaged" if corrupt else b"synthetic verified archive"
    payloads[key + ".json"] = json.dumps(
        {
            "sha256": hashlib.sha256(b"synthetic verified archive").hexdigest(),
            "created_at": timestamp.isoformat(),
        }
    ).encode()
    return [{"Key": value, "LastModified": timestamp} for value in (key, key + ".json")]


def listing(stub, items, token=None, next_token=None):
    response = {"Contents": items, "IsTruncated": bool(next_token)}
    if next_token:
        response["NextContinuationToken"] = next_token
    expected = {"Bucket": "synthetic-backups", "Prefix": "database/"}
    if token:
        expected["ContinuationToken"] = token
    stub.add_response("list_objects_v2", response, expected)


def test_latest_on_second_page_among_over_1000_objects(selection):
    client, restored, alerts, payloads = selection
    old = pair(payloads, "old", age=7200)
    latest = pair(payloads, "latest")
    noise = [{"Key": f"database/noise-{n}", "LastModified": datetime.now(UTC)} for n in range(998)]
    with Stubber(client) as stub:
        listing(stub, old + noise, next_token="opaque-next-token")
        listing(stub, latest, token="opaque-next-token")
        assert backup.restore_latest() == "0041_income_availability"
        stub.assert_no_pending_responses()
    restored.assert_called_once()
    assert alerts.call_args.args[2]["key"] == "database/latest.dump"
    assert alerts.call_args.args[2]["rpo_met"] is True


@pytest.mark.parametrize(
    "invalid",
    ["archive_only", "manifest_only", "checksum", "malformed_manifest", "future_manifest"],
)
def test_newest_invalid_falls_back_with_age_and_warning(selection, invalid, caplog):
    client, restored, alerts, payloads = selection
    valid = pair(payloads, "valid", age=4000)
    newest = pair(payloads, "newest", age=10, corrupt=invalid == "checksum")
    if invalid == "archive_only":
        newest = newest[:1]
    elif invalid == "manifest_only":
        newest = newest[1:]
    elif invalid == "malformed_manifest":
        payloads["database/newest.dump.json"] = b"[]"
    elif invalid == "future_manifest":
        manifest = json.loads(payloads["database/newest.dump.json"])
        manifest["created_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        payloads["database/newest.dump.json"] = json.dumps(manifest).encode()
    with Stubber(client) as stub:
        listing(stub, valid + newest)
        backup.restore_latest()
    restored.assert_called_once()
    warning = alerts.call_args_list[0].args
    assert warning[:2] == ("database_restore_selection", "warning")
    assert warning[2]["key"] == "database/valid.dump"
    assert warning[2]["selected_backup_age_seconds"] >= 4000
    assert warning[2]["skipped_recovery_points"] == 1
    assert warning[2]["rpo_met"] is False
    assert "restore_recovery_point_selection" in caplog.text
    assert "sentinel" not in caplog.text


def test_no_valid_backups_never_attempts_restore(selection):
    client, restored, _, payloads = selection
    with Stubber(client) as stub:
        listing(stub, pair(payloads, "corrupt", corrupt=True))
        with pytest.raises(ValueError, match="No complete checksum-verified"):
            backup.restore_latest()
    restored.assert_not_called()


def test_actual_restore_failure_is_not_hidden_by_older_backup(selection):
    client, restored, _, payloads = selection
    restored.side_effect = RuntimeError("Synthetic restore unavailable")
    with Stubber(client) as stub:
        listing(stub, pair(payloads, "old", age=7200) + pair(payloads, "latest"))
        with pytest.raises(RuntimeError, match="restore unavailable"):
            backup.restore_latest()
    restored.assert_called_once()

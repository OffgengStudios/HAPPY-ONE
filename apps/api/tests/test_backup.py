import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.db import backup


def test_postgres_url_rejects_non_postgres() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        backup.postgres_url("sqlite:///unsafe.db")


def test_verify_backup_checks_manifest_and_catalogue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "happy.dump"
    archive.write_bytes(b"synthetic archive")
    archive.with_suffix(".dump.json").write_text(
        json.dumps({"sha256": backup.checksum(archive)}), encoding="utf-8"
    )
    command = MagicMock(stdout="TABLE public users\nTABLE DATA public alembic_version")
    monkeypatch.setattr(backup, "run", MagicMock(return_value=command))

    manifest = backup.verify_backup(archive)

    assert manifest["sha256"] == backup.checksum(archive)


def test_verify_backup_rejects_tampering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "happy.dump"
    archive.write_bytes(b"before")
    archive.with_suffix(".dump.json").write_text(
        json.dumps({"sha256": backup.checksum(archive)}), encoding="utf-8"
    )
    archive.write_bytes(b"after")
    run = MagicMock()
    monkeypatch.setattr(backup, "run", run)

    with pytest.raises(ValueError, match="checksum"):
        backup.verify_backup(archive)

    run.assert_not_called()


def test_restore_admin_url_must_use_maintenance_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup, "verify_backup", MagicMock(return_value={}))

    with pytest.raises(ValueError, match="postgres or template1"):
        backup.restore_test(
            tmp_path / "happy.dump",
            "postgresql://admin:secret@127.0.0.1:5432/happy",
        )


def test_scheduled_backup_uploads_verified_pair_and_prunes_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "happy-20261017.dump"
    archive.write_bytes(b"synthetic")
    archive.with_suffix(".dump.json").write_text("{}", encoding="utf-8")
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "database/expired.dump",
                    "LastModified": datetime.now(UTC) - timedelta(days=60),
                },
                {
                    "Key": "database/current.dump",
                    "LastModified": datetime.now(UTC),
                },
            ]
        }
    ]
    monkeypatch.setattr(backup.settings, "backup_s3_bucket", "happy-backups")
    monkeypatch.setattr(backup.settings, "backup_s3_prefix", "database/")
    monkeypatch.setattr(backup, "get_storage_client", lambda: client)
    monkeypatch.setattr(backup, "create_backup", lambda output: archive)
    monkeypatch.setattr(backup, "verify_backup", lambda path: {"sha256": "abc123"})
    monkeypatch.setattr(backup, "alert", MagicMock())

    result = backup.scheduled_backup()

    assert result == {
        "key": "database/happy-20261017.dump",
        "sha256": "abc123",
        "deleted": 1,
    }
    assert client.upload_file.call_count == 2
    client.delete_objects.assert_called_once()


def test_restore_latest_downloads_provider_archive_and_runs_isolated_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = MagicMock()
    client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "database/older.dump",
                "LastModified": datetime.now(UTC) - timedelta(days=1),
            },
            {"Key": "database/latest.dump", "LastModified": datetime.now(UTC)},
        ]
    }
    monkeypatch.setattr(backup.settings, "backup_s3_bucket", "happy-backups")
    monkeypatch.setattr(backup.settings, "backup_s3_prefix", "database/")
    monkeypatch.setattr(
        backup.settings,
        "restore_admin_url",
        backup.settings.restore_admin_url.__class__("postgresql://admin:secret@db/postgres"),
    )
    monkeypatch.setattr(backup, "get_storage_client", lambda: client)
    monkeypatch.setattr(backup, "restore_test", lambda archive, admin_url: "0031_oidc_sso")
    monkeypatch.setattr(backup, "alert", MagicMock())

    revision = backup.restore_latest()

    assert revision == "0031_oidc_sso"
    assert client.download_file.call_count == 2

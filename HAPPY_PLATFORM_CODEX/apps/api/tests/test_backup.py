import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.db import backup


def test_postgres_url_rejects_non_postgres() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        backup.postgres_url("sqlite:///unsafe.db")


@pytest.mark.parametrize("name", ["pg_dump", "pg_restore"])
def test_backup_uses_client_on_path_without_server_installation(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = str(tmp_path / name)
    monkeypatch.setattr(backup.shutil, "which", lambda value: client if value == name else None)
    server_lookup = MagicMock(side_effect=ValueError("No server installed"))
    monkeypatch.setattr(backup, "find_binary_directory", server_lookup)

    assert backup.executable(name) == client
    server_lookup.assert_not_called()


def test_backup_falls_back_to_installed_postgres_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup.shutil, "which", lambda value: None)
    monkeypatch.setattr(backup, "find_binary_directory", lambda: tmp_path)
    suffix = ".exe" if backup.os.name == "nt" else ""
    assert backup.executable("pg_restore") == str(tmp_path / f"pg_restore{suffix}")


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
    monkeypatch.setattr(backup, "executable", lambda name: f"/synthetic/{name}")

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

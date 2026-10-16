import json
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

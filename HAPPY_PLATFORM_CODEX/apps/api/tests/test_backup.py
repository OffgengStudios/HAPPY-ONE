import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.db import backup


@pytest.mark.parametrize("username", ["application", "restore_admin"])
def test_failed_postgres_child_never_exposes_credentials(
    username: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "SENTINEL-backup-credential-42"
    database = backup.postgres_url(f"postgresql://{username}:{secret}@127.0.0.1/postgres")
    execute = subprocess.run
    calls = []

    def observed(command, **kwargs):
        calls.append((command, kwargs))
        return execute(command, **kwargs)

    monkeypatch.setattr(backup.subprocess, "run", observed)
    previous = os.environ.get("PGPASSWORD")
    with pytest.raises(RuntimeError, match="PostgreSQL") as failed:
        backup.run(
            [
                sys.executable,
                "-c",
                "import os,sys; print(os.environ['PGPASSWORD']); "
                "print(os.environ['PGPASSWORD'],file=sys.stderr); sys.exit(7)",
            ],
            database=database,
        )
    assert calls[0][1]["env"]["PGPASSWORD"] == secret
    assert secret not in repr(calls[0][0])
    assert secret not in "".join(traceback.format_exception(failed.value))
    assert secret not in repr(failed.value)
    assert os.environ.get("PGPASSWORD") == previous


def test_successful_postgres_child_receives_password_only_in_its_environment() -> None:
    database = backup.postgres_url("postgresql://application:sentinel-success@127.0.0.1/happy")
    result = backup.run([sys.executable, "-c", "print('synthetic catalogue')"], database=database)
    assert result.stdout.strip() == "synthetic catalogue"
    assert "sentinel-success" not in repr(result.args)


def test_postgres_command_start_failure_has_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args, **kwargs):
        raise OSError("SENTINEL-operating-system-error")

    monkeypatch.setattr(backup.subprocess, "run", unavailable)
    with pytest.raises(RuntimeError, match="PostgreSQL") as failed:
        backup.run(["missing-pg-client"])
    assert "SENTINEL" not in "".join(traceback.format_exception(failed.value))


def test_postgres_url_rejects_password_query_parameters() -> None:
    with pytest.raises(ValueError, match="password"):
        backup.postgres_url("postgresql://application@db/happy?password=SENTINEL")


@pytest.mark.parametrize("action", ["create", "scheduled", "restore-latest"])
def test_backup_cli_and_scheduler_failure_output_is_sanitized(
    action: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "SENTINEL-scheduler-database-password"

    def failed(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["pg_dump", secret], secret, secret)

    monkeypatch.setattr(sys, "argv", ["backup", action])
    for name in ("create_backup", "scheduled_backup", "restore_latest"):
        monkeypatch.setattr(backup, name, failed)
    monkeypatch.setattr(backup, "alert", MagicMock())
    with pytest.raises(SystemExit) as stopped:
        backup.main()
    captured = capsys.readouterr()
    assert stopped.value.code == 1
    assert secret not in captured.out + captured.err
    assert "Traceback" not in captured.err


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


@pytest.mark.parametrize("action", ["create", "scheduled", "restore-test", "restore-latest"])
@pytest.mark.parametrize("failed", [False, True])
def test_backup_and_restore_entrypoints_keep_sentinel_private(
    action, failed, tmp_path, monkeypatch, capsys, caplog
):
    secret = "SENTINEL-entrypoint-password-42"
    monkeypatch.setattr(
        backup.settings, "database_url", f"postgresql://synthetic:{secret}@db/happy"
    )
    monkeypatch.setattr(
        backup.settings,
        "restore_admin_url",
        backup.settings.restore_admin_url.__class__(f"postgresql://synthetic:{secret}@db/postgres"),
    )
    monkeypatch.setattr(backup.settings, "backup_s3_bucket", "synthetic-backups")
    monkeypatch.delenv("HAPPY_RESTORE_ADMIN_URL", raising=False)
    monkeypatch.setattr(backup, "BACKUP_ROOT", tmp_path)
    monkeypatch.setattr(backup, "executable", lambda name: name)
    archive = tmp_path / "synthetic.dump"
    archive.write_bytes(b"synthetic backup")
    manifest = {"sha256": backup.checksum(archive)}
    archive.with_suffix(".dump.json").write_text(json.dumps(manifest))
    observed = []

    def child(command, **kwargs):
        assert secret not in repr(command)
        observed.append(command)
        if "--dbname" in command:
            assert kwargs["env"]["PGPASSWORD"] == secret
            if failed:
                return subprocess.CompletedProcess(command, 7, secret, secret)
        if "--file" in command:
            Path(command[command.index("--file") + 1]).write_bytes(b"synthetic backup")
        return subprocess.CompletedProcess(command, 0, "TABLE public alembic_version", "")

    monkeypatch.setattr(backup.subprocess, "run", child)
    monkeypatch.setattr(backup.psycopg, "connect", MagicMock())
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.scalar.side_effect = [
        "0036_vacancy_terms",
        20,
    ]
    monkeypatch.setattr(backup, "create_engine", lambda *args, **kwargs: engine)
    storage = MagicMock()
    storage.get_paginator.return_value.paginate.return_value = []
    storage.list_objects_v2.return_value = {
        "Contents": [{"Key": "database/synthetic.dump", "LastModified": datetime.now(UTC)}]
    }

    def download(bucket, key, target):
        if key.endswith(".json"):
            Path(target).write_text(json.dumps(manifest))
        else:
            Path(target).write_bytes(b"synthetic backup")

    storage.download_file.side_effect = download
    monkeypatch.setattr(backup, "get_storage_client", lambda: storage)
    alerts = MagicMock()
    monkeypatch.setattr(backup, "alert", alerts)
    monkeypatch.setattr(
        sys,
        "argv",
        ["backup", action, *([str(archive)] if action in {"create", "restore-test"} else [])],
    )
    if failed:
        with pytest.raises(SystemExit) as stopped:
            backup.main()
        assert stopped.value.code == 1
    else:
        backup.main()
    captured = capsys.readouterr()
    assert observed
    assert secret not in captured.out + captured.err + caplog.text
    assert secret not in repr(alerts.call_args_list)
    assert secret not in repr(storage.method_calls)


@pytest.fixture(autouse=True)
def isolate_operational_checkpoint_side_effects(monkeypatch):
    # This suite tests backup credentials/CLI behavior; durable checkpoint
    # semantics are covered against PostgreSQL in operational-health tests.
    monkeypatch.setattr(backup, "persist_state", MagicMock())

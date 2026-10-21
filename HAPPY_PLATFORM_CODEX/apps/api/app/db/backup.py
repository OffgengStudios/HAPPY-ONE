"""Create, validate and restore-test PostgreSQL backups without targeting live data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.core.config import PROJECT_ROOT, settings
from app.core.process import creation_flags
from app.db.local import find_binary_directory
from app.storage.s3 import get_storage_client

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef

BACKUP_ROOT = PROJECT_ROOT / ".local" / "backups"
RESTORE_DATABASE = re.compile(r"^happy_restore_test_[0-9a-f]{32}$")


def alert(event: str, status: str, details: dict[str, object]) -> None:
    url = settings.alert_webhook_url.get_secret_value()
    if not url:
        return
    payload = json.dumps(
        {"service": "happy-backup", "event": event, "status": status, **details}
    ).encode()
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def postgres_url(value: str) -> URL:
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or not url.database:
        raise ValueError("A PostgreSQL database URL is required.")
    if any(key.casefold() == "password" for key in url.query):
        raise ValueError("Use the URL password component, not a password query parameter.")
    return url.set(drivername="postgresql")


def executable(name: str) -> str:
    # Client-only Linux images have pg_dump/pg_restore without server pg_ctl.
    binary = shutil.which(name)
    if binary:
        return binary
    suffix = ".exe" if os.name == "nt" else ""
    return str(find_binary_directory() / f"{name}{suffix}")


def run(command: list[str], *, database: URL | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if database is not None:
        database = postgres_url(database.render_as_string(hide_password=False))
        # libpq reads this child-only credential. Never render it into argv or mutate
        # the worker's shared environment. An absent URL password must not inherit
        # an unrelated connection's PGPASSWORD (PGPASSFILE remains supported).
        environment.pop("PGPASSWORD", None)
        if database.password is not None:
            environment["PGPASSWORD"] = database.password
        connection = URL.create(
            database.drivername,
            username=database.username,
            host=database.host,
            port=database.port,
            database=database.database,
            query=database.query,
        )
        command = [
            *command,
            "--dbname",
            connection.render_as_string(hide_password=False),
        ]
    result = None
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            creationflags=creation_flags(),
        )
    except OSError:
        pass
    # Driver output is untrusted and may contain credentials. Do not attach it,
    # the command, or a chained subprocess exception to operational failures.
    if result is None:
        raise RuntimeError("PostgreSQL backup command could not start.")
    if result.returncode:
        raise RuntimeError(f"PostgreSQL backup command failed (exit {result.returncode}).")
    return result


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(output: Path | None = None) -> Path:
    source = postgres_url(settings.database_url)
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    archive = output or BACKUP_ROOT / f"happy-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.dump"
    archive = archive.resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            executable("pg_dump"),
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(archive),
        ],
        database=source,
    )
    manifest = {
        "format": "postgresql-custom",
        "created_at": datetime.now(UTC).isoformat(),
        "source_database": source.database,
        "sha256": checksum(archive),
        "size_bytes": archive.stat().st_size,
    }
    archive.with_suffix(archive.suffix + ".json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return archive


def verify_backup(archive: Path) -> dict[str, object]:
    archive = archive.resolve()
    manifest_path = archive.with_suffix(archive.suffix + ".json")
    if not archive.is_file() or not manifest_path.is_file():
        raise ValueError("Backup archive and checksum manifest are required.")
    manifest: dict[str, object] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != checksum(archive):
        raise ValueError("Backup checksum does not match its manifest.")
    catalogue = run([executable("pg_restore"), "--list", str(archive)]).stdout
    if "alembic_version" not in catalogue or "TABLE" not in catalogue:
        raise ValueError("Backup catalogue does not contain the expected HAPPY schema.")
    return manifest


def restore_test(archive: Path, admin_url: str) -> str:
    verify_backup(archive)
    admin = postgres_url(admin_url)
    if admin.database not in {"postgres", "template1"}:
        raise ValueError("Restore admin URL must connect to postgres or template1.")
    database = "happy_restore_test_" + uuid4().hex
    target = admin.set(database=database)
    with psycopg.connect(
        admin.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        run(
            [
                executable("pg_restore"),
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                str(archive.resolve()),
            ],
            database=target,
        )
        engine = create_engine(target.set(drivername="postgresql+psycopg"))
        try:
            with engine.connect() as connection:
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                tables = connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            if not revision or not tables:
                raise ValueError("Restored database is missing migration or table evidence.")
        finally:
            engine.dispose()
        return str(revision)
    finally:
        if not RESTORE_DATABASE.fullmatch(database):
            raise ValueError("Refusing to remove a database outside the restore-test namespace.")
        with psycopg.connect(
            admin.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def backup_key(filename: str) -> str:
    return settings.backup_s3_prefix.strip("/") + "/" + filename


def scheduled_backup() -> dict[str, object]:
    if not settings.backup_s3_bucket:
        raise ValueError("BACKUP_S3_BUCKET is required for scheduled backups.")
    client = get_storage_client()
    with tempfile.TemporaryDirectory(prefix="happy-backup-") as directory:
        archive = create_backup(Path(directory) / f"happy-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.dump")
        manifest = verify_backup(archive)
        manifest_path = archive.with_suffix(archive.suffix + ".json")
        client.upload_file(str(archive), settings.backup_s3_bucket, backup_key(archive.name))
        client.upload_file(
            str(manifest_path), settings.backup_s3_bucket, backup_key(manifest_path.name)
        )
    cutoff = datetime.now(UTC).timestamp() - settings.backup_retention_days * 86400
    deleted = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(
        Bucket=settings.backup_s3_bucket, Prefix=settings.backup_s3_prefix.strip("/") + "/"
    ):
        expired: list[ObjectIdentifierTypeDef] = [
            {"Key": item["Key"]}
            for item in page.get("Contents", [])
            if item["LastModified"].timestamp() < cutoff
        ]
        if expired:
            client.delete_objects(
                Bucket=settings.backup_s3_bucket, Delete={"Objects": expired, "Quiet": True}
            )
            deleted += len(expired)
    result = {"key": backup_key(archive.name), "sha256": manifest["sha256"], "deleted": deleted}
    alert("database_backup", "success", result)
    return result


def restore_latest() -> str:
    admin_url = settings.restore_admin_url.get_secret_value()
    if not admin_url:
        raise ValueError("RESTORE_ADMIN_URL is required for scheduled restore exercises.")
    client = get_storage_client()
    response = client.list_objects_v2(
        Bucket=settings.backup_s3_bucket, Prefix=settings.backup_s3_prefix.strip("/") + "/"
    )
    archives = [item for item in response.get("Contents", []) if item["Key"].endswith(".dump")]
    if not archives:
        raise ValueError("No provider backup is available for restore testing.")
    latest = max(archives, key=lambda item: item["LastModified"])["Key"]
    with tempfile.TemporaryDirectory(prefix="happy-restore-") as directory:
        archive = Path(directory) / Path(latest).name
        client.download_file(settings.backup_s3_bucket, latest, str(archive))
        client.download_file(settings.backup_s3_bucket, latest + ".json", str(archive) + ".json")
        revision = restore_test(archive, admin_url)
    alert("database_restore_exercise", "success", {"key": latest, "revision": revision})
    return revision


def execute() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["create", "verify", "restore-test", "scheduled", "restore-latest"]
    )
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--admin-url", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.admin_url:
        raise ValueError("Use RESTORE_ADMIN_URL in the environment, not --admin-url.")
    if arguments.action == "scheduled":
        try:
            result = scheduled_backup()
            print(f"Provider backup uploaded: {result['key']}")
        except Exception as error:
            alert("database_backup", "failure", {"error": type(error).__name__})
            raise
        return
    if arguments.action == "restore-latest":
        try:
            revision = restore_latest()
            print(f"Provider restore exercise passed at migration {revision}.")
        except Exception as error:
            alert("database_restore_exercise", "failure", {"error": type(error).__name__})
            raise
        return
    if arguments.action == "create":
        archive = create_backup(arguments.archive)
        print(f"Backup created: {archive}")
        return
    if not arguments.archive:
        parser.error("verify and restore-test require an archive path")
    if arguments.action == "verify":
        manifest = verify_backup(arguments.archive)
        print(f"Backup verified: {manifest['sha256']}")
        return
    admin_url = (
        os.environ.get("HAPPY_RESTORE_ADMIN_URL") or settings.restore_admin_url.get_secret_value()
    )
    if not admin_url:
        parser.error("restore-test requires RESTORE_ADMIN_URL in the private environment")
    revision = restore_test(arguments.archive, admin_url)
    print(f"Isolated restore test passed at migration {revision}.")


def main() -> None:
    try:
        execute()
    except Exception as error:
        print(f"Backup/restore operation failed ({type(error).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

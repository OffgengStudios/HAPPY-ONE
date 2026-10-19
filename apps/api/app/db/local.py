"""Run a project-local PostgreSQL cluster using installed PostgreSQL binaries."""

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import psycopg
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT
from app.core.process import creation_flags
from app.db.setup import SetupSettings, setup_database

LOCAL_ROOT = PROJECT_ROOT / ".local" / "postgres"
DATA_ROOT = LOCAL_ROOT / "data"
ADMIN_PASSWORD_FILE = LOCAL_ROOT / "admin-password"


def run_command(command: list[str]) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=creation_flags(),
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    result.check_returncode()


def find_binary_directory() -> Path:
    binary = shutil.which("pg_ctl")
    if binary:
        return Path(binary).parent
    installation_root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL"
    if installation_root.exists():
        versions = sorted(
            (path for path in installation_root.iterdir() if path.name.isdigit()),
            key=lambda path: int(path.name),
            reverse=True,
        )
        for version in versions:
            if (version / "bin" / "pg_ctl.exe").is_file():
                return version / "bin"
    raise ValueError("Install PostgreSQL or put its bin directory on PATH.")


def run_local_database(action: str) -> None:
    bin_directory = find_binary_directory()
    suffix = ".exe" if os.name == "nt" else ""
    pg_ctl = str(bin_directory / f"pg_ctl{suffix}")
    process_flags = creation_flags()
    control_command = [pg_ctl, "-D", str(DATA_ROOT)]

    if action in {"stop", "status"}:
        run_command([*control_command, action])
        return

    settings = SetupSettings()
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql" or url.host != "127.0.0.1":
        raise ValueError("For db:local, set DATABASE_URL to PostgreSQL at 127.0.0.1.")
    port = url.port or 5432
    running = False
    if (DATA_ROOT / "PG_VERSION").exists():
        result = subprocess.run(
            [*control_command, "status"],
            capture_output=True,
            creationflags=process_flags,
        )
        running = result.returncode == 0

    if not running:
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError(f"Port {port} is occupied; choose an unused DATABASE_URL port.")

        LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
        if not ADMIN_PASSWORD_FILE.exists():
            with ADMIN_PASSWORD_FILE.open("x", encoding="utf-8") as password_file:
                password_file.write(secrets.token_urlsafe(32) + "\n")
            ADMIN_PASSWORD_FILE.chmod(0o600)

        if not (DATA_ROOT / "PG_VERSION").exists():
            run_command(
                [
                    str(bin_directory / f"initdb{suffix}"),
                    "-D",
                    str(DATA_ROOT),
                    "--username=happy_local_admin",
                    f"--pwfile={ADMIN_PASSWORD_FILE}",
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--no-locale",
                ],
            )

        run_command(
            [
                *control_command,
                "-l",
                str(LOCAL_ROOT / "server.log"),
                "-o",
                f"-h 127.0.0.1 -p {port}",
                "-t",
                "30",
                "start",
            ],
        )

    setup_database(
        SetupSettings(
            postgres_admin_user="happy_local_admin",
            postgres_admin_password=SecretStr(
                ADMIN_PASSWORD_FILE.read_text(encoding="utf-8").strip()
            ),
        )
    )
    print(f"Project-local PostgreSQL is running at 127.0.0.1:{port}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"), default="start", nargs="?")
    action = parser.parse_args().action
    try:
        run_local_database(action)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except psycopg.Error:
        print(
            "Local database provisioning failed; check .env and .local/postgres/server.log.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

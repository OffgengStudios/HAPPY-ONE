import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = (
    ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
)
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
API = ROOT / "apps" / "api"
TEST_DIRECTORY = ROOT / ".local" / "pytest" / uuid4().hex
COMMANDS = {
    "dev": (API, ["-m", "uvicorn", "app.main:app", "--reload"]),
    "lint": (
        ROOT,
        [
            "-m",
            "ruff",
            "check",
            "--config",
            "apps/api/pyproject.toml",
            "apps/api",
            "database/migrations",
            "scripts",
        ],
    ),
    "type-check": (
        ROOT,
        ["-m", "mypy", "--config-file", "apps/api/pyproject.toml", "apps/api/app"],
    ),
    "test": (
        ROOT,
        [
            "-m",
            "pytest",
            "--basetemp",
            str(TEST_DIRECTORY / "tmp"),
            "-o",
            f"cache_dir={TEST_DIRECTORY / 'cache'}",
            "apps/api",
        ],
    ),
    "migrate": (API, ["-m", "alembic", "upgrade", "head"]),
    "db-setup": (API, ["-m", "app.db.setup"]),
    "db-local": (API, ["-m", "app.db.local"]),
    "db-backup": (API, ["-m", "app.db.backup"]),
    "storage-local": (API, ["-m", "app.storage.local"]),
    "storage-setup": (API, ["-m", "app.storage.setup"]),
    "iam-bootstrap": (API, ["-m", "app.modules.iam.bootstrap"]),
    "cv-parser-worker": (API, ["-m", "app.modules.cv_parser.worker"]),
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Choose an API command: " + ", ".join(COMMANDS), file=sys.stderr)
        return 1
    directory, command = COMMANDS[sys.argv[1]]
    if sys.argv[1] == "test":
        TEST_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return subprocess.call([PYTHON, *command, *sys.argv[2:]], cwd=directory)


if __name__ == "__main__":
    sys.exit(main())

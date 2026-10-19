import os
import subprocess
import sys

from app.core.config import API_ROOT


def test_migrations_accept_url_encoded_credentials() -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+psycopg://happy:p%40ss%25@localhost:5433/happy"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "0001_foundation" in result.stdout

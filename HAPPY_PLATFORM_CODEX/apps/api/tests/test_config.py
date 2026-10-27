import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.config import API_ROOT, PROJECT_ROOT, Settings, environment_files


@pytest.fixture(autouse=True)
def isolate_legacy_adapter_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_LEGACY_INTEGRATIONS", raising=False)


def test_environment_files_are_anchored_to_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HAPPY_ENV_FILE", raising=False)
    assert environment_files() == (
        PROJECT_ROOT / ".env",
        API_ROOT / ".env",
    )
    assert (PROJECT_ROOT / "pnpm-workspace.yaml").is_file()


@pytest.mark.parametrize("working_directory", ["root", "api"])
def test_environment_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, working_directory: str
) -> None:
    api_directory = tmp_path / "apps" / "api"
    api_directory.mkdir(parents=True)
    root_env = tmp_path / ".env"
    api_env = api_directory / ".env"
    root_env.write_text(
        "DATABASE_URL=postgresql+psycopg://root:password@localhost/root_db\n"
        'API_CORS_ORIGINS=["http://localhost:3000"]\n',
        encoding="utf-8",
    )
    monkeypatch.setitem(Settings.model_config, "env_file", (root_env, api_env))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_CORS_ORIGINS", raising=False)
    monkeypatch.chdir(tmp_path if working_directory == "root" else api_directory)

    assert Settings().database_url.endswith("/root_db")
    assert Settings().api_cors_origins == ["http://localhost:3000"]

    api_env.write_text(
        "DATABASE_URL=postgresql+psycopg://api:password@localhost/api_db\n",
        encoding="utf-8",
    )
    assert Settings().database_url.endswith("/api_db")

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://ci:password@localhost/ci_db")
    assert Settings().database_url.endswith("/ci_db")


def test_selected_environment_excludes_development_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    selected = tmp_path / ".env.staging"
    selected.write_text("APP_ENV=staging\nS3_BUCKET=happy-staging-private\n", encoding="utf-8")
    monkeypatch.setenv("HAPPY_ENV_FILE", str(selected))
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    assert environment_files() == (selected,)
    configured = Settings(_env_file=environment_files())
    assert configured.app_env == "staging"
    assert configured.s3_bucket == "happy-staging-private"


def test_missing_selected_environment_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HAPPY_ENV_FILE", str(tmp_path / "missing.env"))
    with pytest.raises(ValueError, match="does not exist"):
        environment_files()


def test_storage_credentials_are_redacted() -> None:
    configured = Settings()
    assert configured.s3_secret_access_key.get_secret_value() not in repr(configured)


def test_production_rejects_development_secrets_and_http_origins() -> None:
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(app_env="production")


def test_production_accepts_explicit_secure_configuration() -> None:
    configured = Settings(
        app_env="production",
        database_url="postgresql+psycopg://happy:unique-production-secret@db/happy",
        api_cors_origins=["https://happy.example.org"],
        s3_secret_access_key="unique-object-storage-secret",
        identity_encryption_key=Fernet.generate_key().decode(),
        identity_lookup_key="independent-lookup-secret-at-least-32-characters",
        backup_s3_bucket="happy-production-backups",
        alert_webhook_url="https://alerts.example.org/happy",
        otel_exporter_otlp_endpoint="https://telemetry.example.org",
    )

    assert configured.app_env == "production"


@pytest.mark.parametrize("key", ["SENTINEL-invalid-key", "SENTINEL-\u2603", "YWJj"])
def test_bad_fernet_key_is_rejected_without_exposing_input(key: str) -> None:
    with pytest.raises(ValueError, match="Fernet") as failed:
        Settings(identity_encryption_key=key)
    assert key not in str(failed.value)


def test_production_validation_does_not_render_any_input_credentials() -> None:
    with pytest.raises(ValueError) as failed:
        Settings(
            app_env="production",
            identity_encryption_key="",
            database_url="postgresql://app:SENTINEL-database-secret@db/happy",
            s3_secret_access_key="SENTINEL-object-storage-secret",
        )
    assert "SENTINEL" not in str(failed.value)


def test_configuration_repr_does_not_expose_database_or_telemetry_credentials() -> None:
    configured = Settings(
        database_url="postgresql://app:SENTINEL-database-secret@db/happy",
        otel_exporter_otlp_headers={"Authorization": "Bearer SENTINEL-telemetry-secret"},
    )
    assert "SENTINEL" not in repr(configured)


@pytest.mark.parametrize("module", ["app.main", "app.workers.operations"])
def test_actual_api_and_worker_startup_reject_bad_key_without_secret_output(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=API_ROOT,
        env={**os.environ, "IDENTITY_ENCRYPTION_KEY": "SENTINEL-invalid-startup-key"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Fernet" in result.stderr
    assert "SENTINEL" not in result.stdout + result.stderr


def test_application_encryption_round_trips_in_separate_worker_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.integrations.hamis.service import encrypt_payload

    key = Fernet.generate_key().decode()
    configured = Settings(identity_encryption_key=key)
    monkeypatch.setattr(settings, "identity_encryption_key", SecretStr(key))
    encrypted = encrypt_payload({"test": "synthetic key recovery"})
    code = (
        "import os,json; from app.integrations.hamis.service import decrypt_payload; "
        "assert decrypt_payload(os.environ['TEST_CIPHERTEXT']) == "
        "json.loads(os.environ['TEST_EXPECTED']); print('round-trip verified')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=API_ROOT,
        env={
            **os.environ,
            "IDENTITY_ENCRYPTION_KEY": configured.identity_encryption_key.get_secret_value(),
            "TEST_CIPHERTEXT": encrypted,
            "TEST_EXPECTED": json.dumps({"test": "synthetic key recovery"}),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "round-trip verified"
    assert key not in result.stdout + result.stderr

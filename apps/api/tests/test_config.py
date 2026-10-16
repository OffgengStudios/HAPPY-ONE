from pathlib import Path

import pytest

from app.core.config import API_ROOT, PROJECT_ROOT, Settings, environment_files


def test_environment_files_are_anchored_to_project() -> None:
    assert Settings.model_config["env_file"] == (
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
        identity_encryption_key="generated-fernet-key",
        identity_lookup_key="independent-lookup-secret-at-least-32-characters",
    )

    assert configured.app_env == "production"

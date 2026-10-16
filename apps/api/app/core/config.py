import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = PROJECT_ROOT / "apps" / "api"


def environment_files() -> tuple[Path, ...]:
    selected = os.environ.get("HAPPY_ENV_FILE")
    if selected:
        path = PROJECT_ROOT / selected
        if not path.is_file():
            raise ValueError("HAPPY_ENV_FILE does not exist.")
        return (path,)
    return (PROJECT_ROOT / ".env", API_ROOT / ".env")


class Settings(BaseSettings):
    app_name: str = "HAPPY Management Platform"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://happy:happy_dev_password@localhost:5432/happy"
    )
    api_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "happy-local-private"
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr = SecretStr("happy_local")
    s3_secret_access_key: SecretStr = SecretStr("happy_local_storage_password")
    auth_session_hours: int = Field(default=8, ge=1, le=168)
    auth_idle_minutes: int = Field(default=30, ge=1, le=1440)
    auth_login_limit: int = Field(default=5, ge=1, le=100)
    auth_ip_limit: int = Field(default=30, ge=1, le=1000)
    auth_window_minutes: int = Field(default=15, ge=1, le=60)
    demand_vacancy_confirmation_required: bool = True
    supply_privacy_notice_version: str = ""
    supply_onboarding_policy_approved: bool = False
    supply_required_fields: list[str] = Field(default_factory=list)
    supply_required_sections: list[str] = Field(
        default_factory=lambda: ["basic", "contact", "consent"]
    )
    file_max_bytes: int = Field(default=10485760, ge=1024, le=26214400)
    file_scan_host: str = ""
    file_scan_port: int = Field(default=3310, ge=1, le=65535)
    cv_parser_provider: str = ""
    cv_parser_model: str = ""
    cv_parser_url: str = ""
    cv_parser_token: SecretStr = SecretStr("")
    cv_parser_timeout_seconds: int = Field(default=60, ge=5, le=300)
    cv_parser_max_attempts: int = Field(default=5, ge=1, le=20)
    hamis_integration_token: SecretStr = SecretStr("")
    employer_portal_integration_token: SecretStr = SecretStr("")
    identity_encryption_key: SecretStr = SecretStr("")
    identity_lookup_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def production_safety(self) -> Self:
        if self.app_env != "production":
            return self
        database = make_url(self.database_url)
        failures: list[str] = []
        if database.password in {None, "", "happy_dev_password"}:
            failures.append("DATABASE_URL must use a production credential")
        if self.s3_secret_access_key.get_secret_value() in {
            "",
            "happy_local_storage_password",
        }:
            failures.append("S3_SECRET_ACCESS_KEY must use a production credential")
        if not self.api_cors_origins or any(
            not origin.startswith("https://") for origin in self.api_cors_origins
        ):
            failures.append("API_CORS_ORIGINS must contain only HTTPS origins")
        if not self.identity_encryption_key.get_secret_value():
            failures.append("IDENTITY_ENCRYPTION_KEY is required")
        if len(self.identity_lookup_key.get_secret_value()) < 32:
            failures.append("IDENTITY_LOOKUP_KEY must contain at least 32 characters")
        hamis_token = self.hamis_integration_token.get_secret_value()
        if hamis_token and len(hamis_token) < 32:
            failures.append("HAMIS_INTEGRATION_TOKEN must contain at least 32 characters")
        employer_token = self.employer_portal_integration_token.get_secret_value()
        if employer_token and len(employer_token) < 32:
            failures.append("EMPLOYER_PORTAL_INTEGRATION_TOKEN must contain at least 32 characters")
        if failures:
            raise ValueError("Unsafe production configuration: " + "; ".join(failures))
        return self

    model_config = SettingsConfigDict(
        env_file=environment_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

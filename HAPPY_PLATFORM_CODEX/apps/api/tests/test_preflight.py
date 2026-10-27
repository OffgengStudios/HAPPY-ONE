import os
import subprocess
import sys

import pytest
from cryptography.fernet import Fernet

from app.core.config import PROJECT_ROOT, Settings
from app.core.preflight import configuration_issues


def production_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "production",
        "enable_legacy_integrations": False,
        "database_url": "postgresql://app:synthetic-password@db/happy?sslmode=require",
        "api_cors_origins": ["https://staff.example.org", "https://intake.example.org"],
        "s3_endpoint_url": "https://storage.example.org",
        "s3_bucket": "synthetic-documents",
        "s3_secret_access_key": "synthetic-storage-password",
        "identity_encryption_key": Fernet.generate_key().decode(),
        "identity_lookup_key": "synthetic-independent-lookup-key-32-characters",
        "backup_s3_bucket": "synthetic-backups",
        "alert_webhook_url": "https://alerts.example.org/receive",
        "otel_exporter_otlp_endpoint": "https://telemetry.example.org",
        "supply_privacy_notice_text": "Synthetic approved notice",
        "supply_privacy_notice_version": "SYNTHETIC-1",
        "employer_intake_notice_text": "Synthetic employer notice",
        "supply_onboarding_policy_approved": True,
        "file_scan_host": "scanner.internal",
        "cv_parser_hostport": "parser.internal:8000",
        "cv_parser_token": "synthetic-machine-token-at-least-32-characters",
    }
    return Settings(_env_file=None, **{**values, **overrides})


def test_preflight_accepts_complete_configuration_without_network_access() -> None:
    assert configuration_issues(production_settings()) == []


def test_preflight_identifies_missing_launch_configuration_without_secret_values() -> None:
    configured = production_settings(
        supply_privacy_notice_text="",
        supply_privacy_notice_version="",
        employer_intake_notice_text="",
        supply_onboarding_policy_approved=False,
        file_scan_host="",
        cv_parser_hostport="",
        cv_parser_url="",
        cv_parser_token="SENTINEL",
        backup_s3_bucket="synthetic-documents",
    )
    issues = configuration_issues(configured)
    assert len(issues) == 7
    assert "SENTINEL" not in repr(issues)


def test_preflight_rejects_url_credentials_and_wildcard_origins() -> None:
    issues = configuration_issues(
        production_settings(
            s3_endpoint_url="https://user:SENTINEL@storage.example.org",
            api_cors_origins=["https://*.example.org"],
        )
    )
    assert len(issues) == 2
    assert "SENTINEL" not in repr(issues)


@pytest.mark.parametrize(
    "overrides",
    [
        {"IDENTITY_ENCRYPTION_KEY": "SENTINEL-invalid-key"},
        {"APP_ENV": "production", "DATABASE_URL": "SENTINEL-invalid-database-url"},
    ],
)
def test_preflight_cli_sanitizes_invalid_startup_configuration(overrides: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "preflight.py")],
        env={**os.environ, **overrides},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "Settings validation failed" in result.stdout
    assert "SENTINEL" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "overrides",
    [
        {"api_cors_origins": ["https://staff.example.org/"]},
        {"api_cors_origins": ["https://staff.example.org:bad-port"]},
        {"s3_endpoint_url": "https://storage.example.org:bad-port"},
        {"cv_parser_url": "https://user:SENTINEL@parser.example.org/parse"},
        {"cv_parser_url": "ftp://parser.example.org/parse"},
        {"cv_parser_hostport": "parser.internal:99999"},
    ],
)
def test_preflight_rejects_invalid_origins_and_parser_endpoints(overrides: dict) -> None:
    issues = configuration_issues(production_settings(**overrides))
    assert issues
    assert "SENTINEL" not in repr(issues)

"""Read-only production configuration checks. Never render configuration values."""

import json
from urllib.parse import urlsplit

from app.core.config import Settings


def configuration_issues(configured: Settings) -> list[str]:
    issues: list[str] = []
    if configured.app_env != "production":
        issues.append("APP_ENV must be production")
    # Apply the same startup safety checks even when inspecting a development file.
    try:
        Settings.model_validate({**configured.model_dump(), "app_env": "production"})
    except (ValueError, TypeError):
        issues.append("Production startup safety checks must pass")
    for name in ("s3_endpoint_url", "alert_webhook_url", "otel_exporter_otlp_endpoint"):
        raw = getattr(configured, name)
        value = raw.get_secret_value() if hasattr(raw, "get_secret_value") else raw
        try:
            parsed = urlsplit(value)
            secure = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and not parsed.username
                and not parsed.password
                and (parsed.port is None or 1 <= parsed.port <= 65535)
            )
        except ValueError:
            secure = False
        if not secure:
            issues.append(f"{name.upper()} must use an HTTPS endpoint without URL credentials")
    for origin in configured.api_cors_origins:
        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and not parsed.username
                and not parsed.password
                and parsed.path == ""
                and not parsed.query
                and not parsed.fragment
                and "*" not in origin
                and (parsed.port is None or 1 <= parsed.port <= 65535)
            )
        except ValueError:
            valid = False
        if not valid:
            issues.append("API_CORS_ORIGINS must contain exact HTTPS origins")
            break
    if not configured.supply_privacy_notice_text.strip():
        issues.append("SUPPLY_PRIVACY_NOTICE_TEXT must contain the approved participant notice")
    if not configured.supply_privacy_notice_version.strip():
        issues.append("SUPPLY_PRIVACY_NOTICE_VERSION must identify the approved notice")
    if not configured.supply_onboarding_policy_approved:
        issues.append("SUPPLY_ONBOARDING_POLICY_APPROVED must reflect programme approval")
    if not configured.file_scan_host.strip():
        issues.append("FILE_SCAN_HOST must identify the provisioned private scanner")
    if not (configured.cv_parser_url or configured.cv_parser_hostport):
        issues.append("CV_PARSER_URL or CV_PARSER_HOSTPORT must identify the private parser")
    if configured.cv_parser_url:
        try:
            parser = urlsplit(configured.cv_parser_url)
            valid_parser = (
                parser.scheme in {"http", "https"}
                and bool(parser.hostname)
                and not parser.username
                and not parser.password
                and not parser.query
                and not parser.fragment
                and (parser.port is None or 1 <= parser.port <= 65535)
            )
        except ValueError:
            valid_parser = False
        if not valid_parser:
            issues.append("CV_PARSER_URL must be an HTTP(S) endpoint without URL credentials")
    if (
        configured.cv_parser_hostport
        and not 1 <= int(configured.cv_parser_hostport.rsplit(":", 1)[1]) <= 65535
    ):
        issues.append("CV_PARSER_HOSTPORT must use a valid TCP port")
    if len(configured.cv_parser_token.get_secret_value()) < 32:
        issues.append("CV_PARSER_TOKEN must contain at least 32 characters")
    if configured.backup_s3_bucket == configured.s3_bucket:
        issues.append("BACKUP_S3_BUCKET must be separate from the document bucket")
    return issues


def main() -> int:
    from app.core.config import settings

    issues = configuration_issues(settings)
    print(json.dumps({"configuration_ready": not issues, "issues": issues}, indent=2))
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())

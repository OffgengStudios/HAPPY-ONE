# DevOps and Observability

## 1. Environments

- Development
- Staging
- Production

No direct developer use of production DB credentials.

## 2. CI

Every pull request:
1. formatting/lint
2. frontend type check
3. backend type/static checks as configured
4. unit tests
5. integration tests
6. build
7. dependency/security checks

## 3. CD

Recommended:

`Git → CI → Staging Deploy → Smoke/E2E → Approval → Production`

## 4. Database Migrations

- Alembic migrations committed
- no manual untracked production schema edits
- backwards-compatible strategy for risky deployments
- backup before destructive migrations

## 5. Backup

Required:
- automated PostgreSQL backups
- object-storage durability/versioning as appropriate
- periodic restore test

RPO/RTO values remain open decisions.

Implemented local operations:

- `pnpm db:backup create <archive>` creates a custom-format PostgreSQL archive
  and SHA-256 manifest.
- `pnpm db:backup verify <archive>` verifies the checksum and archive catalogue.
- `pnpm db:backup restore-test <archive>` requires an explicit maintenance
  administrator URL and rehearses recovery only in a disposable
  `happy_restore_test_*` database.

See [the production runbook](39-PRODUCTION-RUNBOOK.md) for release, restore,
rollback, incident and secret-rotation procedures.

## 6. Observability

Monitor:
- HTTP error rate
- API latency
- DB connections/slow queries
- worker failures
- queue backlog
- file scan failures
- authentication failures
- export failures
- AI/parser failures

## 7. Structured Logging

Every request should have a request/correlation ID.

Logs include:
- timestamp
- level
- service
- request ID
- safe actor/user ID where appropriate
- route
- result

No sensitive payload dumping.

Implemented API access logs include service, request ID, method, route, response
status and duration as structured JSON. Supplied request IDs are length- and
character-restricted before they are accepted.

The route is a matched template (some FastAPI versions expose it without router
prefixes), or `<unmatched>`; raw unknown paths and query strings are not logged.
The application suppresses the duplicate `uvicorn.access` logger even when a
caller uses default Uvicorn options, and sanitizes exception details in the server
error logger. Supported launch commands also use `--no-access-log`.

Outgoing spans pass through a privacy exporter before OTLP serialization. It
retains trace correlation, route/method/status, safe resource identifiers and
timing, while removing URLs/query strings, headers, SQL/parameters, span events,
exception messages/stacks, raw span names, links and vendor trace state. Metrics
use an allowlist of operational labels; participant identifiers, query values and
submitted content must never become labels. Do not enable HTTP-library wire/debug
logging in a participant-data environment.

Ingress access/error logs are an independent release gate. Configure a proxy or
provider log sink to retain correlation ID, normalized method, status and timing,
without `$request`, `$request_uri`, query strings, request headers, request bodies
or raw error tracebacks. Even an access-log format without queries is insufficient
if upstream error logs include the original URL. Before UAT, send sentinel search
values and SSO codes through the actual public ingress, trigger a controlled
upstream failure, and inspect all provider log destinations and OTLP dashboards.
Disable or sanitize any additional raw log stream before using real participant
data. Managed Render ingress logging and external collector behavior have not yet
been verified; application tests do not certify those providers.

## 8. Alerts

Create alerts for:
- service unavailable
- DB failure
- sustained error spike
- migration failure
- queue backlog
- backup failure
- storage failure

## 9. Feature Flags

Use for risky staged releases where useful.

Do not use feature flags to permanently hide incomplete security.

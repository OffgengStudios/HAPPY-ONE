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

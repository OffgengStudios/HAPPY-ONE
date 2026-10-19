# Durable Background Processing Acceptance

Acceptance date: 19 Oct 2026

Branch: `development`

## Scope

This checkpoint removes report generation and eligible HAMIS application from the
API process lifetime and combines them with the existing durable CV parser runner.

- Report requests commit `PENDING` jobs and return before execution.
- HAMIS requests commit encrypted `RECEIVED` events before application.
- The standalone `app.workers.operations` process claims work with PostgreSQL row
  locks and `SKIP LOCKED`.
- Jobs carry bounded attempt counts, retry timestamps, worker leases and lease
  expiry so another worker can recover work after a crash or restart.
- Report output remains private and requester-scoped; terminal success and failure
  are audited as system actions.
- HAMIS application preserves integration audit identity and still sends existing
  participants and unsupported event mappings to staff review.
- Employer Portal conversion remains staff-controlled and is not auto-executed.
- The Render blueprint and synthetic browser environment run the standalone worker
  from the same reviewed API image.

Migrations `0033_durable_jobs` and `0034_hamis_worker` add worker state without
renumbering or rewriting earlier revisions.

## Verification

The root `pnpm verify` command passed as one uninterrupted acceptance run:

- Python formatting: 188 files clean.
- Ruff and strict mypy: passed; mypy checked 120 source files.
- PostgreSQL/Alembic migration through `0034_hamis_worker`: passed.
- Backend unit and live integration tests: 276 passed.
- JavaScript formatting, ESLint and workspace TypeScript: passed.
- Environment tests: 4 passed.
- Next.js production build: passed.
- Authenticated Playwright suite: 98 passed across desktop and mobile with the
  synthetic API and operations worker running as separate processes.
- Python dependency consistency and vulnerability audit: passed.
- JavaScript production dependency audit: passed.
- Synthetic API, worker and PostgreSQL test schema were removed after the run.

The single Starlette `TestClient`/`httpx` deprecation warning is third-party
transition noise and does not affect acceptance.

## Remaining Gates

Local restart and retry behavior is verified. Production acceptance still needs a
hosted worker deployment, forced worker-restart exercise, live storage/scanner and
parser providers, live HAMIS staging fixtures, alert routing, queue-depth/lease-age
monitoring and an approved retention policy. Consent/training/placement HAMIS
mappings remain human-review items until programme ownership rules are approved.

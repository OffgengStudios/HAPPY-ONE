# Partnership and Document Acceptance

Acceptance date: 19 Oct 2026

Branch: `development`

## Scope

This checkpoint closes the local Demand gaps for partnership history and secure
agreement/job-description documents without creating a new product phase.

- Partnerships support controlled `TRAINING`, `RECRUITMENT` and `COMBINED` types,
  date-bounded periods, generated partnership codes and organization history.
- HAPPY UUIDs remain authoritative and existing singular partnership access stays
  backward compatible by projecting the current or latest period.
- Partnership agreements and vacancy job descriptions use immutable,
  owner-scoped versions in private object storage.
- Upload validation, malware-scan state, checksum verification and authorization
  are enforced server-side. Downloads fail closed until a document is available.
- Raw storage keys and checksums are not exposed by public API projections.
- Demand can manage both document families; Matching and Management receive only
  the explicitly granted read/download access.

Migration `0032_partner_docs` applies the schema and permission changes without
renumbering earlier revisions.

## Verification

The root `pnpm verify` command passed as one uninterrupted acceptance run:

- Python formatting: 182 files clean.
- Ruff and strict mypy: passed; mypy checked 116 source files.
- PostgreSQL/Alembic migration through `0032_partner_docs`: passed.
- Backend unit and live integration tests: 274 passed.
- JavaScript formatting, ESLint and workspace TypeScript: passed.
- Environment tests: 4 passed.
- Next.js production build: passed.
- Authenticated Playwright suite: 98 passed across desktop and mobile.
- Python dependency consistency and vulnerability audit: passed.
- JavaScript production dependency audit: passed.
- Synthetic browser API and PostgreSQL test schema were removed after the run.

The single Starlette `TestClient`/`httpx` deprecation warning comes from a
third-party transition and does not affect acceptance.

## Remaining Release Gates

This is local implementation acceptance, not production storage/scanner
acceptance. A real malware-scanning provider, hosted private object storage,
provider credentials, retention policy and operational upload/download UAT remain
required before production release. Existing live integration, backup-retention,
restore-exercise, MFA/SSO-provider and observability gates also remain open.

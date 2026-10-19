# Phase 0 Verification

Historical filename: this foundation work is **Phase 1** in the revised
[roadmap](20-IMPLEMENTATION-ROADMAP.md). Original evidence below retains its
historical numbering and results. No migration history was renumbered.

## Phase 1 Recheck: 07 Oct 2026

**Complete for the agreed local-development scope; no rebuild needed.**

- Focused foundation tests: 19 passed, including live PostgreSQL/private-S3 tests.
- Environment-loading tests: four passed.
- Live API liveness/readiness and web home: HTTP 200.
- Supplied request ID was preserved in the live API response.
- Alembic current revision: 0009_integration_readiness; no model/schema drift.
- App account has no superuser, database-creation, or role-creation privileges.
- Playwright live-shell checks passed at 1440x900 and 412x915: no page errors or
  horizontal overflow. Both screenshots were visually reviewed.
- Staging Compose/environment example and shared CI workflow remain present.

This focused recheck did not rerun the entire CI pipeline. The full 07 Oct
local CI result (133 backend, four environment, 14 browser tests, build and
dependency audits) is recorded in [integration readiness](27-INTEGRATION-READINESS.md).
Application code, existing migrations, IAM, Demand, and the Supply draft were
left unchanged. Live screenshots are in ignored .local/phase1-desktop.png and
.local/phase1-mobile.png.

Docker remains unavailable on this workstation. Container builds/execution,
hosted GitHub Actions, and staging deployment are still unverified, not new local
acceptance failures. The HTTPX TestClient deprecation warning remains non-blocking.

## Original Verification: 06 Oct 2026

Verified on 06 Oct 2026. Phase 0 is complete for the agreed local-development
scope. This is not a production-readiness or staging-deployment claim.

## Exit Criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Local stack boots | Pass | Next.js, FastAPI, project-local PostgreSQL 18 on 5433, and authenticated SeaweedFS 4.48 on 9000 |
| CI passes | Pass | Full `pnpm verify` exited 0; user selected local CI |
| DB migration runs | Pass | Alembic baseline `0001_foundation` applied; encoded connection passwords covered |
| Staging configuration exists | Pass | Environment example, app Dockerfiles, Compose configuration, and deployment runbook |

## Foundation Deliverables

- pnpm monorepo with API/web shells and shared config, UI, and type packages.
- Docker Compose infrastructure with loopback-only published development ports.
- FastAPI request IDs, versioned routing, and liveness/readiness endpoints.
- PostgreSQL connection, safe local provisioning, and Alembic migration baseline.
- Root environment loading, app overrides, and isolated explicit environment selection.
- Private S3 client, bucket setup, and native storage fallback for this workstation.
- Responsive Next.js shell, Tailwind tokens, and Lucide workstream icons.
- Shared local CI command and a GitHub Actions workflow using the same command.
- Separate database admin and non-superuser app credentials for fresh Compose volumes.

## Automated Results

`pnpm verify` completed successfully with:

- Python formatting and lint checks.
- Strict backend types: 20 source files.
- Backend tests: 19 passed, including 3 live PostgreSQL/S3 integration tests.
- JavaScript formatting, frontend lint, and workspace type checks.
- Environment-loading tests: 4 passed.
- Optimized Next.js production build.
- Playwright desktop and mobile tests: 2 passed using installed Microsoft Edge.
- Python dependency consistency and vulnerability audit: passed.
- JavaScript production dependency audit: no known vulnerabilities found.

The S3 integration test writes and reads a synthetic object, rejects anonymous
access, verifies a signed read, and removes the object. Database integration
uses a temporary table. No programme data was imported.

## Additional Checks

Both development and staging Compose configurations passed `config --quiet`.
The Compose initialization SQL was exercised against local PostgreSQL with a
temporary role/database: the app role owns its database and has no superuser,
database-creation, or role-creation rights. Temporary resources were removed.

Desktop/mobile screenshots were inspected for visible content, loaded styles,
icons, and layout. Screenshots are generated in ignored `apps/web/test-results/`.

## Boundaries

Docker is not installed on this workstation. Containers and Linux staging images
have not been built or run; configuration validation and native-stack verification
do not replace that deployment test. Staging is configured, not deployed.

No hosted GitHub Actions execution is claimed. Connect a repository to exercise
the workflow on Linux. Fresh-volume initialization does not alter existing
database accounts or volumes.

The backend test client emits an upstream HTTPX deprecation warning; all tests pass.
Authentication, authorization, and domain workflows were outside this original
foundation verification. The current IAM baseline belongs to Phase 2; see
[historical IAM evidence](25-PHASE-1-AUTH-IAM.md).
Production providers, SSO, branding, and programme policy remain open decisions.

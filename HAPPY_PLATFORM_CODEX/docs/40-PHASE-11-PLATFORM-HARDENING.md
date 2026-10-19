# Phase 11 - Platform Hardening

Local acceptance completed on 13 Oct 2026. This checkpoint hardens the existing
platform; it does not claim that a production environment has been deployed.

## Implemented

- API request IDs are validated and returned on every response.
- API access logs are structured JSON with route, status and duration data.
- API and web responses include restrictive browser security headers.
- production configuration rejects development credentials, insecure CORS,
  missing identity encryption material and weak lookup keys.
- PostgreSQL backup creation, checksum verification and isolated restore rehearsal
  are available through `pnpm db:backup`.
- migration `0019_hardening` adds indexes for the principal operational queries.
- accessibility checks cover sign-in and the principal role-aware workspaces at
  desktop and mobile viewports.
- the production runbook documents release, migration, backup, restore, rollback,
  incident response, secret rotation and routine operational checks.

## Recovery Evidence

The final local archive was checksum-verified and restored into a randomly named,
disposable database. The restored database reported Alembic revision
`0019_hardening`; the restore database was removed by the rehearsal command.

The restore implementation refuses application database targets and only creates
names matching `happy_restore_test_<random>`. An explicit maintenance-database
administrator URL is required.

## Verification

- backend suite: 254 passed against PostgreSQL and private object storage
- environment configuration suite: 4 passed
- browser suite: 94 passed across desktop and mobile
- automated accessibility matrix: 14 WCAG A/AA cases passed
- Ruff formatting/lint, strict mypy, Prettier, ESLint and TypeScript: passed
- Next.js production build: passed
- Python and production JavaScript dependency audits: no known vulnerabilities
- Alembic model drift check: passed at revision `0019_hardening`
- backup checksum verification and isolated restore rehearsal: passed

The verification components passed after the final fixes. They were exercised as
the same checks used by local CI; no hosted-CI or production deployment result is
claimed.

## Production Gates

The following operational decisions remain required before production release:

- hosting and managed-service providers
- approved RPO and RTO values
- alert destinations, escalation owners and release approvers
- production MFA provider configuration
- Supply privacy-notice, scanner and visual-acceptance rollout gates

These are deployment and programme-approval gates, not reasons to invent local
configuration. See [the production runbook](39-PRODUCTION-RUNBOOK.md).

## Result

Phase 11 is complete for the documented local scope. Phase 12 begins by inspecting
the real HAMIS/Kollekt implementation and defining an evidence-based integration
contract. No HAMIS synchronization or Google Sheets backend is implied here.

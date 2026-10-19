# Quality Baseline Restoration

Acceptance date: 18 Oct 2026

Branch: `development`
Starting revision: `defc1ca`

## Scope

This checkpoint restores the repository quality gates after the work-management,
TOTP MFA, parser-delivery, observability and OIDC additions. It does not introduce
a new product phase, renumber migrations, or claim production-provider readiness.

The generic Task and Handoff workspace now has its own `Tasks & Handoffs`
navigation destination. Existing role-specific `My Work` projections remain the
default experience for Demand, Supply, Matching, MERL, Marketing and Management.
Server-side permissions remain authoritative.

Marketing request and campaign commands now wait for vacancy, training and request
reference data before opening their editors. This prevents fast clients from
capturing an empty set of linked-record options while queries are still loading.

## Verification

The root `pnpm verify` command passed as one uninterrupted acceptance run:

- Python formatting: 180 files clean.
- Ruff and strict mypy: passed; mypy checked 115 source files.
- PostgreSQL/Alembic migration to `0031_oidc_sso`: passed.
- Backend unit and live integration tests: 273 passed.
- JavaScript formatting, ESLint and workspace TypeScript: passed.
- Environment tests: 4 passed.
- Next.js production build: passed.
- Authenticated Playwright suite: 98 passed across desktop and mobile.
- Python dependency consistency and vulnerability audit: passed.
- JavaScript production dependency audit: passed.
- Synthetic browser API and PostgreSQL test schema: removed after the run.

The remaining Starlette `TestClient`/`httpx` deprecation warning is third-party
transition noise and did not fail the suite. It should be removed during a future
dependency upgrade rather than suppressed locally.

## Remaining Release Gates

This result establishes a clean local quality baseline. It does not verify live
HAMIS or Employer Portal forwarding, a real CV parser/scanner, production OIDC or
MFA providers, hosted observability and alert delivery, scheduled off-site backup
retention, or a provider restore exercise. Those remain explicit deployment and
integration acceptance gates.

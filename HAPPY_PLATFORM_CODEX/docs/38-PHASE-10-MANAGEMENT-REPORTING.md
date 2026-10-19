# Phase 10 - Management + Reporting

Status: **Local functional acceptance complete.**

Date: 12 Oct 2026

## Implemented

- A server-authorized Management workspace exposes an attention summary,
  programme KPI overview, placement trend, full KPI catalogue, evidence
  drilldowns, data-quality summary, global targets and CSV exports.
- Every request uses an explicit inclusive date range. The initial calendar-year
  range is a UI convenience, not an approved reporting-period policy.
- KPI calculations implement the current dictionary for placements, vacancy
  headcount, matching conversion, employer turnaround, Supply completion/readiness,
  latest verified employment status and open duplicate suspects.
- Retention, completeness and marketing-attribution measures return explicit
  unavailable reasons because their programme rules are not approved. They are
  never silently presented as zero.
- Configured global targets and forecasts are stored data. Actual and non-negative
  gap are derived; no targets or forecast methodology are hard-coded.
- KPI cards link to bounded evidence rows. CSV exports use stable columns even
  when the selected period has no rows and create an audit event.
- Ordinary Management users can view and export non-sensitive reports. Global
  target management remains Admin-only. Sensitive export requires a separate
  permission and explicit privacy acknowledgement.

## API

- `GET /api/v1/reports/dashboard`
- `GET /api/v1/reports/kpis`
- `GET /api/v1/reports/kpis/{code}/drilldown`
- `POST /api/v1/reports/export`
- `POST /api/v1/reports/export-jobs`
- `GET /api/v1/reports/export-jobs`
- `GET /api/v1/reports/export-jobs/{id}`
- `GET /api/v1/reports/export-jobs/{id}/download`
- `GET /api/v1/reports/data-quality`
- `GET|POST /api/v1/reports/targets`
- `PATCH /api/v1/reports/targets/{id}`

## Database And Permissions

Migration `0018_reporting` adds `report_targets`, global period/KPI uniqueness,
controlled provenance constraints, `report:view` and `report_target:manage`.
Management receives report view/export. Admin retains target management and
sensitive-export authority. Existing operational tables remain the source of
actuals; reporting does not duplicate domain records or replace internal UUIDs.

## Verification

- Four focused PostgreSQL scenarios pass for formulas, evidence drilldowns,
  targets/gap/forecast, stable CSV, audit, unavailable KPIs and authorization.
- The complete backend regression executed 247 tests: 243 passed in the full run;
  the four tests blocked by an access-denied shared Windows temp directory were
  rerun with a workspace-local temp root, where all six configuration cases pass.
- Alembic applies through `0018_reporting` and reports no model/schema drift.
- Ruff, strict mypy, frontend lint, TypeScript, formatting and optimized Next.js
  build pass.
- The authenticated Management journey passes on desktop and mobile: view KPI,
  inspect evidence, open reports and download a bounded CSV.

## Open Programme And Delivery Inputs

- Official reporting periods/locked periods, target dimensions, forecast method,
  retention denominator/cadence, versioned completeness rules and campaign
  attribution remain programme decisions.
- Female/PWD denominator rules, sensitive-export approver workflow and deeper
  organization/region drilldown dimensions remain open.
- Immediate exports remain synchronous and capped at 5,000 evidence rows.
  Migration `0024_report_export_jobs` subsequently added requester-scoped full
  export jobs in private object storage. Local execution uses a replaceable
  in-process background adapter; production queue/recovery policy remains open.
- Central cross-workstream reporting is limited to Management/Admin. Operational
  roles keep their module dashboards until scoped report requirements are approved.

Phase 11 Platform Hardening is the next implementation phase.

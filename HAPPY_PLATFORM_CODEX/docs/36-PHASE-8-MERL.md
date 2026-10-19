# Phase 8 - M&E / MERL

Status: **Local functional acceptance complete.**

Date: 12 Oct 2026

## Implemented

- Follow-ups can be scheduled manually or from administrator-configured templates.
  No programme cadence is seeded or assumed.
- Due and overdue state is derived from the scheduled date at read time, so queues
  remain accurate across date boundaries without a background job.
- Completed follow-ups preserve contact result, notes, verifier and audit history.
- Outcomes are dated observations linked to authoritative participant and placement
  records. They do not overwrite prior outcomes.
- Every outcome appends employment-status evidence. Corrections preserve an
  append-only prior-value revision and require an optimistic record version.
- Current income is separately gated by `participant_sensitive:view` and
  `participant_sensitive:edit`; ordinary M&E access does not expose it.
- Data-quality issues support open, assignment and resolution workflows. A working
  outcome after a recorded employment end raises a conflict automatically.
- Dashboard counts cover follow-up queues, latest verified working state, impact
  story candidates and open data-quality issues.
- The role-aware web workspace provides Follow-ups, Outcomes, Data Quality and
  Dashboard views on desktop and mobile. API authorization remains authoritative.

## API

- `GET /api/v1/merl/dashboard`
- `GET|POST /api/v1/follow-ups`
- `GET /api/v1/follow-ups/{id}`
- `POST /api/v1/follow-ups/{id}/complete`
- `POST /api/v1/follow-ups/{id}/cancel`
- `GET|POST /api/v1/outcomes`
- `GET|PATCH /api/v1/outcomes/{id}`
- `GET|POST /api/v1/data-quality/issues`
- `POST /api/v1/data-quality/issues/{id}/assign`
- `POST /api/v1/data-quality/issues/{id}/resolve`
- `GET|POST /api/v1/follow-up-templates`
- `PATCH /api/v1/follow-up-templates/{id}`

## Database And Permissions

Migration `0016_merl` adds follow-up templates, follow-ups, historical outcomes,
append-only outcome revisions and data-quality issues. Existing placement and
participant UUIDs remain authoritative. Controlled provenance is inherited from
the shared record model.

The server enforces `follow_up:view/edit/configure`, `outcome:view/edit`, and
`data_quality:view/edit`. Management receives read-only operational visibility;
MERL receives normal workflow access; template configuration remains explicit
administrative access.

## Verification

- Four focused PostgreSQL integration scenarios pass for manual/template
  scheduling, completion, historical outcomes, employment evidence, sensitive
  income authorization, conflict detection, correction revisions and audit.
- The complete backend regression passes with 239 tests.
- Duplicate outcomes for one completed follow-up are rejected before the database
  constraint, and manually raised data-quality issues require a real entity.
- Ruff and strict mypy pass across 79 API source files.
- Frontend lint, TypeScript checks and optimized Next.js production build pass.
- The authenticated MERL journey passes in isolated desktop and mobile browser
  runs: schedule, complete, record outcome, mark impact story and inspect dashboard.
- Alembic applies through `0016_merl` and reports no model/schema drift.

## Open Programme Inputs

The official follow-up cadence and retention KPI denominator are still awaiting
programme approval. Templates allow those decisions to be configured later.
This phase does not invent them and does not claim production rollout approval.

Phase 9 Marketing is the next implementation phase.

# Phase 6 - Placement and First-Income Verification

Status on 10 Oct 2026: **complete for the local development scope.**

## Implemented

- Migration `0012_placement` adds authoritative placements, one first-income
  verification per placement, append-only placement history and append-only
  employment-status history with controlled provenance.
- A selected candidate can create one placement. Actual start is required before
  first-income scheduling, and candidate/placement states change atomically.
- Daily, weekly, biweekly and monthly payroll calculations are supported. Missing
  payroll rules require a manual due date and explicit exception reason.
- First-income queues derive upcoming, due and overdue states and expose payment
  delay and scheduling-exception actions.
- Human first-income confirmation requires `placement:confirm`, is idempotent,
  and is the only ordinary path to a confirmed placement.
- Confirmation correction requires `placement:correct_confirmation`, a reason
  and audit history. Later employment exit preserves historical `confirmed_at`.
- Vacancy headcount is derived from actual starts and confirmed placements;
  overfill requires the explicit override permission.
- Salary and received-income amounts are redacted without sensitive-participant
  permission. Placement search and participant placement history remain
  independently permission checked server-side.
- Responsive Placements and First Income views support intake, actual start,
  failed/cancelled starts, verification, delays/exceptions and employment end.

## Verification Evidence

`pnpm verify` passed on 10 Oct 2026 with 231 backend tests, four environment
tests and 72 desktop/mobile browser tests. Python/JavaScript formatting, Ruff,
mypy across 68 backend source files, workspace TypeScript, the Next.js production
build, migration application and both dependency audits passed. Alembic reports
no model drift, and the isolated browser API/schema was removed successfully.

The browser journey verifies selected candidate to placement, actual start,
calculated monthly first-income date, authorized first-income confirmation and a
later exit that retains the confirmed achievement on desktop and mobile. Backend
coverage verifies idempotency, stale writes, duplicate placement rejection,
salary redaction, privileged correction, audit events, append-only history,
headcount derivation and payroll calculations.

Phase 7 owns parser jobs and parser-result review. Phase 8 owns later follow-ups,
retention outcomes and MERL workflows; neither is folded into placement records.

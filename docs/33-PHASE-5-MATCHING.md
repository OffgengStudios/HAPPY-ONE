# Phase 5 - Matching

Status on 09 Oct 2026: **complete for the local development scope.**

## Implemented

- Migration `0011_matching`: candidate-vacancy relationships, active-pair uniqueness,
  screenings, employer decisions, interviews and chronological history indexes.
- PostgreSQL constraints for provenance, stage vocabulary, screening evidence,
  interview outcomes and audit actors; evidence/history rejects update and delete.
- Versioned APIs for guarded transitions, atomic bulk transitions, pre-screening,
  submission, interview attendance/rescheduling/outcomes and employer decisions.
- Submission reuses Supply onboarding/consent eligibility; actual starts and
  confirmed placements remain reserved for Phase 6.
- Initial responsive pipeline, candidate detail, interview day, dashboard and
  My Work views in the existing authenticated shell.
- Dashboard stage drill-downs, five My Work groups, desktop table/pipeline and
  mobile stacked-card views, and version-aware atomic bulk transitions.
- Effective-permission action controls, interview reschedule/cancel actions,
  candidate screening/decision/interview evidence and interview history.
- Deterministic advisory match strength with positive reasons, potential gaps,
  confidence and mandatory human review. Suggestions do not create records or
  perform state transitions.

## Verification Evidence

`pnpm verify` passed on 09 Oct 2026 with 229 backend tests, four environment
tests and 70 desktop/mobile browser tests. The run also passed Python and
JavaScript formatting, Ruff, mypy across 63 backend source files, workspace
TypeScript, the Next.js production build, migration application and Python/npm
dependency audits with no known vulnerabilities.

The browser journey exercises atomic bulk review, human pre-screen evidence,
onboarding/consent-gated submission, interview scheduling and rescheduling,
attendance, outcome, employer selection and responsive overflow checks on both
viewports. Backend coverage includes guarded transitions, vacancy-specific
declines, atomic stale-write rejection, append-only history, effective DENY
overrides and explained advisory matching. Synthetic API/schema cleanup passed.

No Phase 6 placement state can be entered through Matching. Actual start,
first-income verification and confirmed placement remain exclusively Phase 6.

Supply privacy-notice approval, operational scanning and user visual acceptance
remain rollout gates, not unfinished Matching behavior. No HAMIS, Employer Portal
or parser integration is connected.

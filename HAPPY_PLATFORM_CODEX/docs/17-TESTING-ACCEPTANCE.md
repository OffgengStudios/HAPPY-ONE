# Testing and Acceptance

## 1. Unit Tests

Required for:
- status-transition validators
- headcount calculations
- first-income date calculation
- placement confirmation rule
- permission decisions
- KPI formulas
- duplicate-normalization helpers

## 2. Integration Tests

Required for:
- API + PostgreSQL
- transaction rollback
- audit emission
- file metadata/storage abstraction
- background job integration
- auth + RBAC

## 3. E2E Critical Flows

### E2E-01 Employer to Vacancy
Create employer → partnership/MOU → create vacancy → activate.

### E2E-02 Participant Onboarding
Create participant → complete progressive onboarding → consent → CV ready → job ready.

### E2E-03 Submission Gate
Attempt submit incomplete participant → blocked → complete onboarding → submit succeeds.

### E2E-04 Matching to Interview
Match → pre-screen → qualify → submit → interview → employer decision.

### E2E-05 Placement
Select → start → first-income due → confirm first income → confirmed placement.

### E2E-06 Employment Exit
Confirmed placement → later exit → placement remains historical → retention/current status changes.

### E2E-07 M&E
Confirmed placement → follow-up → outcome → impact-story candidate.

### E2E-08 Marketing
Create request → campaign → review → publish → metrics.

### E2E-09 Permissions
Marketing user cannot access restricted participant fields.
Demand user sees aggregated supply but not unrestricted PII.
Admin can manage roles.

### E2E-10 Export
Authorized user exports permitted fields; unauthorized user rejected; audit emitted.

## 4. Acceptance Criteria — Dashboard

- role-specific KPI set
- role-specific work queues
- no sensitive data leakage
- KPI drill-down works
- loading/error/empty states exist

## 5. Acceptance Criteria — My Work

- current user's tasks filtered correctly
- overdue/due/upcoming classification correct
- completion updates record/task atomically
- team handoffs appear in correct queue

## 6. Acceptance Criteria — Participants

- duplicate check occurs before create
- phone stays string-normalized
- progressive save works
- onboarding completion validates required sections
- role-specific field projection works

## 7. Acceptance Criteria — Vacancies

- headcount cannot be negative
- outstanding is derived
- material changes are historized
- closure requires reason
- stale update protected

## 8. Acceptance Criteria — Placement

- actual start required for started
- first-income confirmation requires authorization
- confirm is idempotent
- confirmed placement immutable except privileged correction
- later exit does not delete confirmed_at

## 9. Accessibility Acceptance

- keyboard navigation works
- focus visible
- buttons/inputs labeled
- color not sole status signal
- mobile tap targets acceptable

## 10. Performance Acceptance

Exact numeric SLOs remain an operational decision, but implementation must:
- paginate large lists
- avoid N+1 queries
- index common filters
- avoid loading full datasets client-side

## 11. Local Browser Verification

The browser suite uses one worker, a bounded 60-second test budget and 15-second
assertion budget for live PostgreSQL/storage/API workflows on the local Windows
host. Composite workflows have explicit bounded allowances: 120 seconds for
the employer-to-vacancy flow and 90 seconds for Supply onboarding. This is a
test-runner allowance, not a production SLO, automatic retry or
relaxation of business rules. Assertions still verify actual persisted results,
permission denials, current record versions, focus and responsive geometry.
Layout checks wait for native surface animation to finish rather than using sleeps.
Normal and reduced-motion cases cover the prototype-aligned shell; changing the
preference must not discard an unsaved form. The HTML reference remains visual
material, not a source of synthetic production records or role assignments.

The current full regression passed 98 tests across desktop and mobile on
14 Oct 2026. It includes authenticated Supply, Matching, Placement, CV review,
MERL, Marketing, Training, Reporting and Employer Portal review/conversion
journeys plus automated WCAG A/AA checks for the role workspaces. A focused
Training-linked Marketing rerun also passed both projections on 15 Oct 2026. Each
browser API and PostgreSQL schema was disposable and removed after its run.

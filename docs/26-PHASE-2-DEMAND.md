# Phase 2: Demand

Historical evidence: this existing Demand baseline is now Phase 3 in the
[revised roadmap](20-IMPLEMENTATION-ROADMAP.md). Preserve its implementation and
original acceptance evidence. Placement work is now Phase 6.
The revised Phase 3 review is recorded in
[29-PHASE-3-DEMAND-ACCEPTANCE.md](29-PHASE-3-DEMAND-ACCEPTANCE.md).

Local Demand workflow baseline completed and verified on 06 Oct 2026.

## Delivered

- Employer create, list, detail, edit, duplicate review, and archive workflows.
- Immutable generated employer/vacancy codes and UUID identifiers.
- Employer Pipeline, Active, MOU Pending, Inactive, and All views.
- Contact create/edit, raw phone storage, Ghana/international E.164 normalization,
  normalized email, and an active-primary-contact partial unique index.
- Partnership stages, explicit MOU requirements, sent/signed dates, action owner,
  next action, staff-entered due dates, and priority.
- Vacancy create/edit, salary validation, locations, working conditions,
  headcount, ownership, confirmation, hold, cancellation, and closure workflows.
- Normalized requirement creation, editing, and archiving with typed operators,
  values, weights, and ordering.
- Material vacancy change history, reasons, and required audit events.
- Cursor-paginated APIs and readable employer/vacancy activity.
- Four Demand dashboard metrics with matching API filters and drill-downs.
- My Work: Overdue, Due Today, Upcoming, High Priority, and Recently Assigned.
- Desktop/mobile forms and record views with refresh, loading, empty, failure,
  stale-write review, and read-only permission states.

## Record Decisions

An employer has one current partnership in this v1 baseline. Creating an employer
creates its initial LEAD relationship in the same transaction. Relationship
status is authoritative on the partnership; employer responses project that
status instead of storing another independently editable copy. Audit events
retain relationship transitions.

The employer relationship owner and partnership action owner are distinct
responsibilities. Both initially use the employer's selected owner, but subsequent
assignment changes are explicit. Owner selectors expose only staff identifiers,
names, and assignment capabilities, not emails, password data, or account roles.

Employer names are not unique. Normalized-name collisions require an explicit
distinct-employer acknowledgement. No automatic merge occurs.

Edits include an expected version and the editable form fields. Read-only codes,
status, calculated headcount, and internal metadata cannot be mass-assigned.
Requirement writes use the parent vacancy version so concurrent requirement or
vacancy edits conflict. Employer-before-vacancy row locks serialize mutations
against employer archiving. Open vacancies block employer archiving.

Contacts can be deactivated. A new primary contact does not silently demote an
existing primary contact. There are no ordinary hard-delete endpoints.

## Workflow Defaults

The final MOU requirement policy by employer type is still open. Each employer
creation explicitly submits its MOU requirement; the UI initially selects
required. Changing the requirement needs a reason recorded in audit.

Skipping MOU stages is allowed only from INTERESTED when MOU is explicitly not
required. Required-MOU activation needs a signed date. MOU_SIGNED always needs a
signed date, even for an optional MOU. Reactivation from INACTIVE needs a reason.
These dates are staff-recorded metadata, not automated signature verification.

Vacancy confirmation is required by default. Set
`DEMAND_VACANCY_CONFIRMATION_REQUIRED=false` only when the intended operational
configuration allows DRAFT to ACTIVE directly. No separate programme approval
matrix or two-person approval policy has been inferred.

Closing/cancelling requires a seeded closure reason. Material edits and
requirement changes require a reason and produce immutable vacancy history.
Database triggers reject UPDATE/DELETE of that history, as with IAM audit events.

My Work derives actions from owned partnership records, avoiding a duplicate
editable task copy. Due dates are entered by staff; no follow-up cadence is
invented. Recently Assigned uses a seven-day engineering lookback and the
recorded owner-assignment timestamp. Existing unknown assignment timestamps
are not fabricated during migration.

Priority, salary frequency, and closure options are database-backed migration
seeds. Organization type, location, sector, and industry codes are captured
without inventing an official programme taxonomy.

## Permissions

Demand/Admin can manage employer contacts. Separate
`organization_contact:view` and `organization_contact:edit` grants prevent
general employer/vacancy readers from receiving contact details.

Matching receives vacancy creation/editing as specified by the baseline E grant.
Supply, MERL, Marketing, and Management retain vacancy read access. Restricted
employer access remains a vacancy's minimal employer-name projection for
Supply/Marketing; direct organization/contact endpoints are not granted.

Mutation endpoints also require the corresponding resource view permission.
An explicit view DENY cannot be bypassed through a mutation response.
Dashboard/My Work require Demand workspace and employer/partnership/vacancy
read permissions. Field projections use explicit allowlists.

## Metrics

- `DEMAND-ACTIVE-EMPLOYERS`: non-archived employers with ACTIVE partnerships;
  drill-down `GET /organizations?status=ACTIVE`.
- `DEMAND-MOU-PENDING`: non-archived employers with MOU_PENDING partnerships;
  drill-down `GET /organizations?status=MOU_PENDING`.
- `KPI-VAC-001`: required positions across ACTIVE, PARTIALLY_FILLED, ON_HOLD
  vacancies; drill-down `GET /vacancies?open_only=true`.
- `KPI-VAC-003`: summed outstanding positions across that same vacancy set and
  drill-down, using `max(required - started, 0)`.

Placement/start records do not exist until Phase 6. Started and confirmed counts
therefore currently return zero; they are not editable estimates or seeded
programme outcomes. Phase 6 must replace the headcount source with real placement
queries and retain the distinction between started and confirmed placements.
Fill-state transitions reject claims that lack recorded actual starts.

## Boundaries

Private MOU document uploads, document registry/scan/evidence flows, and document
tabs await the secured files module. No unverified document UUIDs, public file
links, or non-functional upload controls are exposed.

Supply/candidate pools, matching pipelines, placements, campaigns, management
reporting, and production deployment remain subsequent phases. There is no
WhatsApp integration, AI decision-making, or historical programme import.

## Verification

`pnpm verify` passed: 85 backend tests, four shared configuration tests, and
14 desktop/mobile browser tests. Strict backend type checking covered 37 source
files. Formatting, lint, frontend types, production build, dependency consistency,
and backend/frontend dependency audits passed. Alembic reported no schema drift.

Tests cover permission denials, MOU rules, contact uniqueness, vacancy transitions,
immutable history, CSRF, pagination, and concurrent edits (one success and one
version conflict). Desktop/mobile screenshots were inspected for readable,
non-overlapping record, history, dashboard, and My Work layouts.

Tests use isolated PostgreSQL schemas; browser fixtures are synthetic and do not
change the local administrator or create employer/vacancy test records in the
application schema. The browser test server and its schema are removed on exit.

On 07 Oct 2026, the restarted development stack passed readiness and a real local
administrator sign-in through the web proxy. Organizations, vacancies, owner
options, reference data, dashboard, and My Work all returned successfully. The
smoke session was logged out; no isolated test schemas remained, and the
application still contained zero employers and zero vacancies.

Migrations extend the immutable IAM seed through versioned revisions. The
schema revision at the original acceptance was `0006_mou_signed_date`.
Later Supply-draft and integration-readiness revisions remain intact; the
Phase 3 review does not renumber or rewrite migration history.

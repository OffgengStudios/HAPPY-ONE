# Phase 3: Demand Acceptance

Review date: 07 Oct 2026. This is the revised roadmap's Demand checkpoint,
not a replacement for the original
[Demand baseline evidence](26-PHASE-2-DEMAND.md).

Status: local Demand workflow baseline accepted, with the explicit deferred
boundaries below. This is not production deployment acceptance.

## Existing Implementation

Preserved employer CRUD/archive and duplicate acknowledgement; contact
normalization and primary-contact constraints; partnership/MOU transitions,
dates, ownership and actions; vacancy confirmation, hold, closure, salary,
headcount and requirements; immutable material-change history; dashboard,
My Work and desktop/mobile permission-aware workflows.

The current database remains at `0009_integration_readiness`. No migrations,
primary keys, permission grants, account credentials, or domain records change
as part of this review. The existing Supply draft remains unaccepted.

## Changes

Organization activity previously included linked partnership and contact events
even when their respective view permissions were denied. The Demand activity
service now applies those permissions in SQL before cursor pagination and
serialization. Organization activity still requires `organization:view`.
Authorized Demand users retain the same complete activity feed; restricted
readers receive only events for resources they may view.

Organization/vacancy activity now returns `actor_type` alongside `actor_id`,
preserving USER UUID attribution and future SYSTEM/INTEGRATION identities.
Audit attribution does not authenticate an integration or grant any access.
This is an additive API field and does not require frontend changes.

Changes are limited to Demand service/routes, regression tests, and docs.
No HAMIS, Employer Portal, Google Sheets, or CV Parser client is implemented.

## Verification

Six new PostgreSQL regression cases cover all four contact/partnership
permission combinations with one-item cursor pages, denial of the parent
organization permission, and human/system/integration actor serialization for
both organization and vacancy activity. Synthetic integration actors are test
fixtures only, not service identities or synchronization implementations.

Before the fix, three restricted-feed cases exposed unauthorized events and
both actor cases lacked `actor_type`; the unrestricted-feed case passed.
After the fix, all 142 backend tests passed, including the 38 Demand cases.
Backend lint and strict typing of 54 source files passed.

`pnpm verify` passed: 142 backend tests, four environment tests and 14
desktop/mobile browser tests. Python/JavaScript formatting, lint, workspace
types, production build, dependency consistency and both dependency audits
passed. Alembic reported no model/schema drift at revision 0009.

Desktop/mobile employer, vacancy-change, dashboard and My Work screenshots
were visually reviewed for readable, non-overlapping layouts. Browser tests
exercise employer/contact/MOU/vacancy/requirement workflows, closure, KPI
drill-downs and read-only access. Test schemas and the temporary browser API
were removed on completion.

The restarted development stack passed private-storage/database readiness and
original-admin sign-in through the web proxy. Organization/vacancy lists,
Demand dashboard/My Work, owner options and reference data returned 200.
Logout returned 204 and the next account request returned 401. No credentials
were printed or changed. The working schema retained one user, seven roles,
zero organizations/vacancies/participants/external references, and zero test
schemas. This smoke check adds only ordinary session/login/logout audit records.

## Explicit Boundaries

Private MOU uploads/document evidence remain deferred until the secured-file
workflow is accepted. Signed dates are staff-recorded metadata, not evidence
of automated signature verification. Final MOU policy and follow-up cadence
remain programme-owner decisions.

Actual starts and confirmed placements await Phase 6. Current started/confirmed
counts are zero rather than invented estimates. Fill transitions still reject
claims without actual starts; Phase 6 must replace the headcount query source.

Hosted CI, Docker execution, staging deployment, production MFA/SSO and
production operational acceptance remain unverified. Supply onboarding policy
and private-file scanner configuration are not silently approved here.

Next checkpoint: Phase 4 Supply. Preserve and finish
its existing backend draft, then add dedicated tests and frontend workflows.

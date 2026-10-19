# Implementation Roadmap

Decision recorded 07 Oct 2026: **HAPPY first, integrations second.**
The core HAPPY platform remains authoritative. CV Parser is the first processing
integration; HAMIS/Data Collection and Employer Acquisition Portal come later.

## Numbering and Existing Work

The sequence below supersedes the original phase numbering. All thirteen phases
are accepted for their documented local-development scope. The current work is
production/staging readiness against the explicit provider, policy and live-
integration gates; it is not a new numbered implementation phase.
Do not restart IAM or discard work that already exists.

Quality checkpoint 18 Oct 2026: the post-Phase-13 worktree passes the complete
local gate at migration `0031_oidc_sso`: 273 backend tests, four environment
tests, 98 authenticated desktop/mobile browser tests, static checks, production
build and dependency audits. See
[quality baseline restoration](49-QUALITY-BASELINE-RESTORATION.md).

Demand document checkpoint 19 Oct 2026: migration `0032_partner_docs` adds typed,
date-bounded partnership history and versioned private partnership agreements and
vacancy job descriptions. The complete local gate passes with 274 backend tests,
four environment tests and 98 authenticated desktop/mobile browser tests. See
[partnership and document acceptance](50-PARTNERSHIP-DOCUMENT-ACCEPTANCE.md).

Durable-work checkpoint 19 Oct 2026: migrations `0033_durable_jobs` and
`0034_hamis_worker` move report exports and HAMIS application out of the API
process and combine them with the existing leased CV parser runner. PostgreSQL
leases, bounded retries and expired-lease recovery are implemented; hosted worker
restart and provider UAT remain open. The complete gate passes with 276 backend,
four environment and 98 authenticated desktop/mobile browser tests. See
[durable background processing acceptance](51-DURABLE-BACKGROUND-PROCESSING.md).

Historical evidence files retain their names: old Phase 0 is now Phase 1, old
Phase 1 IAM is now Phase 2, and old Phase 2 Demand is now Phase 3. Existing
migration revisions, seeds, UUIDs, and completed work are not renumbered.

## Phase 1 - Platform Foundation

Deliver: monorepo, Docker Compose, FastAPI/Next.js shells, PostgreSQL, Alembic,
configuration, request IDs, health checks, local CI, and base design tokens.

Status: **Complete for local development on 06 Oct 2026.** Hosted CI, staging
deployment, and production operations are not claimed verified.
Rechecked on 07 Oct 2026: 19 foundation tests, four environment tests, live
API/database/storage checks, and desktop/mobile shell checks passed. No rebuild
or application changes were needed.
See [historical foundation evidence](24-PHASE-0-VERIFICATION.md).

## Phase 2 - Authentication + RBAC

Deliver: individual accounts, password authentication, users, roles, permissions,
role assignments, explicit overrides, sessions, MFA-ready architecture,
server-side authorization, role-aware frontend, and append-only audit foundation.

The local password-authentication baseline was completed on 06 Oct 2026.
MFA is provider-ready, not a configured production factor.
Role determines the default experience; permission determines actual access.
See [historical IAM evidence](25-PHASE-1-AUTH-IAM.md).

Current extension: generic external references, controlled record provenance,
non-user audit actors, and small future integration boundaries.
See [integration-readiness contract and verification](27-INTEGRATION-READINESS.md).
Status: **Extension verified locally on 07 Oct 2026.** Full local CI passed:
133 backend, four environment, and 14 desktop/mobile browser tests.
No HAMIS, Employer Portal, or CV Parser connection is part of this phase.

Status: **Local Phase 2 acceptance complete on 07 Oct 2026.** A follow-up review
fixed pending MFA challenge invalidation on password reset/deactivation and
verified concurrent revocation. Full CI passed with 136 backend, four environment,
and 14 browser tests. Production MFA remains provider-unconfigured.
See [current Phase 2 acceptance](28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md).

## Phase 3 - Demand

Deliver: organizations, employer contacts, partnerships/MOUs, employer pipeline,
vacancies, requirements, change history, dashboard, and My Work.

Status: **Existing local workflow baseline verified on 06 Oct 2026.** Preserve it.
Status: **Local Phase 3 workflow acceptance complete on 07 Oct 2026.** The review
fixed related-event authorization in organization activity and preserved actor
types in activity responses. Full CI passed: 142 backend, four environment,
and 14 desktop/mobile browser tests; no migration or model drift.
Versioned private MOU and job-description workflows passed local acceptance on
19 Oct 2026; production scanner/provider acceptance remains open. Placement-derived
counts were delivered in Phase 6. See [historical Demand evidence](26-PHASE-2-DEMAND.md).
See [current Demand acceptance and boundaries](29-PHASE-3-DEMAND-ACCEPTANCE.md).

## Phase 4 - Supply

Deliver: Person/Participant, progressive onboarding, versioned consent, duplicate
checks, private CV upload/versioning, readiness, dashboard, and My Work.

Status: **Functional local checks passed; visual acceptance remains open.** The existing
backend draft is preserved, staff frontend and dedicated coverage are now added,
and revision 0010 strengthens identity uniqueness. Approved onboarding policy,
notice and operational scanner verification remain outstanding for rollout.
Full local CI passed on 07 Oct 2026: 219 backend, four environment, and 48
desktop/mobile browser tests at the preceding checkpoint. The user has now
confirmed Jobberman blue-accent recruitment styling with fluid UI motion and
supplied the role-based v4 HTML prototype as its visual reference.
That shell/palette direction is implemented and verified. User visual review
remains open, but is not treated as a request to pause the standing goal to build
the phases in order. Development proceeds without claiming visual approval or
relaxing programme policy, consent, scanner or production-release gates.
The documented compact mobile header, bottom navigation and More sheet are
verified locally; desktop retains its sidebar. Official logo/font choices and
final visual acceptance remain open, rather than the overall colour direction.
See [prototype adaptation and functional boundaries](32-VISUAL-REFERENCE.md).
The prototype-aligned checkpoint passed full local CI on 08 Oct 2026: 219 backend,
four environment and 66 desktop/mobile browser tests, plus dependency audits.
Migration 0010 remains unchanged and has no model drift. This verification does
not replace user visual acceptance or the documented policy/scanner rollout gates.
The subsequent intake-owner permission correction passed full CI on 08 Oct 2026:
220 backend, four environment and 68 browser tests, with clean dependency audits.
Supply creators with editing denied can create unassigned participants rather
than defaulting to an ineligible owner; server authorization remains unchanged.
The account menu and permission-aware Participants/Employers/Vacancies search
are implemented and passed the fresh full CI checkpoint. No migration, permission
catalog or authentication flow was replaced. Shared search will gain placement
and campaign groups when their domain services exist in Phases 6 and 9.
See [Supply implementation and gates](30-PHASE-4-SUPPLY.md).

## Phase 5 - Matching

Deliver: candidate-vacancy relationships, guarded transitions, pre-screen,
pipeline, interviews, employer decisions, dashboard, and My Work.
Employer submission requires completed onboarding and required recorded consent.

Status: **Local Phase 5 acceptance complete on 09 Oct 2026.** Candidate
relationships reuse existing Participant/Vacancy records and the permission
catalog. Migration 0011 follows 0010 without rewriting history. Full local CI
passed with 229 backend, four environment and 70 desktop/mobile browser tests,
plus clean dependency audits. Actual start and first-income confirmation remain
in Phase 6. See [Phase 5 acceptance evidence](33-PHASE-5-MATCHING.md).

## Phase 6 - Placement + First-Income Verification

Deliver: placements, actual-start confirmation, payroll rules, first-income
scheduling, verification queue, confirmed-placement rule, and employment-end flow.
Extend shared search with permission-filtered placement results.

**Confirmed Placement = Actual Start + Verified First Monthly Income.**
Employment ending must not erase historical placement outcomes.

Status: **Local Phase 6 acceptance complete on 10 Oct 2026.** Migration 0012,
placement/start workflows, payroll scheduling, first-income queues, privileged
confirmation/correction, employment end, derived vacancy headcount and placement
search are implemented. Full local CI passed with 231 backend, four environment
and 72 desktop/mobile browser tests plus clean dependency audits. See
[Phase 6 acceptance evidence](34-PHASE-6-PLACEMENT-FIRST-INCOME.md).

## Phase 7 - CV Parser Integration

First real integration: adapt the existing parser, do not copy its repository.
Use private document IDs/versions, parser jobs, failure states, separate results,
extracted values/confidence, human review, approved domain updates, and audit.

Parser output is assistive and non-authoritative. Never automatically overwrite
participant records. Core staff workflows must remain usable if parsing fails.

Status: **HAPPY-side local acceptance complete on 11 Oct 2026; real adapter
transport pending.** Migrations 0013-0015, parser jobs, immutable advisory results,
append-only human review, permissions, audit events and Supply review UI are in
place. No guessed external client was added. See
[Phase 7 acceptance and external gate](35-PHASE-7-CV-PARSER.md).

## Phase 8 - M&E / MERL

Deliver: follow-ups, outcomes, employment history, data-quality issues, dashboard,
and impact-story identification.

Status: **Local Phase 8 functional acceptance complete on 12 Oct 2026.** Migration
0016, configurable/manual follow-ups, historical outcomes, employment evidence,
data-quality workflow, impact-story identification, dashboard and role-aware web
workspace are implemented. The official follow-up cadence and retention KPI
denominator remain open programme inputs and were not invented. See
[Phase 8 acceptance evidence](36-PHASE-8-MERL.md).

## Phase 9 - Marketing

Deliver: requests, campaigns, assets, impact stories, permission-limited
participant projections, and dashboard.
Extend shared search with permission-filtered campaign results.

Status: **Local Phase 9 functional acceptance complete on 12 Oct 2026.** Migration
0017, requester-scoped requests, campaign production, reviewed assets, manual
metrics, consent-gated impact stories, restricted projections, dashboard and
campaign search are implemented. External channels and unresolved programme
approval/attribution policy were not invented. See
[Phase 9 acceptance evidence](37-PHASE-9-MARKETING.md).

## Phase 10 - Management + Reporting

Deliver: KPI services, drill-down, targets, programme performance, authorized
exports, and management dashboard.

Status: **Local Phase 10 functional acceptance complete on 12 Oct 2026.**
Migration 0018, KPI services, bounded evidence drilldowns, stored global targets,
audited CSV exports, data-quality summaries and a responsive Management workspace
are implemented. Unapproved retention, completeness and campaign-attribution
rules remain explicitly unavailable rather than guessed. See
[Phase 10 acceptance evidence](38-PHASE-10-MANAGEMENT-REPORTING.md).

## Phase 11 - Platform Hardening

Deliver: security/performance reviews, accessibility, UAT, backup/restore tests,
production runbook, and release-readiness verification.

Status: **Local Phase 11 acceptance complete on 13 Oct 2026.** Request and browser
security controls, production configuration guards, query indexes, accessibility
coverage, backup verification, isolated restore rehearsal and an operational
runbook are implemented. Full acceptance evidence records 254 backend tests,
four environment tests, 94 browser tests, clean static/build/dependency checks,
no migration drift and a successful restore at revision `0019_hardening`.
Production provider, RPO/RTO, alert-routing and MFA decisions remain deployment
gates. See [Phase 11 acceptance evidence](40-PHASE-11-PLATFORM-HARDENING.md).

Post-acceptance audit remediation added the previously omitted first-class Training
domain in migration `0020_training`. Its 256-test backend checkpoint, no-drift
result and restore evidence are recorded in
[the audit resolution](41-POST-HARDENING-AUDIT-RESOLUTION.md). This does not change
the phase numbering or the integration sequence.

Completion-audit follow-up subsequently added the permission-aware Training web
workspace and persisted asynchronous reporting exports in migrations
`0024_report_export_jobs` and `0025_report_export_actor_fks`. Verification passed
265 backend tests, a 98-test full
desktop/mobile browser run after Training, and the focused prepared-export browser
journey. Production queue provider/recovery policy remains a deployment decision.
See [completion audit follow-up](44-COMPLETION-AUDIT-FOLLOW-UP.md).

The same follow-up now closes the deferred Marketing-to-Training link in forward
migrations `0026_marketing_training_links` and `0027_marketing_training`, with
focused API and desktop/mobile browser acceptance. A provider-specific Render web/API
and Neon PostgreSQL deployment is prepared in root `render.yaml`; provisioning and
production gates remain pending. See
[the Render/Neon runbook](45-RENDER-NEON-DEPLOYMENT.md).

## Phase 12 - HAMIS / Data Collection Integration

Inspect the real system before selecting API contracts, push/pull/webhooks,
synchronization, conflict handling, or source-of-truth rules.
Map external identifiers through generic references into existing HAPPY services
and domain APIs. Internal UUIDs remain authoritative.
No Google Sheets backend, automatic historical import, or fake staff identities.
User-supplied sources are recorded in the integration-readiness document.

Inspection started from Kollekt repository revision
`0389cbac919844a2e13b34ea74b2775a03ce005a`. The repository contains a static PWA,
an IndexedDB offline queue and a Google Apps Script backend that writes participant,
consent, capacity-building, placement and audit sheets. Phase 12 must replace that
transport with an approved authenticated integration boundary into existing HAPPY
services; spreadsheet IDs and client-supplied actor strings are not trusted identity
or authorization contracts.

Status: **Local Phase 12 adapter acceptance complete on 13 Oct 2026.** Migrations
`0021_hamis` and `0022_hamis_encryption` add authenticated machine events,
idempotency, encrypted staging, integration-aware audit, controlled participant
creation, external references and review-first updates. Full backend verification
passed 259 tests with no migration drift. Production Apps Script deployment,
credential provisioning and staging UAT remain external gates. See
[Phase 12 acceptance evidence](42-PHASE-12-HAMIS-INTEGRATION.md).

## Phase 13 - Employer Acquisition Portal Integration

Inspect the real portal contract first. Map through HAPPY authorization and
business rules into the same organizations, contacts, partnerships, MOUs, and
vacancies used internally. Do not create a second authoritative employer database.

Status: **Local Phase 13 adapter acceptance complete on 14 Oct 2026.** Migration
`0023_employer_portal` adds an authenticated, encrypted and idempotent submission
inbox. Demand/Admin review converts accepted records into the existing employer
domains with authoritative HAPPY UUIDs, provenance, external references and
integration-aware audit. Verification passed 262 backend and 96 desktop/mobile
browser tests, static/build checks, no-drift migration checks and an isolated
restore at revision `0023_employer_portal`. Live Apps Script forwarding, staging
UAT and production operations remain deployment gates. See
[Phase 13 acceptance evidence](43-PHASE-13-EMPLOYER-PORTAL-INTEGRATION.md).

All thirteen planned phases now have local implementation acceptance for their
documented scope. External provider, policy and live-integration gates remain
explicitly tracked and are not represented as production acceptance.

## Future Integrations

Introduce adapters only against inspected, approved contracts. External metadata
is not a source of permissions or authoritative business decisions.

## Task Granularity

Each task must be vertically testable: schema/migration, service rules,
permissions, API, audit, UI where relevant, and focused tests.
Do not build speculative clients or batches of unverified domain models.

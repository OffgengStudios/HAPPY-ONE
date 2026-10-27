# HAPPY Management Platform

Greenfield implementation of the HAPPY Management Platform.
Run an optimized local build with `pnpm local:production build` followed by
`pnpm local:production start`. See the
[local startup guide](../docs/LOCAL-PRODUCTION.md) for environment selection,
addresses and lifecycle commands.

Current release: **`1.0.0-rc.1`**. The product uses Semantic Versioning while the
backward-compatible HTTP contract remains under **`/api/v1`**. See the
[versioning and release policy](docs/47-VERSIONING-AND-RELEASES.md).
The [production launch package](../docs/PRODUCTION-LAUNCH.md) contains the complete
ecosystem deployment candidate, configuration inventory and release gates. Use
`pnpm release:preflight` with the intended production environment to check required
configuration without printing credentials or changing provider resources.

Current evidence-based status and release blockers are recorded in the
[Operations Platform readiness audit](docs/48-OPERATIONS-READINESS-AUDIT.md).
The latest local quality baseline is recorded in
[Quality Baseline Restoration](docs/49-QUALITY-BASELINE-RESTORATION.md).
The subsequent Demand document checkpoint is recorded in
[Partnership and Document Acceptance](docs/50-PARTNERSHIP-DOCUMENT-ACCEPTANCE.md).
The durable execution checkpoint is recorded in
[Durable Background Processing Acceptance](docs/51-DURABLE-BACKGROUND-PROCESSING.md).

HAPPY first, integrations second. All thirteen phases have local implementation
acceptance for their documented scope. Phase 7's HAPPY-side parser job, advisory
result and human-review workflow is accepted; the real parser transport remains a
deployment gate. Phase 12's local HAMIS adapter and Phase 13's local Employer
Acquisition Portal adapter are accepted.
Visual acceptance and policy/scanner rollout gates remain open.
CV Parser is Phase 7; HAMIS is Phase 12;
Employer Acquisition Portal is Phase 13. See the revised
[roadmap](docs/20-IMPLEMENTATION-ROADMAP.md) and
[integration-readiness contract](docs/27-INTEGRATION-READINESS.md).

The implementation specification lives in `docs/`. Start with:

1. `docs/00-CODEX-START-HERE.md`
2. `docs/20-IMPLEMENTATION-ROADMAP.md`
3. The module-specific specification for the task

## Local Setup

```bash
pnpm install
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e apps/api[dev]
```

On Linux/macOS, use `.venv/bin/python` instead of `.venv/Scripts/python`.
The pnpm API commands automatically use the project virtual environment.

Create a root `.env` from `.env.example`. The API, migrations, and web app load
root configuration. App-local files can override it; process variables take
precedence. `HAPPY_ENV_FILE` selects an isolated environment file for API and web.

With Docker installed, start infrastructure:

```bash
docker compose up -d postgres object-storage
```

If PostgreSQL is already installed locally, use that server instead of starting
the Docker PostgreSQL container on the same port. Set `POSTGRES_ADMIN_PASSWORD`
in the root `.env` to the password chosen during PostgreSQL installation, then run:

```bash
pnpm db:setup
pnpm api:migrate
```

`db:setup` creates the role and database from `DATABASE_URL` only if they are
missing. It preserves existing credentials and data. The API uses the app account,
not the admin account. Remove `POSTGRES_ADMIN_PASSWORD` after setup.

Alternatively, use an isolated project-local database with the installed PostgreSQL
binaries. Set `DATABASE_URL` to
`postgresql+psycopg://happy:happy_dev_password@127.0.0.1:5433/happy` and
`POSTGRES_PORT=5433` in `.env`, then run:

```bash
pnpm db:local
pnpm api:migrate
```

This stores database files and a generated local admin password in ignored
`.local/postgres/`, binds to loopback only, and creates a non-superuser app account.
Use `pnpm db:local:status` to check the server and `pnpm db:local:stop` to stop it.
Run `pnpm db:local` again after reboot. Use one database option at a time.

For native local S3-compatible storage without Docker:

```bash
pnpm storage:install
pnpm storage:local
```

The pinned, checksum-verified SeaweedFS binary and data stay in ignored `.local/`.
The S3 endpoint is `http://localhost:9000`; authentication is required and the
application bucket is private. Use `pnpm storage:stop` to stop it and
`pnpm storage:local` after reboot. Keep these services on loopback.

Run the API:

```bash
pnpm api:dev
```

Run the web app:

```bash
pnpm web:dev
```

Create, verify and safely rehearse a PostgreSQL backup with `pnpm db:backup`.
See the [production runbook](docs/39-PRODUCTION-RUNBOOK.md); restore tests can only
create randomly named `happy_restore_test_*` databases through an explicit
maintenance-database admin URL.

Phase 11 local hardening is accepted: 254 backend tests, four environment tests,
94 browser tests, static/build/dependency checks, migration-drift verification and
an isolated PostgreSQL restore at `0019_hardening` passed. See the
[Phase 11 acceptance report](docs/40-PHASE-11-PLATFORM-HARDENING.md). Production
provider, RPO/RTO, alert-routing and MFA choices remain release gates.

A post-hardening audit added the missing first-class Training domain in migration
`0020_training`. The expanded backend suite passed 256 tests, Alembic found no
model drift, and a fresh verified archive restored successfully at that revision.
See [the audit resolution](docs/41-POST-HARDENING-AUDIT-RESOLUTION.md). Training is
now a dedicated tested domain rather than participant summary text.

The Phase 12 HAMIS adapter uses a distinct machine credential, idempotent events,
encrypted source payloads, integration-aware audit actors and generic external
references. The full backend suite passed 259 tests at migration
`0022_hamis_encryption`. See the
[Phase 12 acceptance report](docs/42-PHASE-12-HAMIS-INTEGRATION.md). A live Apps
Script deployment remains a production integration gate.

Durable background processing now commits report exports and HAMIS events before
execution and runs them with CV parser jobs through `pnpm background:worker`.
PostgreSQL leases, bounded retries and expired-lease recovery make worker restarts
safe; live provider and staging restart UAT remain release gates.

Phase 13 accepts encrypted, idempotent Employer Portal submissions under a
separate machine identity and converts staff-approved records into the existing
Organization, Contact, Partnership, Vacancy and Requirement domains. The current
checkpoint passed 262 backend tests and 96 desktop/mobile browser tests, clean
static/build checks, Alembic no-drift at `0023_employer_portal`, and a fresh
checksum-verified isolated restore at that revision. See the
[Phase 13 acceptance report](docs/43-PHASE-13-EMPLOYER-PORTAL-INTEGRATION.md).
Live Apps Script forwarding, staging UAT, provider backup scheduling, off-site
retention and approved RPO/RTO remain production gates.

Completion-audit follow-up added a dedicated Training workspace and persisted
full report-export jobs in migrations `0024_report_export_jobs` and
`0025_report_export_actor_fks`. The current
backend suite passes 265 tests; the expanded full browser run passes 98 tests,
and the prepared-export desktop/mobile journey passes separately. Immediate
exports remain bounded for responsiveness, while full exports use private object
storage and requester-scoped job/download APIs. The local in-process executor is
replaceable; production queue/recovery policy remains an infrastructure decision.
See [completion audit follow-up](docs/44-COMPLETION-AUDIT-FOLLOW-UP.md).

Training-linked Marketing requests and campaigns are now implemented in migrations
`0026_marketing_training_links` and `0027_marketing_training`, with server-side
lineage validation and passing desktop/mobile coverage.

## Authentication

After migrations, create the first administrator explicitly:

```bash
pnpm iam:bootstrap --email administrator@example.org
```

The CLI prompts for a 12-128 character password. In loopback development,
`--local` generates ignored local credentials; `--password-file` accepts a
local file without exposing the password in command-line arguments.
Bootstrap refuses to run once accounts exist. Manage further accounts and roles
from the signed-in administration screens.

Open `http://localhost:3000`. Authentication uses a same-origin API proxy and
HttpOnly sessions. `API_CORS_ORIGINS` must include the exact web origin.
Configure `API_INTERNAL_URL` for a different backend; it is server-only.
See [docs/25-PHASE-1-AUTH-IAM.md](docs/25-PHASE-1-AUTH-IAM.md) for security controls,
MFA-provider boundaries, and verification.
The revised [Phase 2 acceptance review](docs/28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md)
also covers account-wide invalidation of pending MFA challenges on password
reset/deactivation. Production MFA remains unconfigured.

## Demand

Phase 3 provides employers, contacts, partnership/MOU stages, vacancies,
requirements, immutable change history, and Demand Dashboard/My Work. Access is
enforced by the API, with read-only projections for other workspaces.
See [docs/26-PHASE-2-DEMAND.md](docs/26-PHASE-2-DEMAND.md) for verification,
workflow defaults, and the later files/placement integration boundaries.
The [current Phase 3 acceptance](docs/29-PHASE-3-DEMAND-ACCEPTANCE.md) also
verifies permission-filtered related activity and integration-aware actor
attribution. Private MOU files and placement-derived counts remain deferred.

## Supply

Phase 4 adds staff participant intake, progressive onboarding, consent,
readiness, assignment, private CV versions, dashboard and My Work. Programme
policy and file-scan gates remain enforced server-side; no spreadsheet data
or external integrations are imported. See [Supply implementation and rollout
gates](docs/30-PHASE-4-SUPPLY.md). Functional local checks passed; visual
acceptance remains open following the theme feedback.
The user-supplied participant headers are the Supply field inventory, with
protected/derived fields and unresolved semantics recorded in the
[field mapping](docs/31-SUPPLY-FIELD-INVENTORY.md).
That document also records a read-only Kollekt consent/field review. Existing
consent wording was found; approval to reuse it remains pending, with no HAMIS
connection or data import.

Supply intake defaults ownership only when the server's eligible-owner options
include the creator. Workspace access does not override a denied edit permission;
otherwise authorized intake can remain unassigned. Ordinary intake and quick-add
share the staff-options wait/retry/cancel flow. The permission follow-up passed
the full local checkpoint below.

## Verification

Current quality checkpoint (19 Oct 2026): root `pnpm verify` passes at migration
`0034_hamis_worker` with 276 backend tests, four environment tests, 98 authenticated
desktop/mobile browser tests, clean Python and frontend static checks, a production
web build, and clean Python/JavaScript production dependency audits. Demand now
supports typed partnership periods and history plus versioned, private partnership
agreements and vacancy job descriptions with scan-gated downloads. Generic Tasks
and Handoffs retain a separate permission-aware workspace while each operational
role keeps its established My Work projection. See the
[latest acceptance evidence](docs/51-DURABLE-BACKGROUND-PROCESSING.md). Live provider,
integration, backup-retention and restore-exercise gates remain open.

Phase 10 functional acceptance (12 Oct 2026): migration `0018_reporting`, KPI
services, evidence drilldowns, stored global targets/forecasts, audited bounded
CSV exports, data-quality summaries and the Management workspace are implemented.
The focused reporting backend scenarios and authenticated desktop/mobile journey
pass; Ruff, strict mypy, frontend lint, TypeScript, formatting and production
build are clean. Policy-dependent KPIs remain explicitly unavailable until their
rules are approved. See [Phase 10 evidence](docs/38-PHASE-10-MANAGEMENT-REPORTING.md).

Phase 9 functional acceptance (12 Oct 2026): migration `0017_marketing`,
requester-scoped marketing requests, campaign production/assets/metrics,
consent-gated impact stories, restricted participant projections, dashboard and
campaign search are implemented. All 243 backend tests and the authenticated
desktop/mobile Marketing journey pass, with clean static/build checks. External
publishing channels and unresolved approval/attribution policy were not invented.
See [Phase 9 evidence](docs/37-PHASE-9-MARKETING.md).

Phase 8 functional acceptance (12 Oct 2026): migration `0016_merl`, follow-up
queues, historical outcomes, employment evidence, sensitive-income authorization,
data-quality workflow, impact-story identification and the MERL workspace are
implemented. All 239 backend tests, four focused PostgreSQL scenarios and the authenticated desktop/mobile
MERL journey pass; Ruff, strict mypy, frontend lint, TypeScript and production build
are clean. The official cadence and retention denominator remain open programme
inputs. See [Phase 8 evidence](docs/36-PHASE-8-MERL.md).

Phase 7 acceptance (11 Oct 2026): migrations through 0015 apply with no schema
drift; 235 backend tests, four environment tests, strict API typing, web
type-check, lint and production build pass. The new parser review journey also
passes in focused authenticated desktop/mobile runs. Parser outputs remain
non-authoritative and review history is append-only. See the
[Phase 7 evidence](docs/35-PHASE-7-CV-PARSER.md). A real parser repository or
approved API contract is still required before external connectivity can be
accepted.

Latest local verification (10 Oct 2026): `pnpm verify` passed with 231 backend,
four environment, and 72 desktop/mobile browser tests, plus clean dependency
audits. Migrations through 0012 apply cleanly. Detailed evidence and boundaries:
[Phase 6 acceptance](docs/34-PHASE-6-PLACEMENT-FIRST-INCOME.md),
[Phase 5 acceptance](docs/33-PHASE-5-MATCHING.md),
[Phase 4 checkpoint and rollout gates](docs/30-PHASE-4-SUPPLY.md),
[Phase 3 acceptance](docs/29-PHASE-3-DEMAND-ACCEPTANCE.md),
[Phase 2 acceptance](docs/28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md), and
[integration readiness](docs/27-INTEGRATION-READINESS.md).

Phase 1 Foundation was independently rechecked on 07 Oct 2026: 19 focused tests,
four environment tests, live API/database/private-storage checks, and desktop/mobile
shell checks passed. No application rebuild or migration changes were needed.
Docker/container execution, hosted CI, and staging deployment remain unverified.
See [foundation acceptance](docs/24-PHASE-0-VERIFICATION.md).

The integration-readiness extension adds authorized external-reference APIs,
controlled provenance, and non-user audit attribution without external clients.
Internal UUIDs remain authoritative. Local credentials and supplied reference
links are not integration configuration. Supply now has a staff frontend and
dedicated tests, with visual acceptance still in progress and policy/scanner
rollout gates outstanding; production MFA is not configured.

## Visual Direction

On 07 Oct 2026 the user confirmed Jobberman-inspired blue accents and recruitment
styling, with Apple-like fluidity. HAPPY keeps its name and operational layouts.
The supplied `index-1.html` role-based prototype v4 now provides the concrete
visual reference: `#004AB9` blue, `#101A38` full-height desktop sidebar, `#F5F8FB`
workspace background, white search/account bar and blue initials avatar.
Shared tokens cover commands, hover, focus and navigation. Arial matches the
prototype's actual fallback rendering; no external font download is introduced.
This is not a claim of an official licensed brand font.
The favicon ZIP's RedMERL manifest is not used to rename HAPPY, and the third-party
logo is not installed. See [brand decisions](docs/21-OPEN-DECISIONS.md) and
[prototype adaptation](docs/32-VISUAL-REFERENCE.md).

Short eased transitions accompany workspace changes, menus, sheets and drawers.
Controls have restrained colour/press feedback. Reduced-motion preferences remove
entrance motion and spinning indicators; changing the preference cancels active
workspace motion. Native focus handling, immediate dismissal, save guards and
server-side authorization remain intact. No animation library, scroll takeover,
decorative autoplay or network font dependency is introduced.
The authenticated mobile shell now follows the documented compact header,
bottom navigation and More-sheet layout. Desktop keeps its sidebar. Navigation
uses the same permission-filtered view list; server authorization is unchanged.
All six desktop/mobile shell regression cases passed in full local CI,
including permission-denied API access, session expiry, focus restoration and
resize handling. A subsequent development-only badge correction passed lint,
types and live desktop/mobile preview checks with unobscured-navigation hit tests.
The header now includes an account menu and grouped search over Participants,
Employers and Vacancies, using existing security settings and domain views.
Search is permission-filtered server-side, cursor-paged and kept out of URLs;
superseded requests are cancelled and results are not persistently cached.
Employers access follows organization:view across workspaces, not a frontend
role-name check. All twelve desktop/mobile header cases passed in full local CI,
including one-press Escape dismissal, focus restoration and sign-out recovery.
Live preview checks also passed at 1440, 412 and 320 px using the existing local
account, with no page errors, overflow or obscured navigation. Search/menu focus
and sign-in/sign-out passed without creating programme records.
Mobile quick-add reuses authorized participant/employer/vacancy forms; roles
prioritize commands while effective permissions determine availability. Staff
editors use a desktop right drawer and mobile full-screen panel, with sticky
actions and reference-data retry/cancel states. Previously granted creators
outside Demand/Supply default to an unassigned owner rather than an ineligible one.
The updated visual implementation is awaiting user review. Placement/campaign
search extends the existing boundary when those later domain services exist.

## Matching

Phase 5 is complete for local development. Migration `0011_matching`, guarded
matching APIs, responsive pipeline/table views, atomic bulk transitions,
dashboard drill-downs, My Work, candidate evidence, interview workflow and
explained advisory suggestions are implemented. Matching cannot create Phase 6
placement states. See [Matching acceptance evidence](docs/33-PHASE-5-MATCHING.md).

## Placement And First Income

Phase 6 is complete for local development. Placements require selected candidate
relationships; actual starts drive vacancy headcount, and only authorized human
first-income verification creates a confirmed placement. Confirmation remains
historical after employment ends. Staff have responsive Placements and First
Income queues, and shared search includes permission-filtered placement results.
See [Phase 6 acceptance evidence](docs/34-PHASE-6-PLACEMENT-FIRST-INCOME.md).

## M&E / MERL

Phase 8 is complete for local functional development. Follow-ups can be manual or
template-driven, outcomes remain historical, corrections are revisioned, sensitive
income is permission-gated, and employment conflicts can create data-quality work.
The responsive MERL workspace exposes operational queues and dashboard evidence.
See [Phase 8 acceptance evidence](docs/36-PHASE-8-MERL.md).

## Marketing

Phase 9 is complete for local functional development. Requests preserve
cross-workstream lineage and requester isolation; campaigns own production state,
reviewed assets and manual metrics; impact stories use restricted projections and
active publication consent. Campaign search is permission-filtered. See
[Phase 9 acceptance evidence](docs/37-PHASE-9-MARKETING.md).

## Management And Reporting

Phase 10 is complete for local functional development. Management can choose an
explicit period, monitor attention queues and programme KPIs, inspect evidence,
download authorized CSV reports and compare actuals with configured global
targets/forecasts. Admin controls target configuration. See
[Phase 10 acceptance evidence](docs/38-PHASE-10-MANAGEMENT-REPORTING.md).

The backend requires `cryptography>=50.0.2,<51` after local dependency auditing
identified vulnerabilities in the draft's old 46.x range. Reinstall the API
dependencies after updating the project.

```bash
pnpm verify
```

`pnpm verify` needs PostgreSQL and private object storage running. It applies the
baseline migration, checks formatting/lint/types, runs live database/storage tests,
builds the web app, runs desktop/mobile browser tests, and audits dependencies.
It temporarily uses port 3100 for the browser-tested server. Stop the development
web server before CI because both use the web build directory.

IAM, Demand, and browser tests use temporary, isolated PostgreSQL schemas and synthetic
accounts. Their separate API is stopped and schemas removed on exit. The CI
production build targets that temporary API; rebuild with the intended backend
before using production output outside CI.

Windows CI uses installed Microsoft Edge when available. Otherwise install the
Playwright browser into the workspace:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/.local/browsers"
pnpm --filter web exec playwright install chromium
```

For Linux, use `PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" pnpm --filter web exec
playwright install --with-deps chromium`.

Individual checks remain available as `pnpm api:test`, `pnpm api:lint`,
`pnpm api:type-check`, `pnpm lint`, and `pnpm type-check`. Plain backend tests skip
live integration tests; `pnpm verify` includes them.

API liveness: `http://localhost:8000/api/v1/health/live`.
Readiness: `http://localhost:8000/api/v1/health/ready`, which checks both PostgreSQL
and the private bucket.

## Staging

Use `.env.staging.example` and the provider-neutral configuration in
`infra/deployment/`. See `infra/deployment/README.md`. No production provider or
programme policy is selected by this setup.

Historical Phase 0 (now Phase 1 Foundation) decisions and local CI acceptance are recorded in
`docs/23-PHASE-0-DECISIONS.md`.

Phase 1 Foundation is complete for local development. Acceptance results and untested
deployment boundaries are in [docs/24-PHASE-0-VERIFICATION.md](docs/24-PHASE-0-VERIFICATION.md).
Provider-specific deployment preparation is available in
[`docs/45-RENDER-NEON-DEPLOYMENT.md`](docs/45-RENDER-NEON-DEPLOYMENT.md): Neon hosts
PostgreSQL, while Render runs the API and web services from `render.yaml`. Cloud
provisioning and the production release gates remain pending.

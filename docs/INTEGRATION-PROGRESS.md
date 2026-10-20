# HAPPY-ONE integration verification and acceptance

Local implementation checkpoint: 20 October 2026. Baseline: `136cc95`.

## Implemented slices

| Slice | Result | Main source |
|---|---|---|
| Audit and ownership | Component map, gap analysis, field ownership, proposed migrations and legacy retirement conditions | `docs/INTEGRATION-ASSESSMENT.md`, `INTEGRATION-CONTRACTS.md`, `LEGACY-DEPRECATION-REGISTER.md` |
| Parser | Dedicated stateless, machine-authenticated entrypoint using actual PDF/DOCX extraction and classification; strict bounded advisory contract | `CV-Parser-main/cv_system_output/happy_service.py`, `requirements-happy.txt`, `Dockerfile.happy`, HAPPY parser adapter |
| Public participant intake | No accounts or sign-in; central participant/consent/self-reported records, local drafts, private CV, idempotency, duplicate review, validation, shared rate controls and audit/provenance | `frontend/`, HAPPY `integrations/intake/` |
| Employer intake | Maintainable employer-only form, multiple vacancies/requirements/terms, private attachments, duplicate candidates, staff review and conversion to central records with draft vacancies | `portal/src/`, HAPPY employer integration and staff submission workspace |
| Operations | Receipt/job status, evidence permissions, duplicate provenance resolution, parser retry, scan retry, recovery of interrupted/final-expired jobs | Staff `intake-operations.tsx`, intake APIs, parser worker |
| Verification and staging preparation | Ecosystem CI, live public browser harness, real-parser golden workflow, isolated Render blueprint | `.github/workflows/ci.yml`, `integration/`, `scripts/`, `render-staging.yaml` |

Additive migrations are `0035_public_intake` and `0036_vacancy_terms`. Existing
migration history and authoritative programme workflow constraints are preserved.
No participant authentication, public record lookup, unrestricted internal CRUD,
browser staff/database credentials, historical import or new system of record is
introduced. Legacy systems remain isolated reference artifacts pending acceptance.

## Local verification evidence

- Original full backend baseline: **277 passed**.
- Latest complete backend run: **296 passed**, no skips (332.34 seconds). This
  includes public intake security/idempotency/duplicates, private staged employer
  document download, central provenance, scanner recovery, parser outage/restart
  and exhausted final-lease recovery.
- Real parser HTTP contract: **14 passed**; isolated parser service contract:
  **8 passed**. PDF and DOCX fixtures exercise real extraction and classification.
  Failure-path tests reproduce private exception content during DOCX extraction
  and structured parsing; the dedicated runtime retains only safe diagnostics.
- Public frontend contract/asset checks: **5 passed**; both static builds passed.
- Participant and employer desktop/mobile browser journeys against a live local
  API passed, including browser draft restoration, final submission, a genuine CV
  upload, responsive overflow checks and removal of synthetic records/private files.
- Full platform verification passed with **294 backend tests** and **98 staff
  desktop/mobile browser tests** before the final worker and staff-operations
  regression additions. Python formatting/lint/strict types, Alembic upgrade and
  model drift check, web formatting/lint/types, four environment tests, production
  build, dependency consistency and dependency audits passed.
- The final 296-test backend run supersedes that backend count. The focused staff
  browser rerun passed **4 desktop/mobile checks** for the latest employer review
  UI and operations view. The new operations check scopes errors
  to workspace content because Next.js also has an empty route-announcer alert.
- Render blueprint validated against Render's published JSON schema; all services
  track the same integration branch. This does not establish a live deployment.

The golden workflow test uses public intake APIs, private storage, a real parser
HTTP process, authorized human review actions and existing domain APIs. It creates
an employer, partnership and draft vacancy; activates the vacancy; collects a
participant and consent/CV; reviews parser suggestions; sets readiness; matches,
pre-screens, submits, interviews and selects; records an actual start; verifies
first monthly income; checks confirmed placement, operational headcount, MERL,
audit and reporting. Operational steps require no manual database edits.
Browser form journeys and this API workflow are complementary evidence; they do
not replace deployed human UAT across programme roles.

Hosted CI is configured for parser, platform, HAMIS, Employer Intake and contracts.
Consult the pull request checks for its actual result; local verification alone
is not a hosted-CI pass.

The first hosted run passed parser, HAMIS, Employer Intake and contracts. Linux
reported 295 backend passes and one pre-existing backup executable discovery
failure: client-only installations were incorrectly required to have `pg_ctl`.
The backup utility now resolves the requested client on PATH first and retains
the installed-directory fallback. Three regression cases cover client-only and
fallback discovery; the manifest unit test no longer depends on host binaries.
The final hosted run must pass these and the full platform checks.

The next hosted run passed **299 backend tests** and **97 of 100 staff browser
checks**. Two existing mobile tests used ambiguous labels after desktop records
were created; they now identify their newly created marketing request and the
correct participant's outcome. The dashboard hover state also exposed insufficient
muted-label contrast; hovered card labels now use the foreground colour and the
accessibility test explicitly exercises that state. Accessibility checks remain
enabled with no exclusions.

The subsequent hosted foundation verification passed **299 backend tests**,
**100 staff desktop/mobile browser tests**, formatting, lint, types, migrations,
production build and dependency audits. Its final public browser harness exposed
a Linux-only fixture issue: PDF serialization requires a seekable stream, while
stdout can be a pipe. The harness now serializes into `BytesIO` before writing
the bytes, and public browser verification runs earlier in CI. The latest complete
workflow result is available in the pull request checks.

## Remaining acceptance gates

1. **Render is not set up yet.** Create/configure the staging workspace and apply
   the isolated blueprint after CI passes. See `STAGING-RENDER.md`; no deployment
   has been performed or claimed.
2. Provision separate staging PostgreSQL, private object storage, scanner and
   parser credentials. Verify HTTPS/CORS, readiness, private parser connectivity,
   abuse-control behavior, credential rotation and scan/worker recovery there.
3. Programme owners must approve privacy wording/version, mandatory onboarding
   fields/sections, document/MOU rules, retention/withdrawal handling, reporting
   definitions and any parser confidence thresholds. Intake stays closed until
   the relevant notice/policy configuration is supplied.
4. Run and record human UAT for Supply, Demand, Matching, MERL, Marketing,
   Management, Admin, participant and employer. Reconcile a known synthetic
   dataset with reports and verify cleanup. Retire legacy services only after
   these acceptance conditions and ownership decisions are satisfied.

This checkpoint is an implemented and locally verified integration candidate.
Deployed staging acceptance and production readiness remain pending.

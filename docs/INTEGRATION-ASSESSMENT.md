# HAPPY-ONE Integration Implementation Assessment

Assessment date: 19 October 2026. Baseline commit: `136cc95`.

## Current system map and disposition

| Component | Current state / backend / persistence / authentication | Keep | Replace / integrate | Remove later |
|---|---|---|---|---|
| HAMIS `frontend/` | Static HTML/JS; Apps Script envelopes; browser drafts/queue; continuation tokens | Form fields, responsive design, validation | HAPPY participant-only intake, local drafts and public submission endpoints, central consent and CV uploads | Apps Script/Drive upload path after acceptance |
| Employer `portal/` | Compiled React/CSS with `/Happy/` asset paths and Apps Script assumptions; maintainable source absent here | Supplied branding and employer field requirements | Maintainable employer-only source; public submission; central submission inbox | Compiled staff/candidate/matching/placement routes after acceptance |
| Staff web | Next.js/TypeScript; HAPPY API; staff HttpOnly sessions and CSRF | Existing workspaces and RBAC | Intake visibility and operations links | Nothing |
| HAPPY API | FastAPI/SQLAlchemy; central domain services and server authorization | Existing domain, review gates, UUIDs | Public intake authorization contexts, schemas and contracts | Apps Script forwarding as a required integration |
| PostgreSQL | Authoritative domain; Alembic through `0034_hamis_worker` | All history and constraints | Additive intake receipt/document migration | No historical imports |
| Object storage | Private S3-compatible storage; PDF/DOCX checks, clamd boundary, checksums/versioning | Existing validation and storage | Participant and employer-owned uploads | Portal/Drive references as trusted files |
| CV Parser | Standalone FastAPI, candidate DB, Sheets, matching, WhatsApp; reusable `parser/` and `classifier/` | Actual extraction, parsing, classification | Separate stateless HAPPY ASGI entrypoint and machine token | Candidate DB, Sheets, matching and WhatsApp dependencies on HAPPY path |
| Workers | PostgreSQL leases/retries; CV, HAMIS, exports | Durable worker and restart recovery | Participant-origin parser jobs and scan recovery | No new queue infrastructure |
| Authentication | Staff IAM and integration bearer credentials | Staff and machine boundaries | No participant identities or authentication; public intake controls | Browser use of staff/integration credentials |
| Documents | CV documents plus partnership/JD version models | Private central document infrastructure | Staged employer documents linked on conversion | Separate portal file store |
| Integration adapters | HAMIS machine event inbox; employer encrypted inbox; HTTP parser adapter | Idempotency, encryption, provenance, review | Direct intake API; actual parser response validation | Apps Script bridge requirement |
| CI/CD | Platform-only workflow; no hosted runs returned at audit | Existing strict checks | Correct Python executable/browser paths; parser, frontend, contract jobs | Stale ATS-only deployment assumptions |

## HAMIS gaps and field ownership

| Capability | Current | Target / required work |
|---|---|---|
| Registration | Apps Script consent-first action | Public validated intake; duplicate review; HAPPY UUID and source |
| Draft/resume | Browser state and queue | Local draft persistence; stable submission IDs; retry-safe final submission and sync feedback |
| Profile | Legacy camelCase fields | Explicit domain mapping for basic/contact/demographics/education/employment/training |
| Consent | Legacy acceptance/signature | Central append-only consent evidence; approved notice configuration; withdrawal history |
| CV | Apps Script or direct Drive | HAPPY private storage and scanned parser job |
| Submission | Legacy screens | Existing onboarding checklist and completion service |

Participant editable: self-reported basic/contact/location, demographics, education,
unverified skills/employment, training summary and consent. Staff authoritative:
assignment, readiness, programme/pipeline/placement status, verified skills/income,
internal notes. Review required: edits after completed onboarding, identity changes,
duplicate matches and parser suggestions. Calculated: progress, age, placement and
headcount totals. No Ghana Card collection is added until handling is approved.
Training attendance remains staff authoritative; participant training is self-report.

## Employer Intake gaps

| Capability | Current | Target / required work |
|---|---|---|
| Source | Minified output only | Buildable, testable employer-only HTML/JS source |
| Intake | Machine-only encrypted inbox | Public intake -> same inbox -> Demand review |
| Mapping | Company/contact/basic vacancy | Extend location, partnership, compensation/schedule/benefits/requirements |
| Duplicates | Exact normalized company name | Also contact email/phone/domain/location; human chooses organization |
| Documents | Untrusted external IDs | Private validated staged documents; link versions on conversion |
| Authority | Existing staff conversion | Preserve separate submission/vacancy states; vacancies remain DRAFT |

## CV Parser gaps

| Capability | Current | Target / required work |
|---|---|---|
| Contract | Standalone candidate endpoints differ from adapter | Dedicated JSON/base64 `/api/v1/integrations/happy/parse` |
| Runtime | Imports database/Sheets/WhatsApp | Stateless ASGI runtime reusing extraction/classification only |
| Authentication | Legacy user auth | Environment-provided constant-time machine bearer validation |
| Output | Candidate records and parser logs containing PII | Bounded advisory allow-list; no candidate persistence; redact logs |
| Verification | Legacy suite | PDF/DOCX, auth, malformed files, real adapter contract, retry/review tests |

## Backend readiness

Existing Supply, Demand, Matching, Placement, MERL, Training and Reporting stay
authoritative. Supply services currently assume a staff actor; adapt attribution
to trusted authorization contexts rather than manufacturing staff identities.
Employer conversion is transactional but must map more fields and staged files.
Parser jobs already support retries/leases and human review. Audit actor types
already include PARTICIPANT/EMPLOYER. ExternalReference supports source IDs.

## Proposed database changes (before implementation)

`0035_public_intake`: additive public idempotency receipts and encrypted duplicate-review evidence, plus private staged intake documents. No participant accounts, sessions, tokens, or server-side draft identities. Client submission IDs are unique per source; a payload hash rejects changed replays. Nullable foreign keys link the existing central participant and employer submission. Staged documents have checksums, scan status, private storage keys and eventual central document links. Existing UUID keys and all prior migrations remain unchanged.

## Legacy classification

Additional additive migration proposed before implementation: `0036_vacancy_terms`
adds nullable `vacancies.deadline` and bounded JSON benefits (empty default).
The existing model has neither field, so employer intake would otherwise lose
these declared vacancy terms. Existing vacancies and workflow constraints remain
compatible; no placement or headcount rule changes.

KEEP central HAPPY domains/services/RBAC/audit/documents/workers and reusable parser.
ADAPT frontend API clients and existing integration contracts.
DEPRECATE Apps Script/Sheets persistence, Portal internal recruitment interfaces,
parser candidate database/Sheets/WhatsApp on the HAPPY path.
REMOVE AFTER ACCEPTANCE only; retain legacy artifacts isolated meanwhile.
See `LEGACY-DEPRECATION-REGISTER.md`.

## Ordered implementation and verification

1. Record audit and run baseline unit/integration/browser/static checks.
2. Repair CI interpreter, browser-cache and Linux portability issues; preserve checks.
3. Add stateless authenticated parser endpoint, isolated dependencies and real fixtures.
4. Validate adapter schema, bounds, errors and retry behavior against actual parser.
5. Add public intake schemas, field ownership and idempotent final submission services.
6. Connect HAMIS drafts, central consent, private CV and submission; test isolation.
7. Restore maintainable employer intake source; extend mapping/review/documents.
8. Test duplicate participants/employers, replay/conflicts, RBAC and audit.
9. Exercise one synthetic employer/participant/parser/matching/placement/MERL workflow.
10. Add ecosystem CI jobs and operations/metrics; repeat relevant strict checks.
11. Configure isolated Render staging and execute deployed UAT when account access exists.
12. Reconcile reports and document remaining policy/provider acceptance gates honestly.

## Baseline evidence and open decisions

Initial unit run: 135 passed, 142 integration tests skipped (16.52s). This is not
an integration baseline. Hosted Actions returned no runs for the initial push.
The initial full baseline subsequently passed all 277 backend tests. Current
implementation evidence and outstanding acceptance gates are maintained in
`INTEGRATION-PROGRESS.md`.

User decisions: no HAMIS sign-in, accounts, authentication sessions, participant RBAC,
or account dashboards. Render is the intended staging provider, but the user has
confirmed it is not set up yet. Draft/resume stays local. Public narrowly scoped
final submission endpoints enforce validation, rate limits, abuse controls,
request-size limits, idempotency, duplicates, private files, audit/provenance and
safe errors. No public internal CRUD or post-submission profile access is exposed. Privacy
notice wording/version, required sections, MOU approval, withdrawal consequences,
retention, confidence thresholds and programme reporting definitions remain
configuration/acceptance gates; do not silently approve them. Staging must use
separate database, storage and credentials and synthetic data only.

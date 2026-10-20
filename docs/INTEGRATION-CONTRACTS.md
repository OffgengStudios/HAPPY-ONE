# HAPPY ecosystem integration contracts

Version: `/api/v1`, schema version 1. PostgreSQL remains authoritative.

## HAMIS: public collection without sign-in

`GET /api/v1/participant-intake/config` returns the approved notice text/version,
configured onboarding requirements and upload limit. An unconfigured notice
closes intake. This response contains no personal records or credentials.

`POST /api/v1/participant-intake` accepts multipart form data:

- `payload`: JSON matching `ParticipantSubmission` in
  `HAPPY_PLATFORM_CODEX/apps/api/app/integrations/intake/schemas.py`.
- `cv`: optional PDF/DOCX bytes. Uploading to a parser or Drive from the browser
  is not part of this contract.

There are **no participant accounts, passwords, login, authentication sessions,
RBAC identities, account dashboards, public participant lookup, or public profile
update endpoints**. The frontend opens directly to collection. Staff credentials,
integration machine tokens and database credentials are never sent to HAMIS.

Unfinished forms autosave in the current browser tab. The participant may opt to
keep the draft on that device for at most 24 hours. Drafts expire and are deleted
after accepted submission or an explicit discard. CV bytes are not persisted in
web storage; reselect attachments after reload. Drafts are not an authoritative
dataset. Subsequent programme operations belong to staff in HAPPY.

The payload explicitly separates basic/contact/demographics/education/employment,
self-reported sensitive fields and training summary. Skill verification, staff
assignment, readiness, placement, pipeline and income verification cannot be set.
Ghana Card collection is disabled pending approved handling. Extra legacy fields
without central columns are retained only as encrypted submission evidence under
an explicit allow-list; they are not silently promoted into authoritative fields.
Formal training attendance remains staff managed.

## Employer Intake: collection and review

`GET /api/v1/employer-intake/config` returns the configured employer notice and
upload limit. `POST /api/v1/employer-intake` accepts multipart `payload` JSON and
up to five `files` parts. `documents` in the payload describes each file in order:
`kind` is MOU, AGREEMENT, JD or SUPPORTING. JD requires a zero-based submitted
`vacancy_index`. Only PDF/DOCX is accepted by the existing private document boundary.
Consent flags are evidence of application submission; they do not sign or approve
an MOU or activate a vacancy.

The server maps the submission into the existing encrypted EmployerSubmission
inbox. Demand staff uses the existing `/integrations/employer-portal/submissions`
review and conversion endpoints with normal staff permissions, CSRF and versions.
Conversion reuses Organization, Contact, Partnership, Vacancy and Requirement.
Vacancies start DRAFT; normal staff transitions are required to activate them.
Salary, frequency, schedule, benefits, accommodation and deadline are preserved.
Possible employer duplicates by name, website domain, contact email or phone
require explicit human selection. No uncertain employer is auto-merged.

The maintained client source is `portal/src/`. `portal/index.html` mirrors
`src/intake.html` for local preview; the build uses the maintained source.
Legacy compiled assets and the old entrypoint in `portal/legacy/` remain isolated
and are excluded from the new static build.

## Shared public security and replay rules

Public intake does not rely on authentication. Every POST must have an explicitly
allowed browser Origin. Staff cookies are omitted by both clients. The API uses
strict schemas, a honeypot, shared PostgreSQL rate counters (20 submissions per
15 minutes by default, configurable through `PUBLIC_INTAKE_LIMIT`), bounded request
bodies, central duplicate checks, encrypted evidence and private document storage.
The server does not trust caller-supplied forwarded IP headers.

Each client persists a UUID `submission_id`. The unique key is `(source, ID)`.
The server hashes the validated payload and attachment bytes. An exact replay
returns the original receipt; different content under the same ID returns 409.
Transaction locks serialize competing submissions and duplicate checks. The
response is always `{receipt_id, status: "RECEIVED"}` for accepted new and
duplicate submissions; no participant identifier, private URL, record contents or
duplicate match details are disclosed. A receipt is not an access credential.

Errors are safe structured responses: 403 origin, 413 size, 422 validation/notice,
429 throttling, 409 changed replay, and 503 unavailable encryption/storage. They do
not echo submitted PII. A network failure or 503 may be retried with unchanged
content/ID; validation errors require correction. Editing a previously attempted
submission creates a new client ID. There is no unrestricted participant CRUD.

Receipts, domain writes, consent and staged document links commit together.
Failed submissions roll back the transaction and compensate newly created private
objects; a cleanup failure emits an operational error without exposing object keys.
No database transaction pretends to make external S3 atomic.

## Private documents and parser

Uploads use central MIME/structure/size validation, SHA-256, private object keys,
versioned domain documents and clamd. Unscanned files remain SCANNING and cannot
be parsed or accepted as employer documents. Intake operations can retry scans;
normal staff document routes remain authoritative for approval and parsing.

HAPPY alone calls `POST /api/v1/integrations/happy/parse` on the dedicated parser.
Request: `filename`, `mime_type`, `content_base64`. Authentication is a backend-only
Bearer secret (`CV_PARSER_TOKEN` on HAPPY, `HAPPY_PARSER_TOKEN` on the parser).
Configure a complete `CV_PARSER_URL` or private `CV_PARSER_HOSTPORT`.

The parser has a separate `happy_service:app` ASGI entrypoint and
`requirements-happy.txt`. It imports real extraction, parsing, skill and
classification code, without importing the candidate API/database, Sheets,
matching or WhatsApp. Temporary files use generated names and are removed.
No candidate profile is persisted. The dedicated runtime sanitizes reused engine
diagnostics, exception content and tracebacks before they reach log handlers;
extracted names/contact data are not logged.

Response: schema version 1, provider/model labels and bounded suggestions for
first name, surname, other names, phone, email, skills and job role. Classification
confidence is advisory; uncalibrated extraction fields use null confidence.
The HAPPY adapter rejects malformed, duplicate, unsupported, unbounded or invalid
confidence values. HTTP responses are bounded to 512 KiB. Provider failure does
not block onboarding; the existing PostgreSQL worker manages leases, backoff and
retry limits. Suggestions are stored separately until a human approves/rejects
them. No parser output changes a participant automatically.

## Staff operations, audit and policy boundaries

The staff navigation includes Integration operations, guarded by
`integration_event:view`. It shows receipt source/status and parser job state,
attempts and safe error codes. Evidence access also requires the applicable
participant-sensitive/employer-submission permission and is audited. Review,
duplicate resolution and scan retry require `integration_event:manage`.
Parser retries use the existing authorized CV parse endpoint, creating a new job
while retaining the failed job's attempt history.

Duplicate participant resolution explicitly links an existing HAPPY UUID and
provenance. It does not overwrite the profile, revive consent, merge people or
approve documents. Central consent history remains append-only, with existing
staff withdrawal workflows preserving grants and withdrawals. Because HAMIS has
no authenticated post-submission access, later corrections/withdrawals are handled
by the HAPPY team under existing permissions.

Intake counters use fixed names and no PII labels. Core reporting reconciles
central records, not counters or receipt totals. The placement rule remains:
actual start plus verified first monthly income is required for confirmation;
vacancy operational fill is based on valid starts.

Privacy notice wording, mandatory fields/sections, MOU policy, retention periods,
withdrawal consequences, programme metrics and confidence thresholds remain
explicit programme decisions. Local synthetic fixtures do not approve policy.

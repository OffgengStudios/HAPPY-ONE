# Phase 4: Supply

Implementation review: 07 Oct 2026. Continue the existing Supply draft, preserve
applied migrations 0007/0008 and the authoritative UUID/external-reference model.
Functional local verification passed; this document does not claim production
acceptance. Visual acceptance remains open following the user's theme feedback.
The full local CI checkpoint below passed; remaining acceptance work is explicit.

## Implemented Workflows

Individual Person/Participant intake, advisory phone/email/name-location
duplicates with explicit distinct-person acknowledgement, progressive typed
onboarding sections, historical education/experience/skills, assignment,
readiness/availability assessment, archive, consent recording and withdrawal,
private CV versions, scan gates, human approval, download and archive.

The staff frontend now exposes participant list/search/status filters and
pagination, a permission-aware record with onboarding checklist, structured
repeatable education/experience/skill forms, consent/history, CV versions,
sensitive-data projections, Supply dashboard drill-downs and five My Work
buckets. Reuses existing shell, session, dialog and form conventions.

Role shapes navigation; the server independently enforces resource permissions.
Supply has no default sensitive-data grant. Authorized administrators can assign
explicit sensitive permissions; no job-title policy was inferred.

## Policy Configuration

The working environment stays fail-closed. No approved privacy notice or
mandatory checklist has been supplied. Spreadsheet headers are not approval.
The supplied headers are now the user-confirmed Supply field inventory;
see [field mapping and outstanding semantics](31-SUPPLY-FIELD-INVENTORY.md).
They do not approve a privacy notice or make every sensitive field mandatory.
The Kollekt source review found existing consent wording; its reviewed commit
and recording/version limitations are documented in the field inventory.
Reuse confirmation remains pending; working approval configuration is unchanged.

- `SUPPLY_ONBOARDING_POLICY_APPROVED=false` by default.
- `SUPPLY_PRIVACY_NOTICE_VERSION` must identify an approved notice.
- `SUPPLY_REQUIRED_SECTIONS` accepts basic/contact/demographics/education/
  employment/training/consent/cv/review. Basic, contact and consent always apply.
- `SUPPLY_REQUIRED_FIELDS` accepts explicit supported public Person fields,
  date_of_birth/sex/nationality, government_id presence, or participant work/
  partner/training fields. Unknown field/section names fail with 503
  ONBOARDING_POLICY_INVALID. No SQL identifiers or identity ciphertext are
  accepted as policy keys.

Completion requires explicit policy approval, current active programme consent,
all required sections and fields, and a non-withdrawn participant. Employer
submission rechecks these conditions rather than trusting a stored COMPLETE
label. Notice/policy changes can make an earlier completion ineligible.
Profile progress includes required fields as well as sections. Profile edits
invalidate a prior review and reopen onboarding; consent withdrawal revokes
all active grants of that type and blocks a completed programme relationship.

Staff-assisted completion records assisting user, mode and timestamp. Staff may
record self-reported completion; this is not a participant authentication flow.
Programme, marketing and publication consent are separate historical records.

## Draft Saving

Basic, contact, training and authorized demographic edits use a 900 ms debounce;
education/employment collection editors use the same draft-save controller.
Save draft remains an explicit flush-and-close action. Consent, review, identity,
readiness, assignments, archive and completion remain explicit commands.
Existing Demand forms retain their manual-save behavior.

Only one draft PATCH runs at a time. Edits during a request remain in memory and
are queued against the version returned by that successful save. Draft writes
still use existing authorization, validation and audit services. Native invalid
fields do not autosave; server validation errors retain entered values. A stale
version stops writes and offers Review latest record rather than overwriting.

Saving/offline/unsaved/conflict states are visible. Offline drafts are not sent;
reconnection resumes a valid changed draft. There is no localStorage/IndexedDB
PII cache. Unsaved navigation warns before leaving, and closing/Escape requires
discard confirmation for unsaved edits. Session expiry continues to clear the
authenticated application; this is not offline authentication or offline intake.

## Documents and Identity

PDF and supported UTF-8 transitional DOCX files are validated before private
storage. Reject mismatched types, macros, paths, oversized/expansion-limit files,
malformed XML and entity/DTD declarations. clamd INSTREAM scans bytes only.
An unconfigured/unreachable/invalid-response scanner leaves SCANNING, never
AVAILABLE. No pending/rejected/archived file can be approved or downloaded.
Rescan is a staff action; no fake scanner or parser job is configured locally.

Each upload has a separate document UUID, storage key, hash and version. New
uploads do not replace an approved current CV or its READY status. Approval
is explicit and human-controlled. Downloads verify stored length/hash and are
audited, attachment-only and no-store. CV-not-required needs permission/reason.
Document/consent state is refreshed after the parent lock to reject stale reads.

Identity values use Fernet encryption and an independent keyed HMAC lookup;
neither full values nor hashes are returned in ordinary/sensitive projections.
Sensitive views and updates are audited without raw values. Missing keys block
identity writes. New migration `0010_supply_identity_unique` adds a nullable
unique identity-hash constraint to prevent concurrent duplicate writes; existing
UUIDs/data/migration history are unchanged. Conflicting existing hashes make
the migration fail rather than silently deleting or merging people.

## Verification and Boundaries

Dedicated unit/PostgreSQL/private-storage tests now cover intake, duplicates,
versions, consent/policy gates, all seven role projections, protected identity,
file validation, clamd protocol/failure states, CV versions/downloads/archive,
dashboard filters, owner-scoped queues, review invalidation and stale documents.
Tests use isolated schemas and remove their private objects.

Browser fixtures alone use an explicitly synthetic approved notice/checklist
in their isolated environment. They do not change working policy or credentials.
Desktop/mobile workflow and read-only tests are included in full local CI.
Full local CI passed on 07 Oct 2026: 219 backend tests, four environment tests,
48 desktop/mobile browser tests, formatting, lint, types, production build,
dependency consistency and dependency audits. Migration 0010 has no model drift.
Twelve Supply browser cases cover autosave, offline recovery, validation and
conflicts, denied access, private CV lifecycle, onboarding/withdrawal and Matching
read-only access across desktop/mobile. Forty dedicated Supply backend cases
cover the workflows above. The isolated browser API/schema and private fixture
objects were removed after the run.

Autosave/connection behavior and additional CV browser cases passed full CI.
The browser review exposed a premature modal-close/refresh race; save now awaits
the refreshed record, and busy Close/Escape actions cannot dismiss it. A delayed
refresh browser regression verifies the next assignment uses the current version.
Browser CV
approval/download uses two explicitly synthetic AVAILABLE fixtures in the
isolated test schema/private bucket, not a real scanner result. New uploads in
that environment remain SCANNING; direct approval/download attempts are blocked.
Cleanup removes only documents within their participant-specific CV prefix
before dropping the validated synthetic schema. Nine safety unit cases cover
schema and object-cleanup boundaries. These fixtures provide UI evidence, not
trusted-scanner deployment evidence.

Do not move the roadmap
checkpoint to Phase 5 merely because the existing backend tests pass. Desktop
and mobile workflow screenshots were inspected, but the user has rejected the
current visual direction. Theme correction and visual acceptance remain open;
see [brand decisions](21-OPEN-DECISIONS.md).
Four browser cases verify shared theme tokens for primary commands, hover,
foreground and selected navigation. Provisional desktop/mobile shell screenshots
were inspected after removing the hard-coded teal interaction classes. This
preparatory work does not approve the current theme or choose the final design.
Six shared-shell cases verify sidebar/bottom-bar positioning, content clearance,
workspace changes, a 320 px More sheet, keyboard focus restoration, desktop
resize, hidden forbidden administration and independent API denial, and session
expiry with a sheet open. The fresh full run passed after correcting the
workspace test selector and a real mobile focus-restoration bug.
Live desktop/mobile preview checks also passed using the existing local account,
with no page errors or horizontal overflow, and successful sign-in/sign-out.
A development badge initially obscured navigation; disabling that development-only
indicator passed subsequent lint/type checks and live navigation hit tests.
The working database still has no model drift. No onboarding policy, notice,
scanner, staff credentials or migration history was changed for these UI checks.

Still required for operational rollout: approved policy/notice, protected key
configuration, a real trusted scanner deployment/evidence, and production
security/deployment acceptance. No participant merge, participant portal,
HAMIS import/sync, Employer Portal client or CV parsing is introduced here.
Authorized duplicate acknowledgement never merges people automatically.

## Shared Header Extension

Account security and logout now live in a keyboard-accessible profile menu.
Permission-aware global search returns bounded public participant, employer
and vacancy projections, with per-group cursor paging and existing UUID-backed
record views. Requests use POST to avoid placing names/phones in access-log URLs;
current session/Origin/CSRF checks still apply. Input and results remain in memory.
Cancelled requests cannot replace a newer query; API reads independently recheck
access when a result is opened. Organization navigation no longer assumes the
Demand workspace is required when organization:view has been granted.

Twenty-eight focused search backend tests and twelve desktop/mobile header
cases passed in full local CI. The browser review also fixed search-input
Escape dismissal so one press closes the dialog and restores its trigger focus.
Test fixtures explicitly acknowledge similar synthetic names; production
duplicate checks remain unchanged. Screenshots were inspected, dependency
audits are clean, and temporary browser schemas/private objects were removed.
Live preview checks at 1440, 412 and 320 px passed using the existing local
account, including menu/search fit, focus, empty states, navigation hit tests
and sign-in/sign-out, with no page errors or horizontal overflow. The working
database retains one administrator, no programme records and migration 0010;
no synthetic test schema remains.
No migration, role grant, staff credential, policy, scanner or external
integration changed.
Placement/campaign search and rendered visual acceptance remain future acceptance work.

## Theme Correction and Action Surfaces

The user has now confirmed Jobberman blue-accent recruitment styling with fluid
motion, and supplied `index-1.html` as the visual reference. Shared tokens,
prototype-aligned Arial typography and short eased surface/control
transitions implement that direction; reduced-motion preferences disable them.
HAPPY is not renamed and the supplied ZIP's third-party logo is not installed.
See [the current UI checkpoint](10-UI-SCREEN-SPEC.md#19-blue-recruitment-theme-and-motion-07-oct-2026).

Mobile participant quick-add reuses the existing intake service and permission
checks. Staff action forms use desktop right drawers/mobile full-screen panels.
Reference-data errors can be retried or cancelled; unsaved state survives resizing.
Explicitly granted creators outside the default Supply workspace remain unassigned
unless an eligible owner can be selected. No policy/notice, scanner, credentials,
migration or external integration is changed. Full local CI passed on 08 Oct 2026:
219 backend, four environment and 66 desktop/mobile browser tests, with clean
dependency audits and no model drift. Matching remains on hold pending user
review of the rendered correction at that checkpoint. The 08 Oct continuation
of the standing all-phases goal now proceeds with Matching development while
keeping visual acceptance and production rollout gates open; it does not imply
user visual approval. See the current roadmap.

The prototype's navy desktop sidebar, white search/account bar, blue initials
avatar, pale background and light KPI surfaces are now reflected in the actual
app. Prototype sample records/counts, role-spoofing controls and fake actions are
not imported. Existing permissions, actual API metrics, intake/onboarding/CV
workflows and future-phase boundaries remain authoritative. See
[visual reference](32-VISUAL-REFERENCE.md).

## Intake Owner Permissions Follow-Up (08 Oct 2026)

An effective `participant:edit` DENY can coexist with Supply workspace access
and `participant:create`. The intake UI previously defaulted that user as owner
from workspace access alone, causing an otherwise permitted create to fail the
existing server assignment check. The default now uses the server-provided
eligible-owner options; an ineligible creator starts unassigned. Eligible staff
still default to themselves. The ordinary New participant command now shares
quick-add's reference-data wait/retry/cancel path rather than opening before
staff options are available.

No API, assignment policy, migration, role grant or working account is changed.
A synthetic denied-editor fixture and PostgreSQL/browser regressions cover
owner exclusion, unassigned creation, eligible assignment, reference-data failure
and independent API edit denial. Full local CI passed on 08 Oct 2026: 220 backend,
four environment and 68 desktop/mobile browser tests, with clean dependency
audits. The 219/four/66 checkpoint above predates this follow-up. User visual
acceptance and operational policy/scanner gates remain open.

The first expanded run passed 220 backend, four environment and 67 of 68 browser
cases. The remaining CV case assumed its older fixture stayed on the first
participant page. Its trace showed HTTP 200, 25 items and a next-page cursor,
with the fixture absent from that page. The test now searches for its fixture
through the existing list control; pagination, timeouts and CV assertions are
unchanged. The fresh full checkpoint above passed after this test correction;
the isolated browser API, test schema and private fixture objects were removed.

After CI, the fresh development preview at `http://localhost:3000` passed live
desktop/mobile checks at 1440 and 412 px: eligible owner default, drawer/panel
framing, no horizontal overflow, cancellation focus and sign-out. Screenshots
were inspected. The first live-check script lacked a base URL for its relative
API request; correcting that harness configuration required no application fix.
The verified preview produced zero page errors and zero participant writes.
The working database retains one user, zero programme records, migration 0010
and no synthetic schemas. The preview remains running for visual review.

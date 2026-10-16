# Completion Audit Follow-Up

Audit follow-up completed on 14 Oct 2026.

## Training User Experience

The first-class Training and Attendance backend introduced in migration
`0020_training` now has a permission-aware web workspace. Authorized Supply and
MERL staff can create and edit sessions, select external training partners,
enrol participants and update individual attendance/completion. Read-only users
receive the same records without edit actions. The participant onboarding
training summary remains prior-history text and is not used as session attendance.

The authenticated Training journey passed on desktop and mobile. The expanded
full browser regression passed 98 tests across both projects.

## Asynchronous Reporting Exports

Migration `0024_report_export_jobs` adds durable export job state; forward
migration `0025_report_export_actor_fks` completes the standard creator/updater
foreign-key constraints. Authorized
users can request a full KPI export, observe pending/running/succeeded/failed
states and download only their completed private object. Immediate exports remain
available and bounded to 5,000 evidence rows for interactive use.

The local executor uses FastAPI background tasks behind a standalone processing
function. This makes local workflows usable without selecting infrastructure,
but it is not claimed as a production-durable queue: a process restart can leave
a pending/running job for operational recovery. The database/API/object-storage
contract is deliberately independent of the future queue provider.

Security properties:

- export and sensitive-export permissions are checked before acceptance
- jobs and downloads are requester-scoped
- output is stored under a guarded private object prefix
- request, completion/failure and download actions are audited
- failed jobs expose a controlled message rather than raw exception details
- browser fixtures delete only their own validated report-export namespace

## Verification

- backend suite with live integrations before the Training/Marketing follow-up:
  265 passed
- focused reporting integration suite: 5 passed
- full desktop/mobile browser suite after Training: 98 passed
- focused prepared-export browser journey: 2 passed
- Ruff, strict mypy, ESLint, TypeScript and production build: passed
- database revision/no-drift check after reporting: `0025_report_export_actor_fks`

## Marketing Training Lineage

Migration `0026_marketing_training_links` adds indexed, nullable Training links to
marketing requests and campaigns. The service validates Training read permission,
record existence, mutually exclusive vacancy/Training linkage, and consistency with
the source request. Migration `0027_marketing_training` brings the persisted
Marketing role grant into line with the RBAC catalog while retaining server-side
authorization. Five focused API scenarios and the Training-linked Marketing journey
pass on desktop and mobile. Alembic is current at `0027_marketing_training` with no
model/schema drift.

## Deployment Preparation

Root `render.yaml` and `docs/45-RENDER-NEON-DEPLOYMENT.md` prepare a Neon PostgreSQL
plus Render API/web deployment. No cloud resources are claimed as provisioned;
Git-hosted source, Neon/S3 credentials and production release approvals are still
required.

Production queue selection, worker recovery/retry policy, retention/expiry and
operational monitoring remain deployment decisions. They do not block local
reporting workflows and are not misrepresented as production readiness.

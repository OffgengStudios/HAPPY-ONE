# Production launch candidate

Prepared 24 October 2026. This is a launch preparation record, not evidence of a
deployed service or programme acceptance. Live release remains pending the inputs
and acceptance evidence below. Keep the release version at `1.0.0-rc.1` until
the release owner accepts it.

## Deployment package

[`render-production.yaml`](../render-production.yaml) is a separate production
candidate for Render. It contains the API, private stateless parser, durable
worker, staff application, HAMIS, Employer Intake, daily backup and weekly restore
jobs. Existing staging and platform blueprints remain separate. Production
services use `main`; promote the reviewed immutable revision to that branch before
applying, or change every service to the approved release branch together.
Automatic deployments are off. Scheduled jobs begin operating when provisioned;
approve their example schedules against the required RPO/RTO first.

The database, private object storage, scanner and monitoring services are explicit
external inputs. No cloud account, region, paid plan, domain or programme policy
has been selected by this file. Confirm these with the release owner before
provisioning. All Render services and any private scanner must share the approved
region/private network. Confirm capacity and cost in the workspace before apply.

The API owns shared configuration. Worker and backup/restore jobs reference its
database, storage and identity values rather than asking operators to re-enter
them independently. The private parser token is generated on the parser and
referenced by the API and worker. Fernet encryption keys require the correct
URL-safe format and are supplied explicitly. Preserve existing encryption and
lookup keys when updating any environment that already contains encrypted data.
Only the restore job receives `RESTORE_ADMIN_URL`; it must identify an isolated
maintenance environment, never the application database. Only the API runs
`alembic upgrade head` before deployment.

Render's [Blueprint reference](https://render.com/docs/blueprint-spec) documents
cross-service variables and `sync: false`. Existing services do not receive new
`sync: false` values automatically on Blueprint updates: provision those directly
in the secret manager/dashboard before releasing. The web Dockerfile declares
only public build configuration and the internal API origin; never add private
credentials to its build arguments.

## Configuration check

Use [`HAPPY_PLATFORM_CODEX/.env.production.example`](../HAPPY_PLATFORM_CODEX/.env.production.example)
as an input inventory. Store actual credentials outside version control. Include
the exact HTTPS origins of staff, HAMIS and Employer Intake in `API_CORS_ORIGINS`.
If custom domains change, update CORS and rebuild the public sites together.
Set the approved privacy notices/version and onboarding settings; do not substitute
development notices or treat defaults as programme approval.

Run from `HAPPY_PLATFORM_CODEX` with the private production configuration selected:

```powershell
$env:HAPPY_ENV_FILE = 'C:\private\happy-production.env'
pnpm release:preflight
```

The production API's pre-deploy command runs the configuration check before
`alembic upgrade head`; failed checks prevent migration/deployment. On the
deployed API, run `python /app/scripts/preflight.py` using its configured
environment. The command is read-only, returns nonzero when required launch
configuration is missing, and reports setting names without their values. It
checks startup safeguards, HTTPS endpoints/exact CORS origins, notices, onboarding
approval, scanner/parser configuration and separate backup/document buckets.
Process variables take precedence over the selected file; run in a clean shell
or directly inside the intended deployment environment.

A successful configuration check does not prove connectivity, notice approval,
bucket privacy, scanner health, credential permissions, SSO acceptance or RPO/RTO.
Record those separately. Optional SSO configuration must be complete when enabled;
verify TOTP/SSO recovery and deactivation using the selected identity provider.

## Release sequence and evidence

1. Complete and record the input/acceptance table below. Provision separate
   staging resources and execute the same topology there first.
2. Run `pnpm verify`, `python ../scripts/verify-intake.py`, parser contract checks,
   and both public builds from the reviewed revision. Require hosted CI on that
   same revision before promotion. Build and exercise Linux container images in
   staging; local Windows execution does not verify containers.
3. Rehearse empty database migrations and a checksum-verified isolated restore.
   Record the migration head, backup checksum, restore duration, and test cleanup.
   Keep the pre-release backup outside the application host.
4. Configure the production API inputs and private parser. Verify configuration,
   migrate once, then start API, worker, staff and public frontends from the same
   reviewed revision. Do not enable public intake until notice/policy approval and
   staging acceptance are recorded.
5. Check `/api/v1/health/live` and `/api/v1/health/ready` over HTTPS. Readiness
   requires PostgreSQL and private storage. Bootstrap the first staff administrator
   through the protected CLI, then verify sign-in, permitted and denied reads,
   CSRF rejection and logout through the staff origin.
6. Submit labelled synthetic participant and employer records with genuine test
   documents. Verify receipt/idempotency, duplicate review, private file scanning,
   parser suggestions and human review. Reconcile intake to recruitment, actual
   start and verified first income, MERL and reporting. Confirm placement remains
   blocked before income verification. Verify permitted/denied file downloads.
7. Stop/restart the worker and parser; verify bounded retries, lease recovery,
   controlled retry authorization and no duplicate records. Exercise scanner
   unavailability and ensure documents remain unavailable until a clean scan.
8. Exercise alert delivery, a scheduled backup and an isolated restore using the
   production provider. Approve backup/retention geography and observed recovery
   times. Remove synthetic records/files through the accepted cleanup procedure
   and verify no test artifacts remain.
9. Record named role UAT and release approval. Observe readiness, latency, errors,
   scans, jobs, audit events and authentication during the launch window. Roll
   back to the previous compatible application image if necessary; do not
   downgrade migrations or restore over new writes without the incident plan.

Use the detailed [production runbook](../HAPPY_PLATFORM_CODEX/docs/39-PRODUCTION-RUNBOOK.md)
for backup, restore, incident response and credential rotation.

## Inputs and acceptance still required

| Gate | Required evidence | Current state |
| --- | --- | --- |
| Hosting | Account access, approved provider/region/plans, domains and TLS | Awaiting owner input |
| Release | Reviewed immutable revision, hosted CI, deployment/rollback owner | Pending |
| Data and files | Least-privilege PostgreSQL, private storage, scanner, parser connectivity | Local synthetic verification only |
| Privacy and policy | Approved notices/version, onboarding, document/MOU rules, retention and reporting definitions | Awaiting programme approval |
| Authentication | Staff MFA/SSO/recovery and deactivation acceptance | Deployment UAT pending |
| Recovery and monitoring | Delivered alerts, scheduled backups, isolated restore, approved RPO/RTO | Provider verification pending |
| Human acceptance | Supply, Demand, Matching, MERL, Marketing, Management, Admin, participant and employer sign-off | Pending |
| Accessibility and reconciliation | Manual assistive-tech/mobile review, known-data totals, verified cleanup | Deployment UAT pending |

Do not retire legacy services, import historical records, or claim production
readiness until the responsible owners accept these gates.

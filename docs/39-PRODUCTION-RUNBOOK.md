# HAPPY Production Runbook

Status: provider-neutral operational baseline. Provider-specific commands, RPO/RTO,
alert destinations and production approvers remain release inputs.

## Release Preconditions

1. Use a reviewed immutable revision and clean dependency lockfiles.
2. Configure production secrets outside the repository. Production startup rejects
   development database/storage credentials, non-HTTPS CORS origins and missing
   identity-encryption secrets.
3. Run `pnpm verify` against isolated PostgreSQL and private object storage.
4. Build the API and web images from the same revision. Scan/sign images using the
   selected deployment provider's approved controls.
5. Create and verify a database backup:

   ```bash
   pnpm db:backup create /secure/backup/happy-before-release.dump
   pnpm db:backup verify /secure/backup/happy-before-release.dump
   ```

6. Rehearse restoration against a non-production maintenance server account:

   ```bash
   pnpm db:backup restore-test /secure/backup/happy-before-release.dump \
     --admin-url "$HAPPY_RESTORE_ADMIN_URL"
   ```

The restore command creates only `happy_restore_test_<random>`, validates its
migration/table evidence, and drops it in `finally`. Never supply the application
database as the admin URL; only `postgres` or `template1` is accepted.

## Deployment

1. Put the release through CI, staging smoke/E2E and the named approval gate.
2. Confirm database and object-storage readiness before migration.
3. Apply `alembic upgrade head` exactly once from a release job.
4. Start API and web containers as non-root users behind TLS termination.
5. Verify `/api/v1/health/live`, `/api/v1/health/ready`, sign-in, a permitted read,
   a denied read, and logout through the public origin.
6. Confirm the environment label is Production and API responses are not cached.
7. Observe error rate, latency, authentication failures, DB connections, scanner,
   parser and export failures during the release window.

## Rollback

- Prefer application rollback to the previous compatible image. Alembic downgrade
  is not the default rollback strategy.
- Do not downgrade after a migration that cannot preserve newer writes. Stop writes,
  assess the migration, and restore the pre-release backup only under an approved
  incident plan.
- Validate restored data in an isolated environment before redirecting traffic.
- Record release revision, migration revision, backup checksum, operator, approver,
  start/end timestamps and validation evidence.

## Backup Operations

- Schedule PostgreSQL backups and provider-native object-storage durability/versioning.
- Store dump archives and `.dump.json` manifests outside application hosts with
  restricted access, encryption, retention and deletion controls.
- Alert on missed backup, checksum/catalogue failure and restore-rehearsal failure.
- Run a real isolated restore rehearsal at the programme-approved cadence.
- RPO, RTO, retention and geographic-copy requirements remain open decisions and
  must be approved before production launch.

## Incident Response

1. Triage severity and appoint an incident lead and recorder.
2. Preserve request IDs, safe structured logs, audit evidence and deployment state.
   Do not copy credentials, government IDs, CV contents or raw tokens into tickets.
3. Contain compromised sessions/accounts or integrations; preserve audit history.
4. For suspected data exposure, restrict exports/downloads and follow the approved
   privacy/breach notification process.
5. Recover from verified artifacts, validate authorization and reconcile records.
6. Document timeline, impact, root cause, corrective actions and owner/date.

## Secret Rotation

- Rotate database, object storage and session-impacting credentials through the
  selected secret manager; restart services and verify readiness.
- Identity encryption-key rotation requires a separately reviewed data re-encryption
  procedure. Do not replace it and strand encrypted government identifiers.
- Lookup-key rotation requires recomputing deterministic lookup hashes under a
  controlled migration. Never log either key or plaintext identifiers.

## Routine Checks

- Daily: readiness, error/latency/auth/export/scanner/parser signals and backup job.
- Per release: full CI, dependency audits, backup checksum and smoke tests.
- Periodic: isolated restore rehearsal, access/role review, stale-session review,
  vulnerability review, audit sampling and accessibility regression.
- Before production: choose provider, RPO/RTO, observability/alerting vendor,
  escalation contacts, release approvers and maintenance windows.

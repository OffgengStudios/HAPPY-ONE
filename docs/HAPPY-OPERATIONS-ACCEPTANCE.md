# HAPPY operational acceptance

2026-10-27. Synthetic data only. This runbook is executable acceptance work for the existing architecture, not evidence that hosted staging exists.

## Environment prerequisite

The owner confirmed that no Render account/project has been created. Create the account, choose its region and project, and connect repository access. Use render-staging.yaml as the starting topology. Supply provider resource names and secret-store references for PostgreSQL, private object storage, backup storage, scanner, OTLP ingestion and an alert destination. Keep values out of Git and reports. Do not deploy production or merge main while acceptance is pending.

Staging needs separate buckets, database, identity encryption and lookup keys, parser token, domains and monitoring resources. Use synthetic staff and participants. Confirm programme privacy notice and onboarding policy with their owner; synthetic fixture notices are not approved policy.

## Operational telemetry

Migration 0039_operational_state stores only WORKER/BACKUP/RESTORE checkpoint times and consecutive failure counts. Apply migrations before starting the updated API and worker. The authenticated GET /api/v1/health/operations endpoint requires integration_event:view. Anonymous access is denied; this endpoint is not a public readiness endpoint.

The worker records heartbeat independently every ten seconds, including while processing a long job. Its successful poll timestamp is separate from the last successful report/parser job timestamp. Heartbeat alone cannot establish that jobs are progressing. Backup/restore failures retain the prior successful timestamp. Checkpoint write failures emit a static safe error and never roll back a completed business operation.

Both API and worker initialize OTLP exporters when OTEL_EXPORTER_OTLP_ENDPOINT is configured. Their resource service names are happy-api and happy-worker. Aggregate observations refresh at most every ten seconds per process; an unsuccessful refresh reports database_available=0 and discards cached healthy observations. Exports use the existing metric attribute allowlist and private trace boundary.

| Signal | Source | Operator action |
| --- | --- | --- |
| API rate/errors/latency | Existing instrumented HTTP metrics and structured route logs | Compare rate, 5xx ratio and latency; use correlation ID, never payload |
| Database availability | happy.operations.database_available; external /health/ready probe | Inspect connection/pool/provider state; /health/live must remain healthy |
| Worker alive | happy.checkpoint.heartbeat_timestamp, operation=WORKER | Detect missing or stale heartbeat independently of successful polling |
| Worker functioning | happy.checkpoint.last_success_timestamp; happy.jobs.last_success_timestamp | Investigate stale successful polls or lack of job completion while queue grows |
| Queue age/depth | happy.jobs.queued/running/oldest_queued_age_seconds/stale_leases | Inspect bounded retries, service failures and expired leases |
| Parser results/latency | happy.parser.attempts; happy.parser.duration_seconds | Review repeated FAILED results without changing authoritative profiles |
| Scanner | happy.scanner.results/duration_seconds; happy.operations.scan_backlog | SCANNING is a failed/unfinished scan, never permission to download |
| Backup/restore | happy.checkpoint timestamps/consecutive_failures, operation=BACKUP or RESTORE | Retain last successful backup age and exercise history across process restarts |
| Intake/duplicates | happy.intake.submissions by fixed status; happy.operations.duplicate_reviews | Human duplicate review; no automated merge |
| Auth failures | happy.operations.auth_failures_15m | Investigate aggregate spikes; never put login identifiers in alert labels |

Database-backed gauges are collected by multiple service instances. In dashboards, select the environment and service, or take the maximum across replicas; do not sum duplicated database snapshots. Parser/scanner attempt counters are process observations and can be summed as rates. Confirm actual backend metric names, units and temporality before configuring queries.

## Alert acceptance matrix

No hosted alert destination is configured or accepted. Suggested initial technical thresholds below require tuning against the staging capacity baseline. Recovery objectives require separate owner approval.

| Fault to create in isolated staging | Detection | Suggested initial trigger | Delivery evidence required |
| --- | --- | --- | --- |
| API stopped | External HTTPS probe | Two consecutive failed probes | Receiver timestamp, alert ID, environment, release, runbook |
| Database unreachable | ready=503 plus database_available=0 | Two consecutive failed probes | Same, plus bounded response time and recovery receipt |
| Worker stopped/stuck | Heartbeat/poll timestamps and queue age | Heartbeat older than 60s or no successful poll for 120s | Stale timestamp and queue context |
| Parser unavailable | FAILED attempts and retry queue | Repeated failures in five minutes | Job type/count only; no document names |
| Scanner unavailable | SCANNING outcomes and scan backlog | Repeated SCANNING outcomes with growing backlog | Fail-closed state and recovery receipt |
| Backup failed/stale | BACKUP failures and last success | Any failed scheduled run; age threshold from approved RPO | Safe operation code; no URLs/credentials/object contents |
| Restore failed | RESTORE failures | Any failed exercise | Isolated recovery environment and safe operation code |
| Storage unreachable | External readiness/provider probe | Two consecutive failed probes | Storage failure signal and recovery receipt |

For each row record: exact revision, fault start, fault mechanism, generated alert ID/time, destination receipt ID/time, acknowledgement, recovery and cleanup. A webhook variable, local receiver, test button or rule file alone is not successful staging delivery. Never include person IDs, emails, filenames, storage keys, raw exception strings or tokens in alerts.

## Recovery objectives

| Proposed option | Maximum data loss (RPO) | Recovery target (RTO) | Provisioning consequence |
| --- | --- | --- | --- |
| Daily recovery | 24 hours | 8 hours | At least daily successful backup, independently stored objects and keys |
| Working-day recovery | 4 hours | 4 hours | More frequent backups plus measured storage/key recovery |
| Short interruption | 1 hour | 2 hours | Provider point-in-time recovery or sufficiently frequent snapshots and faster rehearsed restoration |

The owner selected RPO = 1 hour and RTO = 2 hours on 2026-10-27. Treat these as the required design targets. Provider compliance is NOT VERIFIED: measure successful backup age and complete DB/object/key recovery before claiming compliance. A daily dump alone does not meet the selected RPO. The production manifest now schedules a backup every 30 minutes instead of daily, leaving execution margin. This alone does not prove a one-hour RPO: validate run duration, provider delivery and failed-run detection, and use provider point-in-time recovery if the measured strategy cannot meet the target. Suggested initial backup-age warning: 45 minutes; breach: 60 minutes. Staging needs its own isolated scheduled backup and timed rehearsal.

## Provider recovery rehearsal

1. Record exact HAPPY/UNIJAY/parser revisions and migration head; take a provider backup into a separate private backup location.
2. Verify archive/manifest existence, byte size, checksum, anonymous GET/LIST denial and retention using synthetic archives. Record private object references in restricted evidence, never public logs.
3. Create a fresh isolated recovery database. Restore the actual provider archive and verify migration head, representative synthetic participants, organizations, vacancies, placements, first-income records and audit events.
4. Restore or reconnect versioned private CV/JD/MOU/evidence objects. Recover the matching identity encryption and lookup keys from the approved secret store.
5. Start the pinned application, open the synthetic participant, decrypt the protected identity through authorized application behavior, download the clean CV/JD/MOU, and verify historical placement/audit evidence.
6. Record backup age and total recovery elapsed time, including objects and keys. Compare against the approved objectives. DB-only restoration is partial DR.
7. Clean only named synthetic recovery resources and verify deletion. Do not restore over the active staging database. Prefer forward migration fixes; application rollback requires database compatibility review.

## Remaining acceptance

Provider access, real staging deployment, policy approval, hosted alert receipt, provider backup/restore, full object/key recovery, six-domain concurrency coverage, representative load, role UAT and manual accessibility remain open. Local private storage and local ClamAV results are separate evidence.

# HAPPY-ONE completion progress

Baseline: `15facc8272a8cd4329390a988ba0984cf5397452`, migration `0036_vacancy_terms`, readiness audit Level 2/5. Work is sequential; hosted infrastructure and programme approvals remain external requirements. Synthetic test resources are isolated from the original development database/storage.

## P0-01 — VERIFIED, 21 October 2026

### Completed

PostgreSQL dump/restore passwords now enter only the child environment through libpq PGPASSWORD. Connection arguments are constructed without a password; parent environment is unchanged. Client failures discard captured stdout/stderr and expose a safe error without subprocess exception chaining. CLI/scheduler failure rendering is sanitized. Password query parameters and the old credential-bearing --admin-url option are rejected; maintenance credentials come from the private environment.

### Evidence

The audit reproduced a real pg_dump failure disclosing its database password. New regressions additionally execute a child that echoes its environment password into both output streams before failing. Both application and restore-admin cases assert that arguments and rendered errors contain no sentinel. Tests caught SQLAlchemy URL.set(password=None) retaining the old password; the implementation instead creates a new password-free URL.

### Files Changed

- `HAPPY_PLATFORM_CODEX/apps/api/app/db/backup.py`
- `HAPPY_PLATFORM_CODEX/apps/api/tests/test_backup.py`
- `HAPPY_PLATFORM_CODEX/docs/39-PRODUCTION-RUNBOOK.md`

### Tests Added/Changed

`apps/api/tests/test_backup.py`: child-only credentials; application/restore-admin failures; safe OS/start failure; successful child; query-password rejection; create/scheduled/restore-latest CLI error output. Existing checksum/catalogue/retention/provider restore tests remain.

### Verification

- `python scripts/api.py test -q -k backup`: **17 passed**, 290 deselected (one dependency deprecation warning).
- Targeted Ruff lint/format: **passed**. `python scripts/api.py type-check`: **passed**, 127 source files, strict settings unchanged.
- Real pg_dump, pg_restore catalogue, separate-database restore and failed CLI: **passed**, restored `0036_vacancy_terms`, 14.022 s combined smoke execution. Instrumented subprocess calls contained neither application nor maintenance passwords. Failed real dump exited 1 without password output. Private evidence: workspace `.local/completion-20261020/evidence/p0-backup.json`; no credentials are committed.

### Remaining Risk

Provider backup scheduling, offsite retention, alert delivery and full files/keys disaster recovery remain unverified. Environment credentials remain sensitive and require ordinary operating-system/service access controls. No cloud deployment is claimed.

### Next Task

P0-02: reconcile expired exhausted report claims, preserve live leases, expose authorized controlled retry, verify actual process death/lease expiry/restart and no duplicate output; apply equivalent semantics to retained HAMIS events.

## P0-02 — VERIFIED backend recovery, 21 October 2026

### Completed

Report and retained legacy HAMIS claimers reconcile expired exhausted leases to FAILED / RETRY_LIMIT_EXCEEDED, clear lease state, timestamp completion and append failure audit. Valid leases are excluded. Processing locks and verifies current ownership; failure handling reacquires the lock and cannot overwrite a new owner. Retry endpoints require current permissions, an optimistic version and a reason; reports remain requester-owned and sensitive exports require renewed acknowledgement. A failed report retry form is available in Prepared exports. HAMIS participant sign-in remains absent.

### Evidence

The original audit killed the final-claim process and demonstrated permanent RUNNING/PROCESSING state. The new actual-process regression claims both jobs with one permitted attempt and a 30-second lease, terminates the actual child PID, confirms live leases are untouched, waits 31 seconds, restarts a fresh interpreter, verifies two terminal failure events, retries through authenticated APIs, and verifies one report object and one authoritative participant. Independent concurrent sessions claim distinct pending reports. The first attempted pre-fix regression on 21 October failed during fixture setup because the overnight-stopped database was unavailable; it is not counted as a functional regression result. PostgreSQL was restarted without resetting its data.

### Files Changed

- `HAPPY_PLATFORM_CODEX/apps/api/app/modules/reporting/{worker,routes,schemas,service}.py`
- `HAPPY_PLATFORM_CODEX/apps/api/app/integrations/hamis/{worker,routes,schemas,service}.py`
- `HAPPY_PLATFORM_CODEX/apps/api/tests/test_reporting_integration.py`
- `HAPPY_PLATFORM_CODEX/apps/api/tests/test_worker_crash_integration.py`
- `HAPPY_PLATFORM_CODEX/apps/web/components/reporting-workspace.tsx`
- `HAPPY_PLATFORM_CODEX/apps/web/lib/reporting.ts`

### Tests Added/Changed

Reporting integration tests cover expired final failure, current live leases, audited/optimistic retry, non-owner 404 and Marketing 403. `test_worker_crash_integration.py` exercises real PostgreSQL transactions, actual interpreter termination/restart, real elapsed lease expiry, authenticated retries, duplicate rejection, real private S3 export and distinct concurrent claims. No successful scan/parser response is substituted by this crash test.

### Verification

- `python scripts/api.py test -q -k 'reporting or hamis or real_final_claim_process'`: **19 passed**, 291 deselected, 65.50 s pytest / 67.530 s command. Earlier successful execution: 19 passed, 74.85 s.
- Strict mypy: **passed**, 127 source files. Targeted Ruff: **passed**. Web TypeScript and ESLint: **passed**; changed TS/TSX formatted with Prettier.
- Evidence: [completion-evidence](completion-evidence/). Full production browser/build gate and direct exercise of the new retry form remain part of the later comprehensive verification.

### Remaining Risk

No hosted restart supervisor, queue alerts or monitoring delivery has been verified yet. Database outage/pool behavior is the later P1-05 task. New retry UI interaction has static checks and backend coverage but awaits browser verification. No staging or production readiness promotion is claimed at this checkpoint.

### Next Task

P1-01: prevent raw search values, callback codes, tokens and unhandled exception messages from entering duplicate access/error logs or exported spans; retain safe request IDs, route templates, status and timing. Verify emitted logs and actual OTLP transport with sentinels.

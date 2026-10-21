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

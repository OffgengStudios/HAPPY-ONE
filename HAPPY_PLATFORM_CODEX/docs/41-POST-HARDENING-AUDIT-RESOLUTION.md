# Post-Hardening Audit Resolution

Audit findings reviewed and remediated on 13 Oct 2026.

## Training Domain

The audit correctly found that participant `training_summary` was not a dedicated
Training domain. Migration `0020_training` now adds:

- `trainings`, with partner, trainer type, mode, dates, location, modules and status
- `training_attendance`, with one record per participant/session
- controlled attendance and completion statuses
- optional participant-owned certificate document linkage
- `training:view` and `training:edit` server permissions
- version-checked APIs, bulk enrolment, audit events and integration tests

Supply and MERL can manage Training by default; Management has read access; Admin
inherits all permissions. Training stipends remain excluded because their workflow
is still an explicit programme-policy decision. The participant onboarding Training
section continues to represent prior training history, not session attendance.

## Migration Evidence

Applying migration `0020_training` was an intentional implementation change. After
application, `alembic check` reported no new upgrade operations. This resolves the
audit uncertainty without rewriting or renumbering previous migration history.

## Backup And Restore Evidence

A new PostgreSQL archive was created after migration `0020_training`, checksum and
catalogue verification passed, and the archive was restored into an isolated
disposable database. The restored database reported `0020_training` and was then
removed automatically.

Production scheduling, off-host encrypted retention, retention duration and alerts
remain release gates because no hosting provider, approved RPO/RTO or retention
policy has been selected. The provider-neutral commands and operational controls
are documented in [the production runbook](39-PRODUCTION-RUNBOOK.md). This is not
misreported as a production schedule.

## Regression Evidence

- full backend suite with integration tests enabled: 256 passed
- focused Training integration suite: 2 passed
- Alembic model drift check: passed at `0020_training`
- fresh backup verification and isolated restore: passed at `0020_training`
- latest complete browser regression: 94 passed across desktop and mobile after
  Phases 8-10 and Phase 11 fixes
- automated accessibility subset: 14 WCAG A/AA desktop/mobile cases passed

The prior statement that no current complete browser regression was available was
first superseded by the recorded `94/94` run. The current Phase 13 checkpoint now
supersedes it with `96/96` desktop/mobile tests on 14 Oct 2026, including the
Phase 8-10 workspaces and later integration surfaces. No browser surface was
introduced by the Training backend remediation itself.

Current platform revalidation at migration `0023_employer_portal` passed 262
backend tests, 96 desktop/mobile browser tests, no-drift/offline migration checks,
and a fresh checksum-verified isolated restore. Production scheduling and off-site
retention remain correctly classified as deployment governance gates.

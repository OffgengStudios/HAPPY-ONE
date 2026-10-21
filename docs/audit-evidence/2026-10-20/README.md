# Audit evidence â€” 20 October 2026

Audited revision: `15facc8272a8cd4329390a988ba0984cf5397452`.

All records are synthetic. Credentials/private state, database archives, uploaded files and browser authentication material are excluded. Known audit and local-admin credentials were checked/redacted before copying these results. Original project code and original local services were preserved.

- `runtime-probes.json`: independently reproduced final-attempt worker failure, concurrent claims, upload-size mismatch, permission denials and backup secret disclosure. The actual failure output is sanitized in `backup-failure-redacted.log`.
- `native-runtime.json`: real production-mode native API/parser/worker/storage, cookies, public receipt/replay, scan-pending file rejection, 96 small-fixture timings and first separate restore. Its retained-database note describes an intermediate state; final cleanup is in `cleanup.json`.
- `complete-stack.json`: complete simultaneous native stack, actual production staff browser login, full HTTP domain workflow and representative row-by-row restore including placements, monthly income, outcomes and audit history.
- `additional-probes.json`, `immutability-and-sso.json`, `csv-formula-probe.json`, `failure-modes.json`: log/key failures, PostgreSQL audit tamper rejection, harmless arithmetic exported without formula neutralization, and actual dependency failures.
- `backend-cases.json` / JUnit: 144 unit and 155 integration cases; 299 passed. Parser JUnit: 22 passed. Substituted successful scans/parser recovery responses are described in the report.
- `17-blob-exact-local-verification.log`: full script passes functional/build/browser checks but stops on old pip in the audit environment. Logs 18â€“21 show the omitted README pip-upgrade step and successful remaining dependency checks. This is not represented as an exit-0 full-script invocation.
- `commands.json`: full command ledger with failed setup experiments retained. Labels 10 and 16 include audit harness argument/line-ending mistakes; these are not application defects. Labels 07/08 expose the missing parser dependency prerequisite. No failed experiment has been silently removed.
- Hosted CI and release branch snapshots are live GitHub readbacks. No branch protection or deployment was changed.

Audit helpers and the discarded fresh checkout were created in workspace `.local/readiness-20261020/`, outside the Git repository. The report's source paths and tests are the basis for reproducing each finding with fresh synthetic credentials; never reuse archived audit authentication state.

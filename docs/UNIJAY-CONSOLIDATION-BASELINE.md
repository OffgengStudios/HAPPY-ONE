# HAPPY consolidation baseline — 2026-10-27

Recorded before implementation changes. Remote fetch completed for both repositories.

| Repository | Local path | Branch at start | HEAD | Remote heads | Working tree |
| --- | --- | --- | --- | --- | --- |
| OffgengStudios/HAPPY-ONE | HAPPY_PLATFORM_CODEX_IMPLEMENTATION_SPEC | integration/happy-ecosystem | 9da0e8ed68a5c585b29dc5bda8c43a332a62fbbb | integration/happy-ecosystem: 15facc8272a8cd4329390a988ba0984cf5397452; main/development: 136cc95 | 25 modified tracked files and 11 untracked paths; existing hardening/local-production work preserved |
| OffgengStudios/UNIJAY-FASHION-DATA-COLLECTION | ../data-collection-tool-jobberman-revised | main | ce389b202e48aa3823a28942f453c421c187b135 | main: same HEAD | Code.gs and README modified; .apps-script untracked; preserved |

HAPPY implementation branch: feature/unijay-production-consolidation, created from local HEAD without discarding existing work. Repositories remain separate.

## Requirements and verification commands

HAPPY: Python >=3.12, PostgreSQL, private S3-compatible storage, pnpm 9.12, Node 22 in CI. Platform scripts: pnpm verify; pnpm api:test; pnpm api:lint; pnpm api:type-check; pnpm type-check. Targeted API: .venv/Scripts/python.exe -m pytest from HAPPY_PLATFORM_CODEX/apps/api. Integration tests require HAPPY_RUN_INTEGRATION=1, isolated loopback database schemas and private storage. CV parser: requirements-happy.txt; pytest tests/test_happy_service.py and tests-happy. UNIJAY: static HTML/CSS/JS; node --check data-collection-tool/app.js; existing legacy .apps-script/backend.test.cjs.

## Current implementation evidence

- UNIJAY app.js sends fullName, phone, dateOfBirth, ghanaCard, location, topicOfInterest array and consent:true to a script.google.com web app. No participant account flow. Local Code.gs already validates and persists topicOfInterest; the prompt's missing-field finding is stale for this working tree. Local backend changes must be retained.
- HAPPY intake routes.py exposes participant config and multipart POST with JSON payload plus optional CV. Versioned consent, origin checks, shared PostgreSQL rate counters, honeypot, encrypted evidence, advisory locks and idempotency exist. Public responses expose receipt_id and constant status only. Supply domain services create master records.
- Participant provenance is hard-coded HAMIS in routes, service, public actor, references and model CHECK constraints. New source needs an additive migration and access-control updates, retaining historical HAMIS values.
- api/v1/router.py unconditionally registers HAMIS machine routes, employer_portal routes and public intake router. That router contains public employer-intake endpoints. Employer portal is therefore still an operational Demand route.
- Supply Person has government_id_type, ciphertext and unique lookup hash. schemas.IdentityWrite and service.save_identity implement protected identity with identity encryption and keyed lookup. Intake currently has no identity field; sensitive profile is a different concept. Training summary exists, but there is no structured training_interests field.
- CV service only parses AVAILABLE CV documents; results are suggestions with explicit staff review before authoritative updates. Matching is an internal domain service. Preserve placement guard requiring actual start and verified first monthly income.
- Backup credential fix already exists in commit 4249c96: child-only PGPASSWORD, password-free argv, safe subprocess failures, safe CLI and alert failure types. Existing test_backup.py: 17 passed in this run. Additional scenario verification remains required.
- Worker fix already exists in 0a8c3d5: expired exhausted report leases become FAILED with RETRY_LIMIT_EXCEEDED and audit; live leases excluded; authorized versioned retry exists. Actual terminated-process test exists but has not yet been rerun.
- Further local commits: 63d01cc privacy-safe logging/OTLP; f89d9ad literal CSV export; 9da0e8e consistent bounded multipart limits. Existing uncommitted config adds startup Fernet validation and production preflight; review before extending.
- CI .github/workflows/ci.yml has platform, cv-parser, hamis, employer-intake and integration-contracts. Hosted execution has not been checked. Existing legacy tests must remain until replacements pass.
- Deployment: platform/render.yaml; root render-staging.yaml (integration branch); untracked root render-production.yaml (main, automatic deploy off). Both root manifests still contain old HAMIS and employer static services. Parser, API, staff, worker, backup/restore services have configuration seams; storage/scanner and credentials require provisioning. No deployment performed.

## Changes already present at start

Local HEAD includes audit documentation plus five fixes beyond the audited remote baseline. These were inspected before implementation. Existing edits concern configuration, IAM tests, frontend build/runtime, dependency versions, local production tooling, deployment/docs and intake browser harness. They are not assumed verified. No existing file was reverted, committed or pushed by this run.

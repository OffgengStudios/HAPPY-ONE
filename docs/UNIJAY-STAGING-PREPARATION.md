# UNIJAY and HAPPY staging preparation

Prepared 2026-10-27. This is a deployment preparation artifact, not evidence of a deployed or approved release.

## Repositories and release order

Keep repositories independent. Core work is on feature/unijay-production-consolidation based on local 9da0e8e, retaining six commits beyond remote 15facc8 and pre-existing uncommitted work. UNIJAY changes are on feature/happy-public-intake in the separate workspace checkout. Review both diffs and publish the collector implementation first; set HAPPY repository variable UNIJAY_INTAKE_REF to its reviewed branch/SHA. Current CI defaults to UNIJAY main, which does not yet contain this contract. Do not infer hosted success from local tests or the older green run.

For a private collector repository, provision UNIJAY_REPO_READ_TOKEN with read access to that repository; public checkouts can use the workflow token. Core CI uses a separate UNIJAY checkout, runs collector contracts/build, browser cases and backend collector-to-Supply acceptance. Retained adapter tests opt in only during backend regression. Legacy browser harness scripts/verify-intake.py is retained for deliberate testing, not the active public release.

## Deployable topology

Root render-staging.yaml targets the implementation branch and contains API, staff, worker, private parser and PostgreSQL. Root render-production.yaml remains a review-only template with automatic deployment off. Neither root manifest contains the old HAMIS or employer static services. Private object storage and a ClamAV-compatible scanner must be provisioned and connected via the configured endpoints; templates do not prove those services exist. The platform render.yaml is a retained older topology; use the root manifests for this consolidation and do not apply overlapping blueprints.

Deploy UNIJAY separately using its render.yaml and build.mjs. Only dist/ is public; Apps Script source and backend metadata are excluded. Set HAPPY_API_BASE_URL to the exact API HTTPS origin. Configure exact staff and collector origins in API_CORS_ORIGINS. Keep ENABLE_LEGACY_INTEGRATIONS=false. Do not set HAPPY_BUILD_LEGACY_INTAKES in a release environment.

## Secrets and policy

Provision database credentials, valid independent Fernet/lookup keys, private document and backup buckets, scanner endpoint, parser machine token and transport, authenticated staff identity provider/bootstrap, telemetry endpoint and alert destination. No secret belongs in collector config.js. Programme owners must supply approved privacy notice/version and required onboarding policy. Do not deploy synthetic notices or migrate Sheet data without a separate approved migration requirement.

Run preflight with the selected private environment file. Employer-intake notice is no longer a prerequisite. Migration 0037 expands provenance CHECK constraints without rewriting attribution; 0038 adds participant training_interests JSON with empty-list default. Normal data environments use forward migrations; downgrade removal is restricted to disposable synthetic schemas. Test migrations against staging-like data and take a verified backup before applying.

## Database capacity and outage bounds

The API/worker engine uses 5 pooled connections plus 5 overflow per process. This keeps the initial modular application pool small; calculate total capacity as process count × 10 plus administrative/headroom connections against the actual provider limit before rollout. DB_POOL_SIZE and DB_MAX_OVERFLOW are configurable. DB_CONNECT_TIMEOUT_SECONDS and DB_POOL_TIMEOUT_SECONDS default to 3 each, limiting a checkout/connect failure budget to roughly 6 seconds before scheduling overhead. DB_POOL_RECYCLE_SECONDS=1800 avoids indefinitely retained idle connections; pre-ping detects stale sockets. These are documented initial operational bounds, not a provider sizing claim. Storage already has 3-second connect/read timeouts and no SDK retries. Liveness does not query dependencies; readiness returns safe 503 responses.

## Required acceptance before recommending staging

- Green hosted CI for the reviewed implementation SHA and matching UNIJAY ref; branch/review controls verified.
- Real private scanner: clean PDF/DOCX, EICAR, unavailable/timeout, rescan, authorized/unauthorized download. Preserve fail closed; synthetic scan success in domain tests does not satisfy this.
- Real deployed backup storage upload and isolated restore exercise; retention/access controls and recovery objectives verified. Local real pg_dump/pg_restore scenarios passed with a synthetic database/role, but the provider adapter was synthetic.
- Actual alert delivery and monitoring for API, DB, storage, scanner, parser, worker heartbeat/queue/stale failures, backup/restore and auth anomalies. A configured webhook alone is insufficient.
- Deployed CORS/origin/abuse tuning, authentication/RBAC/CSRF, document privacy and PII-safe logging/exports validated.
- Staging golden flow and programme UAT. Confirmed Placement remains actual start plus first monthly income verified. Parser/matching decisions remain human-reviewed.

## Local reproduction

Set HAPPY_ENV_FILE to the existing private loopback configuration. Start PostgreSQL and private storage via existing app.db.local/app.storage.local commands. Run targeted pytest tests with HAPPY_RUN_INTEGRATION=1 and a new workspace-local --basetemp. For the complete retained-adapter regression suite only, set ENABLE_LEGACY_INTEGRATIONS=true. Active-architecture tests inspect a fresh default-disabled process. Run python scripts/ci.py or pnpm verify with UNIJAY_REPOSITORY pointing to the independent collector checkout. The optimized local launcher now serves /unijay/ and builds that checkout, with legacy integrations forced off.

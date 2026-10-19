# Staging

This is a provider-neutral staging configuration, not a production hosting decision.
Use synthetic data only. Place a TLS reverse proxy in front of the loopback API and
web ports. Only the reverse proxy should be reachable externally.

Create a root `.env.staging` from `.env.staging.example`, replace example domains
and all credentials, and keep it outside version control. The database password
inside `DATABASE_URL` must be URL-encoded and match `POSTGRES_PASSWORD`.
Use a different `DOCKER_POSTGRES_ADMIN_PASSWORD`. Fresh database volumes create
the application role without superuser, role-creation, or database-creation rights.
Initialization scripts do not modify existing volumes or accounts.

With Docker available:

```bash
docker compose --env-file .env.staging -f infra/deployment/compose.staging.yml build
docker compose --env-file .env.staging -f infra/deployment/compose.staging.yml up -d postgres object-storage
docker compose --env-file .env.staging -f infra/deployment/compose.staging.yml run --rm api alembic upgrade head
docker compose --env-file .env.staging -f infra/deployment/compose.staging.yml run --rm api python -m app.modules.iam.bootstrap --email administrator@example.org
docker compose --env-file .env.staging -f infra/deployment/compose.staging.yml run --rm api python -m app.storage.setup
docker compose --env-file .env.staging -f infra/deployment/compose.staging.yml up -d api web
```

Verify `/api/v1/health/ready` returns 200 through the staging API origin and the web
origin displays Staging. API readiness checks the database and private bucket.

For host-run services, set `HAPPY_ENV_FILE=.env.staging` before starting the API or
web. An explicit environment file excludes local development files. Process
environment values take precedence. Public frontend variables are fixed at build
time, so build with the intended staging API URL.

The staging database and S3 service are internal to the Compose network. Both app
containers run as non-root. The build context excludes secrets, local data, and
development dependencies.

Linux builds produce the standalone Next.js artifact used by the staging image.
Windows host builds use normal Next.js output to avoid requiring Windows symlink
privileges. Both are checked with the same browser tests.

Authentication uses the web service's same-origin `/api/v1` proxy to
`http://api:8000`. Preserve Origin and cookies through the TLS reverse proxy,
disable caching for API responses, and configure only trusted forwarded client
addresses. Staging/production session cookies require HTTPS. Bootstrap is
interactive and must use a unique staging password, not local credentials.
See `docs/25-PHASE-1-AUTH-IAM.md` for the unconfigured MFA-provider boundary.

The provider-neutral release, backup/restore, rollback, incident and secret-rotation
procedures are in [`docs/39-PRODUCTION-RUNBOOK.md`](../../docs/39-PRODUCTION-RUNBOOK.md).
Production deployment remains blocked until its named providers, RPO/RTO, alert
destinations and approval owners are selected.

For the selected Render application / Neon PostgreSQL topology, use the root
`render.yaml` and follow [`docs/45-RENDER-NEON-DEPLOYMENT.md`](../../docs/45-RENDER-NEON-DEPLOYMENT.md).

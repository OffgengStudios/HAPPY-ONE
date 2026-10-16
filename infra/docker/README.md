# Local Infrastructure

Phase 0 runs PostgreSQL and private S3-compatible storage locally.

Fresh PostgreSQL volumes use `init-app.sql` to create a non-superuser app role.
`DOCKER_POSTGRES_ADMIN_PASSWORD` is separate from `POSTGRES_PASSWORD`, which is
the app credential in `DATABASE_URL`. Existing volumes are not reinitialized.

```bash
docker compose up -d postgres object-storage
```

Application services can run on the host during development:

```bash
cd apps/api
../../.venv/bin/python -m uvicorn app.main:app --reload

cd apps/web
pnpm dev
```

On Windows use the root `pnpm api:dev` command. The PostgreSQL host port is
controlled by `POSTGRES_PORT`; do not start a container on a port already used by
the native project-local database.

Object storage requires `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` and does not
publish anonymous objects. Run `pnpm storage:setup` when using an existing S3
service. The API's readiness route verifies authenticated bucket access.

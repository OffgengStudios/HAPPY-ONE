# Render + Neon Deployment

Status: deployment configuration prepared; cloud resources and production approval
are not yet provisioned.

## Topology

- Neon hosts the authoritative PostgreSQL database.
- Render runs `happy-platform-api` and `happy-platform-web` from the repository's
  existing non-root Docker images.
- The web service proxies same-origin `/api/v1` requests to the API service. This
  preserves the current secure-cookie and CSRF model.
- CVs, campaign documents, and prepared report exports require private
  S3-compatible object storage. They must not be placed in Neon or on Render's
  ephemeral filesystem.
- File scanning and the real CV Parser remain separately configured private
  services. Leave uploads/parser execution fail-closed until those services exist.

## Before Creating The Blueprint

1. Push the reviewed repository to a Git provider connected to Render.
2. Create a Neon project in a region near the selected Render region.
3. Create a least-privilege HAPPY database role. Use a TLS-enabled connection
   string and replace the URL scheme with `postgresql+psycopg://` for SQLAlchemy.
4. Provision a private S3-compatible bucket with versioning, encryption, lifecycle,
   and access restricted to the HAPPY API credentials.
5. Confirm the Render service names are available. If either name changes, update
   `API_CORS_ORIGINS`, `API_INTERNAL_URL`, and `NEXT_PUBLIC_API_BASE_URL` together.

## Blueprint Secrets

Create the Blueprint from root `render.yaml`. Render prompts for every value marked
`sync: false`. At minimum supply:

- `DATABASE_URL`: Neon connection string using `postgresql+psycopg://` and TLS.
- `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and
  `S3_SECRET_ACCESS_KEY`.
- Approved Supply policy values. Use JSON arrays for required fields/sections.
- `FILE_SCAN_HOST` only when a reachable scanner is operational.
- `CV_PARSER_PROVIDER` and `CV_PARSER_MODEL` only after the Phase 7 adapter has a
  real approved transport.
- HAMIS and Employer Portal tokens only when their deployed producers are ready.

The Blueprint generates the identity encryption and lookup keys once. Back these
values up in the approved secret manager before writing encrypted identity data.
Rotating either key requires the controlled process in the production runbook.

## First Release

1. Render builds both services. The API pre-deploy command applies `alembic upgrade
   head` to Neon before the new API instance receives traffic.
2. Verify API liveness and readiness. Readiness requires both Neon and object
   storage, so a 503 is a real configuration failure and must not be bypassed.
3. From a one-off API shell, bootstrap the first administrator using the existing
   IAM bootstrap command. Enter the password through the command's protected local
   input; never add it to `render.yaml` or build arguments.
4. Verify the public web origin, sign-in, one permitted request, one denied request,
   logout, file storage, and audit events.
5. Run the release checks, backup evidence, monitoring checks, and approval gates in
   `docs/39-PRODUCTION-RUNBOOK.md` before treating the environment as production.

## Neon Operations

Use a pooled Neon connection for normal API traffic when compatible with the
approved migration rehearsal. Keep a direct owner connection separately protected
for administration and recovery. The application URL must not carry database- or
role-creation privileges. Define provider backup retention, point-in-time recovery,
RPO/RTO, and restore-rehearsal ownership before production launch.

## Important Boundary

The Blueprint prepares deployment but does not claim production readiness. Domain
policy approvals, MFA provider selection, scanner/parser availability, monitoring,
backup retention, restore rehearsal, and external-integration UAT remain explicit
release gates.

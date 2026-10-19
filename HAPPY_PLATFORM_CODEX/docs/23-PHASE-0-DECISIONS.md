# Phase 0 Engineering Decisions

Historical numbering: this is now Phase 1 Platform Foundation. These engineering
decisions and their original acceptance scope remain in force; see the revised
[roadmap](20-IMPLEMENTATION-ROADMAP.md) and
[foundation recheck](24-PHASE-0-VERIFICATION.md).

## Local Infrastructure

Docker Compose remains the portable infrastructure configuration. This Windows
workspace has no Docker engine, so local verification uses installed PostgreSQL
18 with project data on port 5433 and SeaweedFS 4.48 as an S3-compatible alternative.
The application remains PostgreSQL plus private S3 object storage.

SeaweedFS is a development/staging implementation option, not the approved
production storage provider. Releases are pinned and downloads are checked against
the official GitHub release asset SHA-256 digest. Local endpoints bind to loopback;
S3 requests require configured credentials, and anonymous access is tested.

Fresh Compose database volumes initialize a separate non-superuser application
role. The administrative password is distinct and is not used by the API
connection. Existing volumes and credentials are preserved.

Sources:
- [SeaweedFS official release](https://github.com/seaweedfs/seaweedfs/releases/tag/4.48)
- [S3 credential configuration](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API)

## CI Verification

The user selected local CI verification on 06 Oct 2026. `pnpm verify` is the Phase 0
acceptance command. It includes live PostgreSQL and S3 integration tests, browser
tests, formatting, lint, types, build, and dependency audits. The GitHub Actions
workflow runs the same command when a repository is connected. No hosted CI run is
claimed by the local result.

## Environment Selection

API and web load root development configuration with app-local overrides.
Process environment values take precedence. `HAPPY_ENV_FILE` explicitly selects
an isolated environment, and must point to an existing file. Only
`NEXT_PUBLIC_*` values are exposed to the frontend.

Staging configuration lives in `.env.staging.example` and `infra/deployment/`.
Production providers, SSO, brand assets, and programme policy remain open decisions.

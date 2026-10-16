# Versioning and Releases

## Current release

The HAPPY Management Platform release is `1.0.0-rc.1`.

This is a release candidate because the application scope is implemented locally,
while production provider verification, alert routing, off-site restore evidence,
SSO provider activation and deployment acceptance remain release gates.

## Product version

HAPPY uses Semantic Versioning:

- `MAJOR` changes for incompatible platform behaviour or data contracts.
- `MINOR` changes for backward-compatible features.
- `PATCH` changes for backward-compatible fixes.
- Pre-release identifiers such as `rc.1` identify non-final release candidates.

The root `VERSION` file is the human-readable release source. Package manifests,
deployment configuration and the API default version must be updated together.
Production deployments set `HAPPY_RELEASE_VERSION` and
`NEXT_PUBLIC_RELEASE_VERSION` to the same immutable release value.

## API version

The public API contract is independently versioned at `/api/v1`. Product patch,
minor and release-candidate changes do not change that path while they remain
backward compatible. A breaking API contract requires a new `/api/v2` router and
a documented migration and deprecation period; existing v1 endpoints are not
silently repurposed.

`GET /api/v1/health/live` and `GET /api/v1/health/ready` report both
`release_version` and `api_version`. OpenAPI reports the product release version.

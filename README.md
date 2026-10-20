# HAPPY Project Suite

This repository contains the four HAPPY applications as separate top-level projects:

- `HAPPY_PLATFORM_CODEX/` - HAPPY Management Platform, API, worker, and internal web application
- `CV-Parser-main/` - CV parsing service and its dedicated frontend
- `frontend/` - participant data-collection frontend
- `portal/` - Employer Acquisition Portal

The authoritative HAPPY Platform setup, architecture, roadmap, and verification
instructions are in [`HAPPY_PLATFORM_CODEX/README.md`](HAPPY_PLATFORM_CODEX/README.md).

HAMIS is a public data-collection form with local drafts and no participant
accounts. Employer Intake collects company/vacancy data for staff review. Both
submit to the central HAPPY API; the dedicated stateless CV Parser returns
suggestions requiring human review.

See the [integration assessment](docs/INTEGRATION-ASSESSMENT.md),
[API/client contracts](docs/INTEGRATION-CONTRACTS.md),
[legacy register](docs/LEGACY-DEPRECATION-REGISTER.md), and
[Render staging setup](docs/STAGING-RENDER.md).
Current test evidence and remaining deployment/UAT gates are recorded in the
[integration progress report](docs/INTEGRATION-PROGRESS.md).

Build the public frontends from the repository root:

```bash
node scripts/build-intake.mjs hamis
node scripts/build-intake.mjs employer
node --test integration/frontend.test.cjs
```

Set `HAPPY_API_BASE_URL` to the public HAPPY API origin when building for a
different host. The generated sites are `frontend/dist` and `portal/dist`.
The approved notice text/version must be configured on the API before public
intake opens; no credentials belong in frontend configuration.

## HAPPY Platform verification

Run platform commands from its project directory:

```bash
cd HAPPY_PLATFORM_CODEX
pnpm install --frozen-lockfile
pnpm verify
```

GitHub Actions runs the same verification from `HAPPY_PLATFORM_CODEX/`. The Render
Blueprint is located at `HAPPY_PLATFORM_CODEX/render.yaml` and uses the nested
platform directory as its Docker build context.

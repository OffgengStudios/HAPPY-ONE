# HAPPY Project Suite

For the optimized localhost application, see
[local build and startup](docs/LOCAL-PRODUCTION.md).

The active architecture is UNIJAY participant collection → HAPPY Public API → PostgreSQL → internal Supply, Demand, Matching, Placement and MERL.

- `HAPPY_PLATFORM_CODEX/`: API, internal staff web and durable workers.
- `CV-Parser-main/cv_system_output/happy_service.py`: private advisory parser; approved suggestions alone update Supply.
- UNIJAY is a separate repository: `OffgengStudios/UNIJAY-FASHION-DATA-COLLECTION`. The workspace checkout is a sibling of this repository.
- Private object storage, malware scanning and backup/restore are required operational dependencies.

UNIJAY has no sign-in and sends directly to HAPPY. Employer data is entered by authorized staff. `frontend/`, `portal/` and their adapters are retained legacy code, excluded from the default release. Historical records are preserved.

See [consolidation baseline](docs/UNIJAY-CONSOLIDATION-BASELINE.md), [current progress](docs/UNIJAY-CONSOLIDATION-PROGRESS.md) and [staging preparation](docs/UNIJAY-STAGING-PREPARATION.md).

See the [integration assessment](docs/INTEGRATION-ASSESSMENT.md),
[API/client contracts](docs/INTEGRATION-CONTRACTS.md),
[legacy register](docs/LEGACY-DEPRECATION-REGISTER.md), and
[Render staging setup](docs/STAGING-RENDER.md).
Current test evidence and remaining deployment/UAT gates are recorded in the
[integration progress report](docs/INTEGRATION-PROGRESS.md).
Production launch inputs, deployment order and remaining acceptance gates are in
the [production launch package](docs/PRODUCTION-LAUNCH.md), with a separate
[`render-production.yaml`](render-production.yaml) candidate.

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

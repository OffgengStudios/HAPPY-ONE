# Legacy deprecation register

The approved operational collector is UNIJAY; Demand starts with authorized staff in HAPPY.

| Component | Current state | Replacement | Release dependency | Removal condition |
| --- | --- | --- | --- | --- |
| HAPPY-ONE/frontend | LEGACY; SAFE TO DISABLE; release build blocked by default | Separate UNIJAY static collector | UNIJAY contract, Supply integration and desktop/mobile tests passed locally | Staging/UAT acceptance and reference cleanup; preserve historical evidence |
| portal | LEGACY; SAFE TO DISABLE; release build blocked | Internal Demand workspace | Internal organization/contact/partnership/vacancy regression | No pending submissions or accepted migration requirement |
| integrations/hamis | RETAIN TEMPORARILY FOR MIGRATION; routes/worker disabled by default | Public participant intake | Historical source attribution retained | Explicit disposition of pending legacy events; no automatic historical import |
| integrations/employer_portal | RETAIN TEMPORARILY FOR MIGRATION; routes disabled by default; staff inbox removed | Internal Demand services | Internal Demand acceptance | Pending-submission disposition and shared encryption helper extraction |
| Public employer-intake API | SAFE TO DISABLE; absent from active OpenAPI and routes | Staff-authenticated Demand API | Active-architecture test | Legacy evidence retention decision |
| Google Apps Script UNIJAY backend | LEGACY; excluded from static build | HAPPY public intake | Local UNIJAY contract/integration acceptance | Staging/UAT and authorized retirement; existing source preserved |
| Google Sheet operational storage | LEGACY; no new collector writes | PostgreSQL domain records | No historical import is authorized | Retention and historical migration policy decision |
| Legacy CV Parser candidate management | LEGACY; not part of happy_service.py runtime | Supply | Existing isolated parser Dockerfile | Confirm no external deployment dependency |
| Legacy parser matching | LEGACY; not part of HAPPY parser contract | HAPPY Matching | Approved-suggestion workflow | Existing consumer retirement |
| Legacy parser WhatsApp | SAFE TO DISABLE; excluded from HAPPY parser runtime | None | No WhatsApp policy | Historical code retirement decision |
| Legacy parser Google Sheets sync | SAFE TO DISABLE; excluded from HAPPY parser runtime | PostgreSQL | Parser isolated runtime contract | Existing consumer retirement |

ENABLE_LEGACY_INTEGRATIONS is false by default and forbidden in staging/production. It exists solely for development/test regression of retained adapters. HAPPY_BUILD_LEGACY_INTAKES=1 permits deliberate development/test builds only. The production manifests must exclude old static services. No domain capabilities or historical data are removed.

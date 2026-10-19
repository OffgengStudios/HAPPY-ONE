# Legacy deprecation register

| Legacy capability | Current dependency | Replacement | Removal condition | Status |
|---|---|---|---|---|
| HAMIS Apps Script actions | `frontend/js/api.js`, config and HTML | HAPPY participant intake API | Participant browser E2E, retries and isolation pass | Adapt |
| Google Sheets persistence | Legacy Apps Script endpoint; parser `google_sheets.py` | Central PostgreSQL domain | Intake/parser staging acceptance | Deprecate on HAPPY path |
| Direct Drive CV upload | HAMIS form handler | HAPPY private document upload | File/security/parser E2E passes | Adapt |
| Portal staff dashboard | Compiled `portal/assets/index-DOnYI7Z8.js` | Existing HAPPY staff workspaces | Employer-only source accepted | Isolate; retain artifact |
| Portal candidate management | Same compiled bundle | HAPPY Supply | Employer source has no candidate dependencies | Isolate |
| Portal matching | Legacy Portal capability, not a central domain | HAPPY Matching | Golden matching workflow passes | Do not integrate |
| Portal placement | Legacy Portal capability | HAPPY Placement | Actual start + verified income regression passes | Do not integrate |
| Parser candidate DB | Standalone `api/routes.py`, `database/` | Stateless HAPPY parser endpoint | Real PDF/DOCX contract and no persistence tests pass | Isolate |
| Parser Sheets sync | `google_sheets.py` and standalone routes | HAPPY authoritative records after human review | Stateless runtime and review E2E passes | Do not import |
| Parser matching | `matching/` | HAPPY Matching | Golden workflow accepted | Do not import |
| Parser WhatsApp | `whatsapp/`, migration/deployment docs | No replacement in scope | Separate cleanup decision | Isolate; never integrate |
| Apps Script forwarding adapters | Historical HAMIS/Portal deployment guides | Direct public HAPPY intake | New clients and staging UAT accepted | Keep compatibility for now |

Legacy files remain until their replacement is verified. No historical records
are imported, no production data is used as test data, and no legacy database
becomes a second HAPPY source of truth.

# Phase 12 - HAMIS / Data Collection Integration

Local adapter acceptance completed on 13 Oct 2026. No Google Sheet was imported
and no production endpoint or credential was configured.

## Inspected System

The implementation was based on `Murphy-Richard/happy-kollekt` revision
`0389cbac919844a2e13b34ea74b2775a03ce005a`, not the spreadsheet headers alone.
Kollekt is a static PWA with an IndexedDB offline queue. Its backend is Google Apps
Script and Google Sheets/Drive. Writes use action names plus client-generated
request/local-queue identifiers.

## Implemented Boundary

- `POST /api/v1/integrations/hamis/events` accepts authenticated server-to-server
  event envelopes.
- The credential is distinct from human users and audits as `INTEGRATION/HAMIS`.
- Event IDs are idempotent; changed content under an existing ID is rejected.
- Source payloads are encrypted at rest.
- Complete, non-duplicate new intake can create a HAPPY participant with HAMIS
  provenance and a generic external reference.
- HAPPY UUIDs and participant codes remain authoritative.
- Existing-record updates and duplicate candidates require staff review.
- Consent, training and placement events require authoritative HAPPY linkage and
  therefore enter review instead of changing domain records automatically.
- Admin-only list and rejection endpoints support the local review queue.

Migrations `0021_hamis` and `0022_hamis_encryption` implement the boundary. The
adapter contract is documented in `apps/api/app/integrations/hamis/README.md`.

## Security Decisions

- The machine token belongs in Google Apps Script Properties and a HAPPY secret
  manager, never in the public PWA, sheets or repository.
- Kollekt actor strings and sessions are not HAPPY identities or permissions.
- Government identifiers are not copied into HAPPY identity fields automatically.
- Source metadata cannot bypass HAPPY authorization or business rules.

## Verification

- focused HAMIS integration suite: 3 passed
- full backend suite with integrations enabled: 259 passed
- Ruff and strict mypy across 100 API source files: passed
- Alembic offline SQL generation: passed
- Alembic model drift: none at `0022_hamis_encryption`

Coverage includes authentication, idempotent replay, event conflicts, UUID/external
ID independence, provenance, encrypted storage, duplicate and update review,
non-participant staging, integration audit actors and admin-only review access.

## Deployment Gates

- provision the production API origin and a strong machine token
- install the server-side Apps Script bridge using the same write-event IDs
- configure retry/error monitoring without browser credentials
- perform staging UAT against non-production Kollekt
- approve privacy-notice and evidence mapping before consent conversion

Phase 12 is complete for the local HAPPY adapter scope. A live production HAMIS
connection is not claimed.

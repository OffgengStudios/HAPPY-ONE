# Phase 13 - Employer Acquisition Portal Integration

Local adapter acceptance completed on 14 Oct 2026. No production submission was
imported and no live Apps Script endpoint or credential was configured.

## Inspected System

The implementation was based on `offgengstudios/Happy` revision
`59403b1ec662025515c23f357af9130f6484026c`. The public React portal submits an
immutable partnership application to Google Apps Script, including company,
contact, consent, signature/document references and one or more vacancies.

## Implemented Boundary

- `POST /api/v1/integrations/employer-portal/submissions` uses a dedicated
  machine bearer token; it never authenticates as a staff user.
- Portal submission IDs are idempotency keys. Identical retries are safe and
  changed content under an existing key is rejected.
- Source payloads are encrypted at rest in a review inbox.
- Demand and Admin staff can review, reject, archive or convert submissions.
- Conversion reuses the authoritative Organization, Contact, Partnership,
  Vacancy and Requirement domains. Vacancies remain `DRAFT`.
- Duplicate employer names require explicit staff selection of the existing
  organization.
- HAPPY UUIDs remain primary keys. The portal submission ID is stored through a
  generic `EMPLOYER_PORTAL` external reference.
- Converted records use `source_system=EMPLOYER_PORTAL` and
  `created_via=INTEGRATION`.
- Receipt audits as `INTEGRATION/EMPLOYER_PORTAL`; human review and conversion
  retain the authenticated staff actor.

Migration `0023_employer_portal` adds the encrypted submission inbox and the
`employer_submission:view` and `employer_submission:manage` permissions. The
adapter contract is documented in
`apps/api/app/integrations/employer_portal/README.md`.

## Security And Authority

The inbox is evidence awaiting review, not a second employer database. Portal
metadata cannot grant permissions or skip normal HAPPY state transitions.
Conversion does not activate vacancies, sign an MOU, confirm a placement or
make uploaded document references trusted files. The machine token belongs in
Apps Script Properties and a production secret manager, never in the browser.

## Verification

- focused Employer Portal integration suite: 3 passed
- full backend suite with integrations enabled: 262 passed
- full desktop/mobile browser regression: 96 passed
- Ruff, strict mypy, ESLint, TypeScript, formatting and production build: passed
- Alembic current/model drift: `0023_employer_portal`, no new operations
- full offline migration SQL generation: passed
- fresh backup checksum/catalogue and isolated restore: passed at
  `0023_employer_portal`

Coverage includes machine authentication, encrypted storage, replay/conflict
handling, duplicate-organization review, domain conversion, provenance, external
references, integration/user audit attribution, permission denial and the
responsive Demand review journey.

## Deployment Gates

- provision the production API origin and strong machine token
- add the server-side Apps Script forwarding call after immutable submission
- configure retries, monitoring and credential rotation
- perform staging UAT with non-production portal submissions
- approve handling/storage for signature and document references
- approve and operate production backup cadence, off-site retention and RPO/RTO

Phase 13 is complete for the local HAPPY adapter scope. A live production Employer
Portal connection and production operational controls are not claimed.

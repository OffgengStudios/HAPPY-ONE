# Employer Acquisition Portal Adapter Contract

Inspected source: `offgengstudios/Happy` revision
`59403b1ec662025515c23f357af9130f6484026c`.

The deployed React portal submits immutable partnership applications to Google
Apps Script. Apps Script is the only permitted caller of HAPPY's machine endpoint;
the bearer token must never be bundled into the public portal.

## Endpoint

`POST /api/v1/integrations/employer-portal/submissions`

Use `Authorization: Bearer <EMPLOYER_PORTAL_INTEGRATION_TOKEN>` and forward the
successful `submitPartnership` record, including its original `submissionId`,
reference number, company/contact fields, consent flags, signature file identifier,
vacancies and linked document identifiers.

The submission ID is the idempotency key. A replay with identical content is safe;
the same ID with changed content returns `409`.

## HAPPY Ownership

The encrypted inbox is review evidence, not an employer system of record. A Demand
or Admin user converts an accepted submission into the existing HAPPY:

- Organization
- primary Employer Contact where one does not already exist
- Partnership
- draft Vacancies
- Vacancy Requirements for employment type

HAPPY UUIDs remain primary keys. The portal submission ID becomes a generic
`EMPLOYER_PORTAL` external reference on the Organization. Duplicate organization
names require staff to select the existing Organization explicitly. Conversion
never activates a vacancy, signs an MOU, places a participant, or bypasses normal
HAPPY authorization and state transitions.

## Deployment

Store the API URL and token in Apps Script Properties. Push only after
`submitPartnership` has produced an immutable record. Retry failures with the same
submission ID and alert on repeated failure. No live endpoint or secret is stored
in this repository.

# Render staging integration

`render-staging.yaml` prepares isolated API, staff web, HAMIS, Employer Intake,
private parser, worker and PostgreSQL resources. It uses distinct `happy-one-staging-*`
names and does not update the existing production blueprint. PostgreSQL denies
public IP access. The parser runs privately and shares its generated token only
with the backend/worker. Public frontends receive only the public API origin.

The configuration follows the [Render Blueprint reference](https://render.com/docs/blueprint-spec).
It was validated locally against Render's published JSON schema. This is structural
validation, not an actual deployment or verification of an account. The user has
confirmed that Render is not set up yet.

Before applying it to a new Render workspace:

1. Create the intended workspace and select the approved region and service plans.
2. Use a separate staging database, private S3 bucket and credentials. Never point
   staging at production records or storage.
3. Set the API's `sync: false` inputs: private storage settings, a generated Fernet
   key and independent lookup key, exact HTTPS origins for all three frontends,
   approved privacy notices and required onboarding sections/fields, and a private
   scanner endpoint. The worker references the API's private values.
4. Apply the blueprint from the integration branch only after hosted CI passes.
   Each service currently tracks `integration/happy-ecosystem`; change all service
   branches together when promoting the reviewed integration to a long-lived branch.
   Review the resources Render resolves before applying; `checksPass` prevents
   deploying commits whose checks have failed.
5. Confirm API readiness, private parser connectivity and scanner behavior. Run
   worker outage/restart and scan-unavailable recovery with synthetic documents.
6. Bootstrap staff through the existing administrator CLI; do not create participant
   accounts. Run UAT for Supply, Demand, Matching, MERL, Marketing, Management,
   Admin, participant and employer.
7. Reconcile a known synthetic dataset with reporting, then remove the UAT records
   through approved cleanup procedures and verify storage/test-data cleanup.

The deployment still requires account access and approved environment inputs.
There is no claim of a live staging environment, role-based human UAT or production
readiness solely from the blueprint or local test suite.

Local verification:

```powershell
cd HAPPY_PLATFORM_CODEX
pnpm verify
python ../scripts/verify-intake.py
```

Use `PLAYWRIGHT_CHANNEL=msedge` where Chromium is not installed on Windows, or
install the project Playwright Chromium as in CI. Both browser harnesses create
isolated synthetic PostgreSQL schemas and clean their private documents.
If a local preview already uses port 8765, set `HAPPY_INTAKE_TEST_PORT` to an unused
port before running `verify-intake.py`; the harness uses the same port for its
server, browser origin and isolated API CORS settings.

# Optimized local application

The local suite serves the optimized Next.js build, public participant form and
employer form through loopback addresses. It runs its own API and durable worker
against the selected local PostgreSQL and private storage configuration.

From `HAPPY_PLATFORM_CODEX`:

```powershell
pnpm local:production build --env-file .local/runtime/working.env
pnpm local:production start --env-file .local/runtime/working.env
pnpm local:production status
pnpm local:production stop
```

Choose the private environment file that contains the intended local settings.
The build and start commands must use the same file. The default is the existing
`.local/runtime/working.env`; supply another path explicitly when using approved
configuration. Credentials stay in the selected file and child-process environment.
The launcher reports URLs and process state without printing configuration values.

| Application | Address |
| --- | --- |
| Staff workspace | http://localhost:3300 |
| Participant registration | http://localhost:8865/hamis/ |
| Employer intake | http://localhost:8865/employer/ |
| API readiness | http://127.0.0.1:8100/api/v1/health/ready |

The API and worker load the selected environment. The launcher adds the exact
loopback staff/public origins to CORS. The staff build proxies to port 8100;
the public server serves only the built public sites and proxies their intake
requests to the same API. All application listeners bind to `127.0.0.1`.

Build output is `.next-local-production`, with a separate TypeScript configuration
and incremental cache. Normal development/CI output remains `.next`. Logs and
tracked process state are under `.local/local-production`. The stop command
validates process identity before stopping only the processes it launched.
Existing development services and the local database/storage processes are
managed separately. Ports 3300, 8100 and 8865 must be free before starting.
Stop the tracked suite before rebuilding. The launcher refuses to replace assets
while its optimized server is running.

PostgreSQL and private storage must already be running, and the database must be
migrated. With the intended file selected, the existing commands are:

```powershell
$env:HAPPY_ENV_FILE = '.local/runtime/working.env'
pnpm db:local
pnpm storage:local
pnpm api:migrate
```

The local HTTP launcher requires development/test API settings and a loopback
database. The web application uses its optimized production assets. This preserves
the API's local HTTP cookie behavior. Use the existing staff account, or bootstrap
the first administrator with `pnpm iam:bootstrap` if the database has no accounts.

Programme gates remain enforced. Until the approved privacy/onboarding settings
and real scanner/parser are configured, their dependent flows remain gated;
an uploaded document does not become clean merely because this build is optimized.
The currently discovered `working.env` contains explicitly labelled development
notices with onboarding approval disabled and no scanner/parser endpoints.
Approval was reported by the user, but its configuration location has not yet been
identified in this checkout. Select that file when available rather than replacing
approval settings with assumptions.

Future hosted production preparation is documented separately in
[`PRODUCTION-LAUNCH.md`](PRODUCTION-LAUNCH.md).
Current local evidence is in
[`LOCAL-VERIFICATION-2026-10-24.md`](LOCAL-VERIFICATION-2026-10-24.md).

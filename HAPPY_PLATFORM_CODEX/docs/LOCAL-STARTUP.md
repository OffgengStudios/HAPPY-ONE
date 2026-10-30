# HAPPY — Manual Local Startup

These instructions start the existing local self-test installation on this Windows computer. Dependencies, private configuration and the database are already installed. Use synthetic participant data with the self-test notice.

## 1. Open PowerShell in the project folder

```powershell
cd "C:\Users\jobbe\Downloads\HAPPY ONE\HAPPY_PLATFORM_CODEX_IMPLEMENTATION_SPEC\HAPPY_PLATFORM_CODEX"

$env:HAPPY_ENV_FILE = ".local/runtime/self-test.env"
$env:PYTHONPATH = "$PWD\apps\api"
```

Run the remaining commands in this PowerShell window.

## 2. Start PostgreSQL if it is stopped

```powershell
$pgControl = "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe"

& $pgControl -D ".local\postgres\data" status

if ($LASTEXITCODE -ne 0) {
    & $pgControl -D ".local\postgres\data" -l ".local\postgres\server.log" -o "-h 127.0.0.1 -p 55433" -w start
}
```

This uses the existing database cluster at `127.0.0.1:55433`.

## 3. Start storage, the scanner and CV parser

```powershell
.\.venv\Scripts\python.exe scripts/api.py storage-local start

.\.venv\Scripts\python.exe "..\.local\launch\start-self-test.py"
```

Wait until the helper reports that the database, storage, real ClamAV scanner and private CV parser are ready. Resolve any reported failure before continuing.

The helper prepares the local self-test environment and reuses the local staff login. It does not rebuild the application.

## 4. Start HAPPY

```powershell
.\.venv\Scripts\python.exe scripts/api.py local-production start --env-file .local/runtime/self-test.env
```

This starts the optimized staff application, API, background worker and public intake service. They run in the background.

## 5. Open the application

| Service | Link |
| --- | --- |
| HAPPY staff workspace | [http://localhost:3300/](http://localhost:3300/) |
| Participant intake | [http://localhost:8865/unijay/](http://localhost:8865/unijay/) |
| API readiness | [http://localhost:8100/api/v1/health/ready](http://localhost:8100/api/v1/health/ready) |
| Private CV parser health | [http://localhost:8130/api/v1/health](http://localhost:8130/api/v1/health) |

The parser health link is a status endpoint. Staff use the parser through HAPPY's participant document workflow.

Local staff login details are stored privately in `.local/self-test/access.json`, relative to the project folder. Keep credentials out of shared documents and screenshots.

## Check application status

```powershell
.\.venv\Scripts\python.exe scripts/api.py local-production status
```

If the application is already running, use its links. To restart it, follow the next section.

## Restart HAPPY

```powershell
.\.venv\Scripts\python.exe scripts/api.py local-production stop

.\.venv\Scripts\python.exe scripts/api.py local-production start --env-file .local/runtime/self-test.env
```

After a computer restart, repeat the full startup sequence so the dependencies are started too.

## Stop HAPPY's application services

```powershell
.\.venv\Scripts\python.exe scripts/api.py local-production stop
```

This stops the managed API, worker, staff application and public intake service. PostgreSQL, storage, the scanner and parser remain separate services.

## Rebuild after code changes

Stop the application before rebuilding. Use the same environment file for build and start:

```powershell
.\.venv\Scripts\python.exe scripts/api.py local-production stop

.\.venv\Scripts\python.exe scripts/api.py local-production build --env-file .local/runtime/self-test.env

.\.venv\Scripts\python.exe scripts/api.py local-production start --env-file .local/runtime/self-test.env
```

Start only after the build succeeds. An ordinary daily startup does not require a rebuild.

If a code update includes database migrations, apply that update's documented backup and migration procedure before starting it. These startup commands do not apply migrations automatically.

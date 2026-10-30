# HAPPY-ONE Local Production Readiness Audit

Audit date: 20 October 2026 (UTC / Africa–Accra). Initial audit only: application source, dependencies in the original checkout, business policy, GitHub settings and deployments were not changed. All runtime writes used synthetic data in separate audit databases/storage. This report supersedes earlier readiness claims for the revision below.

Status terms: **VERIFIED** means demonstrated by the stated inspection or execution; **PARTIALLY VERIFIED** means narrower evidence or an explicit substitute; **NOT VERIFIED** means no sufficient execution evidence; **FAILED** means an observed requirement failure; **NOT APPLICABLE** means outside the agreed architecture. Passing a test does not prove its external dependencies or every failure mode.

## 1. Executive Verdict

**LOCALLY INTEGRATED — Level 2/5. Confidence: HIGH for the demonstrated defects and local workflows; MEDIUM for overall operational readiness.**

The ecosystem supports real central PostgreSQL records, staff authorization, direct public intake, private storage, advisory parsing, placement and income verification, and durable report exports. It is **not staging ready** under this audit's acceptance gate. Two P0 defects remain: backup failure output discloses database passwords, and a worker killed on its final claim can strand a report job permanently. Production privacy, export safety, deployment alignment and operational validation also remain incomplete.

Local production-mode execution is useful evidence, but does not meet Level 3: there are P0 defects, no actual antivirus service, no deployed monitoring/alerts, and no hosted recovery evidence. Level 5 cannot be established by a local audit. Continue development and controlled synthetic local integration; do not load real participant data into a release environment yet.

## 2. Verified Baseline

| Item | Observed baseline |
|---|---|
| Repository | `OffgengStudios/HAPPY-ONE`, public; actual Git root is `HAPPY_PLATFORM_CODEX_IMPLEMENTATION_SPEC/` under the supplied workspace |
| Audited branch / commit | `integration/happy-ecosystem` / `15facc8272a8cd4329390a988ba0984cf5397452` |
| Commit date | `2026-10-20T10:54:32Z` |
| Release / migration head | `1.0.0-rc.1` / `0036_vacancy_terms` |
| Original working tree | Clean before audit; only this report and its evidence are added by the audit |
| Fresh source | Separate Git archive and new virtual environment / frozen Node install; final verification copy matches Git blob LF contents |
| Native runtimes | Python 3.12.10, Node 24.16.0, pnpm 9.15.9, PostgreSQL/client tools 18.4, Microsoft Edge |
| CI / container targets | Python 3.12; Node 22; pnpm 9.12.0; CI PostgreSQL 16. Native execution is not a container-image test |
| Unavailable locally | Docker engine/CLI and ClamAV binaries; no Render environment exists |
| Release branches | `main` and `development` at `136cc959539e2b311be60f289211f18e8f4f9c41`; integration branch not merged; all three branches unprotected |
| PR | [Draft PR #1](https://github.com/OffgengStudios/HAPPY-ONE/pull/1), integration → development, open |

Tracked layout is preserved: `HAPPY_PLATFORM_CODEX/` contains the staff platform/API; `frontend/` is HAMIS; `portal/` contains maintained employer intake plus isolated legacy code; `CV-Parser-main/` contains the processing service plus excluded standalone legacy code. Same-named folders outside the Git root are not the release source. PostgreSQL is authoritative; no Google Sheets or WhatsApp component is required or activated.

Evidence is under [audit-evidence/2026-10-20](audit-evidence/2026-10-20/). Audit helpers/raw logs were created outside Git in workspace `.local/readiness-20261020/`. After verification the audit databases, role, bucket/objects and storage process were removed, along with private state, credentials, TLS private key and dump archives. Original PostgreSQL/storage were preserved; `cleanup.json` records scope. Only sanitized evidence is included here.

## 3. Component Readiness

| Component | Status | Evidence / practical limit |
|---|---|---|
| HAPPY API | PARTIALLY VERIFIED | Fresh migration, real HTTP workflows and production settings executed; P0/P1 findings remain |
| Staff Web | PARTIALLY VERIFIED | Production build and desktop/mobile browser gate; complete production-mode stack result in evidence |
| PostgreSQL | VERIFIED locally | Fresh non-superuser application role/database, migrations, drift check, real transactions and separate restores; managed PostgreSQL 16 remains untested locally |
| HAMIS | PARTIALLY VERIFIED | Direct no-sign-in flow; desktop/mobile live submissions, drafts, validation, bounded upload, replay controls; real scanner/provider acceptance pending |
| Employer intake | PARTIALLY VERIFIED | Live public submission → staff conversion → central employer/contact/draft vacancy; internal document upload size mismatch |
| CV Parser | PARTIALLY VERIFIED | Real PDF HTTP parse and machine-token rejection; 22 service/contract tests; integrated golden test uses a substituted successful scan |
| Background worker | FAILED | Real report export succeeds; terminated final-attempt report claim never reaches terminal/reclaimable state |
| Private storage | VERIFIED locally | Actual authenticated SeaweedFS; anonymous object GET 403, unscanned download 409; hosted encryption/versioning/retention not verified |
| Document security | PARTIALLY VERIFIED | PDF/DOCX structure/size/checksum checks; scanner absence fails closed; no real clean/infected ClamAV run |
| Staff authentication | PARTIALLY VERIFIED | Production Secure/HttpOnly/SameSite cookies, CSRF, permissions and negative probes; live organizational SSO/MFA recovery policy remains external |
| RBAC | VERIFIED for exercised paths | Backend and browser roles/denies; anonymous internal routes 401 and Marketing placement mutation 403; final organizational field matrix still needs approval |
| Audit / provenance | VERIFIED for exercised paths | Integration/source attribution; real PostgreSQL UPDATE and DELETE against audit history rejected with SQLSTATE P0001 |
| Reporting / exports | FAILED | Counts and durable export success verified; final-lease recovery and CSV formula neutralization fail |
| Backup creation / validation | PARTIALLY VERIFIED | Actual custom-format pg_dump and checksum/catalogue validation; failure path leaks password; offsite security/scheduler unverified |
| Database restore | VERIFIED locally | Actual separate-database pg_restore, revision and representative row comparison; full workflow evidence includes placement/income/history |
| Full disaster recovery | NOT VERIFIED | Database archive does not contain private S3 objects or encryption keys; coordinated file/key restoration, RPO/RTO and provider exercise remain open |
| Documentation | FAILED for bootstrap completeness | README API-only install cannot run parser-dependent golden test without additional dependencies; older architecture statements conflict with current source |
| CI / release | PARTIALLY VERIFIED | Hosted five-job gate green at audited SHA; local execution described below; no protected release branches or deployed artifact verification |

## 4. Critical Business Rules

| Requirement | Status | Evidence and enforcement boundary |
|---|---|---|
| Actual start + authorized first monthly income → confirmed placement | VERIFIED through API | Production HTTP flow: START_PENDING → AWAITING_FIRST_INCOME → CONFIRMED; start alone has no confirmation timestamp |
| Duplicate confirmation cannot increase achievement | VERIFIED for replay | Repeating confirmation returns existing success; headcount remains started=1, confirmed=1, outstanding=2 of required=3 |
| Exit preserves historical confirmed achievement | VERIFIED in integration suite | Placement/MERL tests and service/reporting logic retain confirmed_at; no new independent live exit probe |
| Onboarding / active consent before formal employer submission | VERIFIED in integration suite and positive HTTP flow | Matching service checks central records, not public-client declarations |
| Employer submissions require staff conversion | VERIFIED through HTTP | Public intake creates review work; converted vacancy starts DRAFT and staff activates it |
| Vacancy-specific candidacy and human decisions | VERIFIED for exercised flow | Separate candidate-vacancy record, screening, interview attendance/outcome and employer decision before placement |
| Derived headcount and separate starts/confirmations | VERIFIED through HTTP | required=3, started=1, confirmed=1, outstanding=2; no manual outstanding edit |
| Parser advice has no authority before human review | VERIFIED in golden integration test | Actual parser suggestions do not change profile before staff review; successful scan is substituted in that test |
| HAMIS creates no participant authentication identity | VERIFIED | Public submission sets no cookies; staff-user count remains one pre-existing bootstrap admin; only receipt/status returned |
| Public duplicate / idempotency / provenance | VERIFIED for exercised paths | Identical replay returns same receipt; altered reuse of submission ID returns 409; possible duplicates enter staff review without disclosing identities |
| Audit history append-only | VERIFIED at PostgreSQL boundary | Independent UPDATE and DELETE rejected; application tests additionally cover event attribution |
| Archive, optimistic versions, consent, training and marketing gates | VERIFIED within existing tests | Tested service/API/browser paths; no assertion that all possible cross-module interleavings were exercised |

Important boundary: the database checks actual-start presence and confirmation timestamp, but the cross-table first-income prerequisite is enforced by application services. Database administrators/import tools remain privileged. This audit did not find a public API route bypassing that rule. Arbitrary database editing is not an approved operational workflow.

## 5. Security Findings and Verification

**FAILED:** plaintext database credentials in failed backup command traceback (P0-01); raw search terms and OIDC callback codes in default Uvicorn access logs (P1-01); public form text emitted as executable spreadsheet formula cells (P1-02); invalid Fernet key accepted by production Settings (P1-04).

**VERIFIED for tested paths:** staff server-side permission checks and explicit denies; no anonymous Participant CRUD; credential-free public frontend contracts; strict public schemas rejecting staff fields; request/body/file limits; database-backed public throttling and honeypots; idempotency and duplicate-review handling; private random object keys and authorized downloads; scan-pending files blocked from download and parser queueing; privacy notice version checks; production session cookie flags; CSRF; stale version rejection; structured safe public errors; append-only audit.

The real absent-scanner test produced SCANNING, zero parser jobs, authorized download 409 and anonymous object GET 403. That proves fail-closed behavior, not virus detection. Existing tests substitute scan success; they cannot certify ClamAV signature updates or infected-file rejection by a deployed engine.

HAMIS and employer builds contain none of the actual audit database, S3 secret, identity encryption/lookup key or parser token (artifact checks in complete-stack evidence). A limited tracked-source secret-pattern scan found no matching secrets among 552 tracked files; it is not a full Git-history or third-party penetration test. Staff and participant identities remain separate. Production staff SSO availability, MFA enforcement policy, key rotation/recovery, field-level approvals and deployed secret-manager access are NOT VERIFIED.

HAMIS currently executes an external unpinned `cdn.tailwindcss.com` script. Public static deployment headers/CSP are not established by the local build. Review this third-party execution path on a participant-data page before real data collection (P1-07). The staff web has explicit security headers/CSP; local audit static servers do not prove provider headers.

## 6. Reliability and Recovery

**FAILED:** real worker termination after committed final claims, followed by lease expiry and a new claim attempt, leaves report RUNNING and optional legacy HAMIS event PROCESSING forever. Both have attempts=max, no completion timestamp and no reclaim (P0-02). The public HAMIS intake route is distinct from that retained legacy event adapter. The CV worker already handles its exhausted lease; do not generalize this defect to all workers.

**VERIFIED:** two simultaneous independent report claim transactions choose distinct pending jobs; normal durable export completes in a separate worker, stores private CSV and downloads with authorization; parser retry/lease/final-failure paths pass integration tests, with a substituted restored parser response in the recovery test; real stateless parser HTTP call succeeds separately.

**PARTIALLY VERIFIED:** database outage leaves liveness 200; readiness initially exceeded the 15-second client deadline with application defaults. With explicit `PGCONNECT_TIMEOUT=3`, database readiness returns safe 503 in 3.892 s; failed S3 returns safe 503 in 2.895 s. The operations worker exits 1 on database failure. Recovery therefore depends on external restart supervision, which is not deployed or verified. Add bounded database connection settings and demonstrate provider restart/backoff/alerting (P1-05).

Local dump/checksum/restore uses real PostgreSQL tools and a separate disposable database. The first archive was 315,804 bytes; backup 1.292 s, built-in restore 21.935 s, revision 0036_vacancy_terms, and independently restored representative rows matched. The final full-workflow archive was 323,401 bytes; backup 0.766 s and restore 6.912 s. Independent restoration matched all 14 checked tables, including three participants, one employer/contact/vacancy, one placement/first-income verification/outcome and 54 audit events. These timings do not establish production RTO. Private document bytes are outside the database dump; file/key recovery is a separate requirement.

NOT VERIFIED: managed backup schedule/retention/deletion, offsite encryption/access policy, restore alert receipt, stale-job monitoring, release rollback against representative production volume, real scanner outages/restoration, machine-token/key rotation during queued jobs, process/host restart under sustained load, and all requested domain concurrency combinations. Version/row-lock/uniqueness mechanisms exist, but actual simultaneous overfill starts and simultaneous document versions were not independently exercised.

## 7. Exact Test Results

Counts below identify unique cases, not the sum of repeated runs. Results are recorded from the completed command ledger, JUnit and console logs; setup experiments are distinguished below.

| Check | Passed | Failed | Skipped | Duration / source |
|---|---:|---:|---:|---|
| Backend unit cases | 144 | 0 | 0 | 5.336 s summed case time; audit pytest classification |
| Backend integration cases | 155 | 0 | 0 | 178.106 s summed case time; actual PostgreSQL/private storage; individual dependency substitutes noted above |
| Backend combined | 299 | 0 | 0 | 189.35 s pytest wall time, 189.324 s JUnit suite time; one dependency deprecation warning |
| Parser contract + runtime/service | 22 | 0 | 0 | 2.59 s pytest; 3.949 s command wall time; 14 contract + 8 service cases |
| Public frontend Node contract checks | 5 | 0 | 0 | 310.905 ms Node suite, 0.666 s command wall time |
| Shared environment/config checks | 4 | 0 | 0 | 445.299 ms Node suite in final local gate |
| Staff desktop/mobile browser cases | 100 | 0 | 0 | 50 desktop + 50 mobile; 9.8 min as reported by Playwright |
| Public live browser journeys | 4 scenarios | 0 | 0 | Participant + employer on desktop + mobile; 65.149 s command wall time; not a pytest count |
| HAMIS / employer builds | 2 commands | 0 | N/A | 0.291 / 0.267 s |
| Python dependency consistency | 1 command | 0 | N/A | 1.034 s after documented pip upgrade |
| Python dependency audit | 1 command | 0 | 1 editable distribution excluded | 3.123 s after documented pip upgrade; no known vulnerabilities reported |
| JavaScript production dependency audit | 1 command | 0 | N/A | 1.184 s; no known vulnerabilities reported |

Independent probes are experiments, not additional unit-test counts: worker crash/expired lease, concurrent claims, actual >512 KiB upload, public replay/permission denial, production cookies, scan-pending private objects, full HTTP business workflow, arithmetic CSV formula, database audit tampering, outages, local restore and measured requests. See each JSON evidence file.

Fresh documented bootstrap: API `[dev]` install and frozen Node install succeed, but `import pdfplumber; import docx` fails at pdfplumber. The selected golden test then reports **1 failed, 298 deselected** because its real parser cannot start. Installing the parser requirements, as hosted CI does, enables the full backend pass. This remains a documentation/bootstrap finding; no production source was patched.

Audit harness errors are not project defects: an initial Windows JUnit argument was misquoted (pytest collected zero); the first archive inherited global `core.autocrlf=true` and produced 79 formatting warnings. The final copy was re-extracted with `core.autocrlf=false` and checked against Git blobs. The fresh environment initially omitted the README's pip-upgrade step: the full script stopped on 12 advisory entries for pip 25.0.1 (repeated identifiers, not 12 distinct application vulnerabilities). Executing that documented step installed pip 26.2.2; dependency consistency, Python audit and the previously unreached JavaScript audit then passed separately. Failed early native probes used an incorrect employer payload, an unintended duplicate person and an unavailable Python Playwright import; the browser probe uses the installed Node package instead. The initial readiness timeout is retained as observed operational evidence. These setup failures are excluded from application-suite failure totals and are preserved in the command ledger.

## 8. CI Status

**Hosted CI: VERIFIED GREEN** at the exact audited SHA. [Run 39411245030](https://github.com/OffgengStudios/HAPPY-ONE/actions/runs/39411245030), completed 2026-10-20T11:04:42Z: platform, cv-parser, hamis, employer-intake and integration-contracts all success. Live `gh run view` reconfirmed this during audit.

**Local: all required component checks passed; the single full-script invocation ended FAILED because of the audit environment's omitted pip-upgrade prerequisite.** Its exact result was exit 1 in 963.031 s. Formatting, Ruff, strict mypy (127 files), migration/drift, all 299 backend cases, frontend formatting/lint/types, four config cases, production build and all 100 browser cases passed before that failure. After applying the already documented pip upgrade to the disposable environment, dependency consistency and both Python/JavaScript vulnerability audits passed separately. The full 16-minute script was not repeated; this is not a claim of an exit-0 full-script run. Hosted CI remains independently green. The parser install prerequisite was also added only to the separate audit environment.

Reproduction from correctly configured private local infrastructure: install API `[dev]`, install `CV-Parser-main/cv_system_output/requirements-happy.txt`, frozen pnpm install; run migrations/storage setup and `python scripts/ci.py`; run `python ../scripts/verify-intake.py`; run parser tests and `node --test integration/frontend.test.cjs` from their documented roots. Environment secrets must come from private files/environment, not commands pasted into logs. The audit helpers remain outside production source.

## 9. Production-Like Local Stack

Docker is absent; native fallback was used. Successfully started real PostgreSQL 18.4, authenticated private SeaweedFS, `APP_ENV=production` HAPPY API, stateless parser HTTP service and separate operations worker. Production configuration uses generated strong credentials and a valid Fernet key. Local HTTPS uses an audit-only reverse proxy and explicitly trusted, short-lived self-signed certificate. This is not a production ingress implementation.

The complete-stack probe additionally built/started the production Next staff server and both public static distributions against the same API: staff/HAMIS/employer/readiness all returned 200 simultaneously. The production web build took 39.841 s and real staff browser sign-in passed over HTTPS. Exact results and the post-workflow restore are in `complete-stack.json`. The earlier public desktop/mobile journeys use the repository's isolated test API.

Not started: actual ClamAV, Docker/container builds, managed PostgreSQL, hosted S3, real OTLP collector/dashboard, alert delivery, scheduled cloud jobs, Render services, public DNS/CA certificates and organizational SSO. Production-mode telemetry/alert endpoints were deliberately configured to unreachable loopback HTTPS addresses to keep the audit self-contained; configuration acceptance is not provider verification. Synthetic notice text and an explicit test-only onboarding policy are not programme approval.

Actual sequential HTTP measurements (12 requests per endpoint, 96 total; two synthetic participants, one employer and one vacancy at measurement time):

| Endpoint | Mean ms | Median ms | p95 ms |
|---|---:|---:|---:|
| Participant list | 529.90 | 552.51 | 727.96 |
| Participant search | 429.82 | 402.83 | 703.69 |
| Employer list | 369.55 | 376.64 | 453.34 |
| Vacancy list | 464.98 | 465.35 | 739.42 |
| Demand dashboard | 459.08 | 429.03 | 723.67 |
| Supply dashboard | 354.84 | 342.40 | 433.50 |
| KPI report | 626.86 | 625.55 | 1052.79 |
| CV document-version metadata | 486.39 | 438.08 | 897.30 |

Nearest-rank p95 of 12 samples is the maximum. Measurements include the audit Python HTTPS proxy/client-creation overhead and concurrent verification work; they are not isolated API/database benchmarks. No approved latency SLO or representative production data volume was supplied. Production capacity, sustained concurrent load, matching at scale and large-export memory remain NOT VERIFIED; no internet-scale performance claim is made.

## 10. P0 Blockers

P0 means fix before a release staging deployment or use of real data. These are observed software defects, separate from missing hosting inputs.

| ID | Blocker | Evidence | Required fix | Verification |
|---|---|---|---|---|
| P0-01 | Backup failure discloses database password | `db/backup.py:67,98,147`: password-bearing URL passed in pg_dump/restore argv; real failure emits CalledProcessError containing the password. `runtime-probes.json`, redacted failure log | Keep credentials out of subprocess arguments, sanitize exceptions/CLI/scheduler logs; include restore-admin credentials in the review | Fail real dump and restore with sentinel credentials; assert absent from stdout/stderr/logs and subprocess argv; successful backup/restore still passes |
| P0-02 | Final-attempt worker death strands report job | `modules/reporting/worker.py:25–49`, `integrations/hamis/worker.py:20–44`: attempts filter excludes expired final claim. Actual child terminated, 30-second lease expired; report RUNNING / legacy event PROCESSING remain unreclaimable | Reconcile exhausted expired leases into explicit terminal failure with audit/error and authorized retry; apply equivalent semantics to both adapters without bypassing live leases | Kill actual worker after final committed claim, wait real lease expiry, restart; verify terminal/audited state, safe retry and no duplicate side effects; retain distinct-claim concurrency check |

Paths in findings are relative to `HAPPY_PLATFORM_CODEX/apps/api/app/` unless explicitly prefixed otherwise. Crash probe configured the supported maximum of one attempt and a 30-second lease to exercise the exhausted-final-claim path; the same predicate governs the default five-attempt setting.

## 11. P1 Requirements

P1 means required before production; selected operational controls also gate staging configuration. These are not all P0 software defects.

| ID | Requirement | Evidence | Required fix/action | Verification |
|---|---|---|---|---|
| P1-01 | Remove sensitive query values from access logs/telemetry | Actual search marker and actual `/auth/sso/callback?code=...` marker logged by production Uvicorn; Docker command leaves access log enabled; `additional-probes.json`, `immutability-and-sso.json` | Use redacted structured access logging; disable/sanitize parallel default logger; explicitly constrain exported span/query attributes | Exercise search, SSO callback and errors; inspect API, ingress and real collector output for sentinel values; retain request IDs and status/timing |
| P1-02 | Neutralize spreadsheet formulas in exports | Actual public first_name `=1+`, surname `1` accepted 202; authorized CSV contains cell `=1+ 1` unchanged. `reporting/service.py:653`; `csv-formula-probe.json` | Encode dangerous text-cell prefixes safely at export boundary; preserve numeric/date semantics; cover synchronous and worker exports | Real public input → both exports; parse output and open with approved spreadsheet viewer in controlled test; no formulas interpreted |
| P1-03 | Honor document upload limits on all staff routes | Valid 1,049,102-byte PDF passes validator with 10,485,760-byte limit but partnership upload returns 413; middleware line 31 only recognizes CV/public intake | Include bounded partnership/JD multipart routes and document aggregate limits consistently | Authorized valid 1 MiB MOU/JD uploads succeed to scanning; oversize/chunked/malformed inputs remain bounded and rejected |
| P1-04 | Validate encryption-key format and provision it consistently | Production Settings accepts `invalid-not-fernet`, cryptography rejects it; `config.py:128`; older `render.yaml` uses generic generateValue for identity key | Validate Fernet material at startup; provision valid key via secrets; document backup/rotation/recovery and ensure API/worker agree. Do not assume generated provider strings have Fernet format | Boot fails safely for malformed key; proper key round-trips sensitive intake, identity and MFA data; rotation/recovery exercise |
| P1-05 | Bound DB failures and prove worker supervision | Default DB readiness exceeds 15 s; with PGCONNECT_TIMEOUT=3 returns 503; worker exits 1; no provider restart tested | Explicit bounded connection/pool behavior, documented supervision/backoff, worker heartbeat and terminal/stale-job alerts | Kill worker / interrupt DB in staging, restore dependency, prove automated recovery and alert receipt without data loss |
| P1-06 | Make fresh setup and release paths reproducible | README misses parser requirements; staging Compose omits parser/worker/public fronts; production Render manifest follows older development branch; PR draft and unprotected branches | Correct bootstrap/runbook; choose one current full-stack release path; align manifests to reviewed revision and require release checks/review | Fresh machine without hidden venv state; whole gate; inspect deployed SHA/schema/all services; test migration/rollback in disposable infrastructure |
| P1-07 | Establish public frontend execution/header controls | HAMIS `frontend/index.html:11` runs external unpinned Tailwind JS; public builds do not establish hosted CSP/security headers | Compile/package styles locally or approve/pin a constrained dependency path; configure and validate static-host headers and third-party data exposure | Production public artifacts/headers reviewed; browser flows/CSP and offline/error behavior pass; no staff/database secrets reach browser |
| P1-08 | Verify actual scanner and full document workflow | Local engine unavailable; fail-closed verified; golden test substitutes clean scan | Provision maintained private clamd and signature updates; approve document/MOU acceptance rules | Clean PDF/DOCX, EICAR, invalid/archive-expansion, outage/timeout/rescan and authorized downloads tested against real engine/provider |
| P1-09 | Complete operational recovery and production acceptance | DB restore verified; files/keys/offsite retention/alerts/real provider restore not verified; RPO/RTO open | Approved RPO/RTO; coordinated DB + S3 + keys backup/restore, retention, alerting and incident runbooks | Timed separate-environment recovery of representative placements/audit/files; demonstrate scheduler, inaccessible backups and alert delivery |
| P1-10 | Close critical race/capacity and programme acceptance gaps | Concurrent export claims verified; actual simultaneous headcount/first-income/document mutations and representative-scale load not all exercised; policies remain open | Targeted concurrent HTTP tests and agreed-volume load measurements; approve programme notices, fields, income evidence and reporting definitions | No overfill/double count/version collision under actual concurrency; approved SLO/capacity evidence; signed business/UAT acceptance |

## 12. P2 Improvements

- Stream/page large export generation: worker currently calls `drilldown(limit=None)` and materializes rows and CSV in memory. No large-data failure was induced; this is a capacity risk to measure, not a claimed outage.
- Inspect N+1/aggregate query cost as data grows, worker report/parser fairness, export expiry/job retention, pool metrics and query budgets.
- Enforce consistent Git line endings for Windows fresh checkouts; the global autocrlf interaction is documented in audit setup, not counted as a Linux hosted-CI defect.
- Reconcile stale documentation referring to in-process exports, legacy login flows, provider defaults and deployment status. Keep legacy code excluded from active artifacts.
- Strengthen database-side protection for critical cross-table invariants if future import/admin paths are added; current API rule checks must remain authoritative.
- Expand manual accessibility, device and assistive-technology acceptance beyond the automated browser checks. Keep a maintained deprecation/ownership register for excluded legacy systems.

## 13. Staging-Only Validation

These are external validation gaps, not evidence of a code defect by themselves: Render workspace/service access, Docker builds and Linux standalone artifact layout; private service discovery and token distribution; hosted PostgreSQL 16 migration permissions/TLS/pooling; managed private S3 encryption, lifecycle, CORS and no anonymous access; network reachability and actual ClamAV updates; provider ingress HTTPS/security headers, domain cookies and rate-limit client IP behavior; organizational OIDC configuration/replay/MFA policy; OTLP backend/redaction/alerts; backup cron, retention, restore privileges and file/key recovery; supervised worker restarts; DNS and publicly trusted certificates; representative load and operational rollback; approved programme UAT and staff workflows.

Render is not set up. No deployment, successful cloud backup, successful cloud restore, live organizational SSO, or UAT is claimed. Container-image execution is NOT VERIFIED because Docker is unavailable; native success does not establish Linux image success.

## 14. Remaining Production Decisions

Programme owners must approve privacy notice/version, mandatory onboarding fields/sections, consent/publication wording, document/MOU requirements and waiver authority, first-monthly-income evidence, payroll cutoff/proration exceptions, follow-up cadence, Youth in Work/retention/PWD/female denominators, targets, locked reporting periods and override/field/export approval matrix. Existing code defaults and synthetic audit policy are not approvals.

Infrastructure owners must choose/provision Render staging ownership/domain, production hosting, private storage/scanning, SSO and staff MFA policy, observability/alert recipients, credential provisioning/rotation/key escrow, worker/job/export retention, offsite backup access/retention and **RPO/RTO (OPEN PRODUCTION DECISION)**. No messaging provider is needed merely to add participant authentication: participant sign-in remains explicitly prohibited by the agreed design. Email/SMS is only a future programme decision if separately required.

## 15. Exact Remaining Work

Each item is a separate reviewable fix or acceptance change, ordered by risk/dependency. No item has been implemented by this audit.

1. Fix backup subprocess credential handling and CLI/scheduler redaction; add real failed dump/restore regressions; rerun successful separate restore; commit P0-01.
2. Fix expired exhausted report claims with terminal audit/error and controlled retry; add real crash/lease test; commit report half of P0-02.
3. Apply equivalent exhausted-lease handling to retained legacy HAMIS events, or explicitly disable that optional adapter for release; test and commit.
4. Redact default API/ingress access logs and OTLP attributes; inspect actual emitted sentinel queries/codes; commit P1-01.
5. Neutralize CSV text formulas in shared export path; verify public intake → synchronous/worker output; commit P1-02.
6. Correct staff MOU/JD request-size classification and multipart bounds; test valid/oversize uploads; commit P1-03.
7. Validate Fernet key material and align secret provisioning/runbooks; test startup and round-trip API/worker consistency; commit P1-04.
8. Define bounded DB failures, worker heartbeat/supervision/retry alerts; test actual failure/restart; commit P1-05.
9. Correct README fresh-install prerequisites and one complete local/staging launch path; verify in a fresh checkout; commit documentation/manifests.
10. Align reviewed release branches and manifest references; make required checks/review effective; build actual Linux images in CI or disposable Docker host.
11. Establish public static security headers and remove/approve external Tailwind execution; rerun desktop/mobile/offline/retry browser flows.
12. Provision real scanner; execute clean/infected/outage/rescan/private download chain, parser suggestion review and employer document acceptance tests.
13. Run actual concurrent placement-capacity, confirmation and document-version requests; measure agreed data volumes and bounded export memory; fix only observed failures.
14. Approve programme notices, required fields, evidence and reporting definitions; record explicit owner acceptance and configuration.
15. Provision isolated Render staging and secrets/providers; deploy reviewed SHA, run migration and all three fronts, validate network/TLS/SSO/headers and worker restart/alerts.
16. Execute timed offsite DB + files + keys restore under agreed RPO/RTO; prove retention and failure alert receipt; complete operational runbooks.
17. Run complete golden workflow with real scanner/parser, negative authorization and failure paths; complete programme UAT and security/operations review, then decide production pilot go/no-go.

## 16. Estimated Readiness by Area

Qualitative engineering estimates only, not measured completion or probability of safety.

| Area | Estimate | Main deductions |
|---|---:|---|
| Application functionality | 85% | Broad workflows and tests work; document-size and export defects, programme acceptance outstanding |
| Integration completeness | 80% | Real local central records/parser/storage/worker; actual scanner and hosted deployment absent |
| Security readiness | 60% | Backup secret disclosure, log privacy, CSV formulas, invalid-key validation and public dependency/header controls |
| Reliability readiness | 60% | Final-lease failure, supervision unverified, incomplete race/load and file/key recovery evidence |
| Operational readiness | 40% | Local DB restore succeeds; no deployed monitoring, cron, provider recovery, approved RPO/RTO or incident acceptance |
| Staging readiness | 60% | Blueprint and green hosted gate exist; two P0 fixes, current release alignment, secrets and actual providers still required |

## 17. Go / No-Go

| Use | Decision | Minimum conditions / limits |
|---|---|---|
| Continued local development | **YES** | Preserve authoritative business rules and no-sign-in public intake; synthetic isolated data |
| Integrated local pilot | **YES, synthetic only** | Exercise documented limitations; use private local storage; scanner-dependent flow remains partial. This does not authorize real participant pilot data |
| Staging deployment | **NO** | Fix both P0s and rerun crash/secret/restore regressions; align deployable revision; provision isolated secrets/storage/scanner/ingress and restart controls. Synthetic staging can then validate remaining external requirements |
| UAT | **NO** | Deploy stable isolated staging, complete real scan/parser golden chain, privacy/log/export fixes and approved programme configuration; validate staff permissions and representative workflows |
| Production pilot | **NO** | Close applicable P1s; pass UAT/security/operations acceptance, hosted backup/file/key restore and alerts under approved RPO/RTO, supervised recovery and agreed load/race tests; explicitly approve release |

The shortest sound path is the ordered backlog above. No production code fixes, repository protection changes, merges, deployments or messages to other people were performed during this audit.

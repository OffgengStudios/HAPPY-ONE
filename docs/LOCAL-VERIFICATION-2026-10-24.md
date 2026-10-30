# Local optimized build verification - 24 October 2026

Target confirmed by the user: optimized application at localhost; hosting deferred.
The working tree is based on `9da0e8e` plus local changes. Release version remains
`1.0.0-rc.1`.

## Results

| Check | Result |
| --- | --- |
| Full backend unit and live integration suite | 352 passed, no skips; one upstream Starlette test-client deprecation warning |
| Additional local process/private-path safeguards | 8 passed |
| Configuration and production preflight focused checks | 27 passed; 26 included in the full backend count, plus a malformed-database configuration regression |
| Real parser/service contracts | 22 passed |
| Public frontend contract/assets | 5 passed; both static builds passed |
| Live participant/employer journeys | Desktop/mobile passed, including local drafts and genuine PDF upload; synthetic fixtures cleaned |
| Optimized local smoke | Desktop/mobile sign-in, authenticated shell, CSRF rejection, logout, public forms/assets, responsive width and blocked private paths passed |
| Local process lifecycle | Start, status, stop and restart passed; rebuilding a running instance is refused |
| Python formatting/lint/strict types | Passed; new launcher/guard files also checked separately |
| JavaScript formatting/lint/workspace types | Passed after excluding generated local build output |
| Environment tests | 4 passed |
| Production builds | Default verification build and separate `.next-local-production` build passed |
| Full staff browser suite and dependency audits | In progress; final result to be recorded before task completion |
| Blueprint validation | Existing platform, staging and future production candidates pass Render's published JSON schema, local build-path checks and cross-service reference checks |
| Local data backup/restore | Verified SHA-256 manifest; restored `0036_vacancy_terms` in 13.36 seconds; temporary restore database cleanup verified |

The full backend pass came from `pnpm verify`. That command subsequently stopped
because Prettier included newly generated `.next-local-production` files. The
generated directory is now ignored by formatting, lint, Git and Docker context
rules, with a separate local TypeScript configuration/cache. A continuation ran
the remaining quality-gate stages against the same disposable database/bucket.
This record distinguishes that continuation from an uninterrupted combined run.

The isolated restore archive has SHA-256
`6c24edba6ff1abff5f3299ef15783fa485ca89288aed4fbe7ed171ac2e4dd57b`.
Its source was the disposable verification database, not operational data.
Verification evidence is retained locally under the workspace's ignored
`.local/launch-20261024/`; credentials are excluded from the published report.

## Local runtime

See [startup and lifecycle commands](LOCAL-PRODUCTION.md). The optimized staff app
is served at `http://localhost:3300`; participant and employer forms are served at
`http://localhost:8865/hamis/` and `http://localhost:8865/employer/`. The API binds to
`127.0.0.1:8100` and shares the selected local database/private storage with its
durable worker. Public static serving is limited to the two build outputs.

The selected environment is `.local/runtime/working.env`. It contains labelled
development notices, onboarding approval disabled, and no scanner/parser endpoint.
The user reports approved configuration is available, but its path has not yet
been identified. This checkpoint verifies an optimized local build; programme
approval and document/parser gates remain enforced.

No hosted deployment, hosted-CI result for these local changes, Linux container
execution, human programme acceptance or live provider certification is claimed.

# Phase 1: Authentication and IAM

Historical evidence: this completed IAM baseline is now Phase 2 in the
[revised roadmap](20-IMPLEMENTATION-ROADMAP.md). Original test evidence remains
unchanged; see [integration readiness](27-INTEGRATION-READINESS.md) for the extension.
The revised Phase 2 review, pending-MFA revocation correction, and current
acceptance evidence are in [28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md](28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md).

Completed for the local password-authentication baseline on 06 Oct 2026.
No production authentication provider, SSO, or field-level programme policy was selected.

## Implemented

- Users, seven seeded system roles, permissions, role assignments, and ALLOW/DENY overrides.
- UUID identifiers, normalized email uniqueness, explicit input schemas, and versioned updates.
- Argon2id password hashing; account creation requires 12-128 characters.
- PostgreSQL-backed account/IP login throttles with configurable limits/windows.
- Opaque session tokens stored only as SHA-256 digests; token rotation on login.
- HttpOnly, SameSite=Lax sessions with Secure cookies in staging/production.
- Absolute and idle expiry; per-device logout/revocation; inactive accounts denied.
- Session-bound CSRF tokens and exact allowed Origin checks on state-changing requests.
- Server-side permission dependencies; grants are reevaluated from the database.
- Role-aware account projection and a restricted-field projection helper.
- Account, role, permission-catalog, and read-only audit endpoints with cursor pagination.
- Last-administrator protection, self-deactivation protection, and immutable ADMIN grants.
- Mandatory IAM audit events with actor, entity, result, timestamp, and request ID.
- PostgreSQL triggers reject UPDATE/DELETE of audit events; no mutation API is exposed.
- Sign-in, account/role editors, permission overrides, session revocation, and audit screens.
- Same-origin Next.js API forwarding; account responses are not cached.

## MFA Boundary

`MfaVerifier` is an injectable provider interface. A successful password check for
an MFA-enabled account issues only a short-lived, attempt-limited challenge.
Session issuance waits for factor verification; challenges cannot be reused, and
MFA-enabled users cannot use password-only sessions.

The default verifier is unavailable and denies access for MFA-enabled accounts.
Provider-backed enrollment, encrypted factor storage, recovery, and replay
protection inside the factor provider still require an implementation/selection.
Do not enable MFA flags directly as an operational workflow. A future enrollment
service must emit `auth.mfa_changed` and revoke affected sessions.
Account-wide revocation also consumes pending MFA challenges. Password resets
and deactivation/reactivation cannot reuse a pre-change challenge; account and
challenge locks follow the same order during verification and revocation.

## Permissions Boundary

The initial grants cover unambiguous baseline resource access. Restricted,
aggregated, workflow-specific, and sensitive-field access remains denied unless
explicitly granted. Resource view permission does not authorize sensitive fields
or exports. Future domain modules must use record scopes and field projections.

The workspace selector is a local engineering baseline, not the approved
multi-role production workspace UX. Sensitive export approvers and the exact
staff field matrix remain open in `21-OPEN-DECISIONS.md`.

The immutable seed snapshot is `database/seeds/iam_v1.json`. Do not change it to
introduce future grants; use a new versioned migration.

## Initial Account

First-account provisioning is an explicit CLI operation, not public registration:

```bash
pnpm api:migrate
pnpm iam:bootstrap --email administrator@example.org
```

The command prompts without echoing the password. It refuses to run after any
accounts exist. Local loopback development may use `--local` to generate ignored
`.local/iam/admin-credentials.json`. `--password-file` reads a supplied local
password without putting it in command-line arguments.

No email is sent. No password or token is included in API projections, audit
payloads, validation errors, or application logs. Never reuse local credentials
in staging/production.

## Configuration

`AUTH_SESSION_HOURS=8`, `AUTH_IDLE_MINUTES=30`, `AUTH_LOGIN_LIMIT=5`,
`AUTH_IP_LIMIT=30`, and `AUTH_WINDOW_MINUTES=15` are configurable engineering
defaults, not programme policies.

Web requests use `/api/v1`; `API_INTERNAL_URL` is server-only. Local development
defaults to `http://127.0.0.1:8000`; staging uses `http://api:8000`.
`API_CORS_ORIGINS` must contain the exact browser origin, including scheme/port.
Login also requires an Origin header for non-browser API clients.

Use TLS for staging/production. A reverse proxy must preserve Origin and cookies,
must not cache authenticated API responses, and must have an explicit trusted
proxy policy. Login throttling uses the ASGI client address, not an arbitrary
forwarded header.

## Verification

`pnpm verify` passed:

- 53 backend tests, including live PostgreSQL/storage and IAM tests.
- Strict backend type checks across 32 source files.
- 4 shared configuration tests.
- 10 real desktop/mobile browser tests using Microsoft Edge locally.
- Formatting, lint, workspace types, and optimized production build.
- Python dependency consistency and both dependency vulnerability audits.

Tests cover all seven seeded role projections, server-side admin denial,
restricted field omission, explicit DENY precedence, login/password-spraying
throttles, CSRF/origin checks, cookie rotation, expiry, revocation, deactivation,
cross-user session targeting, MFA gating/challenge consumption, stale updates,
override changes, protected admin grants, and append-only audit enforcement.

Browser tests cover invalid login, sign-out, session visibility, Marketing
restrictions, account creation/deactivation, custom role editing, and audit access
on desktop and mobile. Screenshots were inspected.

`alembic check` reports no new upgrade operations at `0002_iam`. Staging Compose
still validates. IAM API tests use an isolated test schema with rolled-back
transactions. Browser tests start a separate API with synthetic accounts and
remove the API/schema on exit; they do not modify local administrator accounts.

The configured local administrator also passed a live smoke test through the
development web proxy: login, account access, CSRF-protected logout, and rejection
of the revoked session. No temporary test schemas remain.

The CI build points to its ephemeral browser API. Rebuild with the intended
`API_INTERNAL_URL` before using production output outside CI. Development
servers must be stopped before CI because they share the build directory.

Hosted Linux CI, Docker images, and staging deployment remain unexecuted on this
workstation. Production SSO/MFA integration, credential recovery, approved
retention/cleanup schedules, and deployment hardening are not claimed complete.

## References

Password authentication and session controls follow the applicable guidance in
the [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
and [CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
references. MFA providers must implement factor-level replay rejection, consistent
with the [PyOTP provider guidance](https://pyauth.github.io/pyotp/).

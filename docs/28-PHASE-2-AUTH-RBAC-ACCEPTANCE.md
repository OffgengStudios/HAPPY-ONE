# Phase 2: Authentication + RBAC Acceptance

Reviewed on 07 Oct 2026 under the revised phase numbering.
Status: **Complete for the local Authentication + RBAC / MFA-ready scope.**
Production MFA/SSO and deployment are not claimed complete.

Preserve the existing foundation, IAM, Demand baseline, Supply draft, and
integration-readiness extension. No restart, seed rewrite, new migration,
external synchronization, or data import is part of this review.

## Acceptance Scope

| Requirement | Existing implementation |
|---|---|
| Individual user accounts | UUID users, normalized unique email, explicit bootstrap and admin account management |
| Authentication | Argon2id, generic errors, account/IP throttles, secret-safe projections |
| Roles and assignments | Seven seeded system roles, custom roles, primary-role UX and protected last-admin rules |
| Permissions and overrides | Resource/action grants, ALLOW/DENY overrides with DENY precedence, fresh database evaluation |
| Session management | Opaque hashed sessions, cookie rotation, absolute/idle expiry, revocation, account-change invalidation |
| MFA-ready architecture | Injectable verifier, short-lived limited-use challenge, fail-closed unconfigured provider |
| Server authorization | Authenticated permission dependencies, protected domain services; navigation is not a security boundary |
| Frontend access | Sign-in, role-aware workspaces, account/role editors, overrides, sessions and audit screens |
| Audit foundation | Append-only database enforcement, safe user/system/integration attribution |
| Integration readiness | Generic references, controlled provenance and small adapter boundaries; no external clients |

Role determines the default experience; permission determines actual access.
The [original IAM evidence](25-PHASE-1-AUTH-IAM.md) and
[integration-readiness contract](27-INTEGRATION-READINESS.md) remain applicable.

## Security Gap Resolved

The review reproduced a pending-MFA invalidation gap: an administrator's password
reset or deactivation/reactivation revoked existing sessions but did not consume
the account's pending password-validated MFA challenges. A configured verifier
could subsequently issue a session using the old challenge.

The existing revoke_all service now also consumes pending challenges for that
account. Verification and account changes consistently lock the user before
challenge records; verification refreshes the challenge under lock before
checking its consumed/expired/attempt-limit state.
Other accounts' challenges are unaffected. A new login can obtain a fresh
challenge after the account change. The same existing error contract returns
401 MFA_CHALLENGE_EXPIRED for invalidated challenges.

Changed implementation:
- apps/api/app/modules/iam/service.py: account-wide revocation includes challenges.
- apps/api/app/modules/iam/routes.py: consistent MFA user/challenge lock order.
- apps/api/tests/test_iam_integration.py: three new regression cases.

No API request/response schema, cookie policy, permission grants, MFA provider,
human account credentials, or database migration changed.
This is a targeted authentication correction, not production MFA enrollment.

## Risk and Rollout

The behavioral change is limited to pending challenges for an account whose
credentials/access are invalidated. Ordinary login, permission evaluation, and
unrelated accounts keep their existing behavior.
MFA verification now serializes with account changes and other verifications
for the same user. A future verifier must have bounded execution time so it
does not hold the account lock indefinitely.
Restart API workers to load the change; no migration or credential reset is
required. Do not enable MFA flags without the separately selected provider.

## Regression Evidence

The two account-change tests failed before the fix (old challenge returned 200)
and passed after it. They cover password reset, deactivation/reactivation,
unaffected users, denied session issuance, and fresh login.
A third test uses two real PostgreSQL transactions to exercise verification
waiting on a concurrent account change and confirms it fails closed without
reversing lock order. Tests use synthetic identities and disposable schemas.

Full local CI (`pnpm verify`) passed:
- 136 backend tests, including 37 IAM and 48 integration-readiness checks.
- Four environment tests and 14 desktop/mobile browser tests.
- Formatting, lint, strict Python/workspace types and production build.
- Migration application and clean model/schema comparison at unchanged 0009.
- Dependency consistency and both Python/JavaScript vulnerability audits.

Desktop/mobile account-security screenshots were visually reviewed. Existing
login, sign-out, session visibility, ordinary-user denial, account/role edits,
overrides and append-only audit behavior remain covered.
The original working administrator is preserved; no real account has MFA enabled
and no external references/data were imported. CI used disposable schemas and
removed its synthetic browser API/schema. The upstream HTTPX TestClient
deprecation warning is non-blocking.

After API/web restart, readiness and web home returned 200; the original
administrator signed in with unchanged local credentials (200), retained
administration permissions, signed out (204), and subsequent protected access
returned 401. No temporary test schemas remain. The app is available at
http://localhost:3000; credentials remain in ignored local storage.

## Deferred Boundaries

Production MFA enrollment/provider, factor storage, recovery and factor-level
replay rejection require a selected implementation. MFA-ready acceptance does
not mean MFA is operational. Existing real accounts are not switched to MFA.
Production SSO, hosted deployment, approved field-level staff policy and
credential-retention schedules remain open decisions.
Machine credentials and participant/employer login are future flows, not fake
staff identities. CV Parser is Phase 7, HAMIS Phase 12, Employer Portal Phase 13.

Next roadmap phase is Phase 3 Demand. Review its existing verified baseline and
outstanding boundaries rather than rebuilding its completed workflows.

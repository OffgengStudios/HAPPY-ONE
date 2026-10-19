# Phase 2: Integration Readiness

Decision: 07 Oct 2026. **HAPPY first, integrations second.**
Continue the existing IAM implementation. CV Parser belongs to Phase 7, HAMIS
to Phase 12, and Employer Acquisition Portal to Phase 13.
The [roadmap](20-IMPLEMENTATION-ROADMAP.md) supersedes historical phase numbers;
previous evidence and migration revisions keep their names.

## Repository Audit

Classification is based on inspected implementation, not the target schema alone.

| Area | Classification | Existing implementation / boundary |
|---|---|---|
| Foundation/PostgreSQL/migrations/environment | Complete locally | FastAPI/Next.js, Alembic, private S3, health, local CI; hosted deployment unverified |
| Individual users/authentication | Complete locally | Argon2 passwords, login throttles, explicit first-admin bootstrap |
| Roles/permissions/assignments/overrides | Complete locally | Seven system roles, custom roles, resource/action grants, DENY precedence |
| Sessions | Complete locally | Opaque hashed sessions, expiry/revocation, exact Origin and CSRF |
| MFA readiness | Partially Complete | Injectable factor boundary and challenges; production provider/enrollment/recovery not configured |
| Server authorization | Complete for current endpoints | Fresh database grants, API checks and domain-service rules; frontend not a security boundary |
| Frontend route/access handling | Complete for current workflows | Signed-in workspace and permission-aware navigation/actions; denied API access independently tested |
| Audit | Complete locally; representation extended | Append-only PostgreSQL triggers and safe IAM/domain events |
| Repository/service pattern | Complete for current modules | Thin routes, SQLAlchemy persistence in domain services; no duplicate repository abstraction |
| API versioning | Complete | Shared /api/v1 domain APIs and OpenAPI |
| Demand | Complete local baseline | Preserve historical Demand verification and workflows |
| Supply | Partially Complete | Existing backend draft preserved; frontend, focused acceptance and programme-policy approval outstanding |
| Generic external references | Not Started before this change; implemented here | Entity-bound mapping, no synchronization |
| Controlled record provenance | Not Started before this change; implemented here | Shared Record mixin and database constraints |
| Machine/service authentication | Not Started | No fake staff accounts; future credential/audience/scope lifecycle remains separate |
| Audit actors | Partially Complete before this change; extended here | Human UUID strings plus controlled non-user attribution |
| Integration boundaries | Not Started before this change; established here | Small packages only, no clients/jobs |
| Participant HAMIS column | Conflicts With Specification; resolved here | Forward migration preserves local values in generic references, removes core column |

## External References

`external_references`: UUID `id`, `entity_type`, internal UUID `entity_id`,
`external_system`, `external_id`, JSON `external_metadata`, timestamps, and
optimistic-concurrency `version`. Existing conventions are retained.

Unique key: `(external_system, entity_type, external_id)`. One external key
cannot bind to two HAPPY entities. Different systems may reference the same
internal record. Internal UUIDs and human-facing HAPPY codes never change.
Bindings are immutable through the API; PATCH changes metadata only.
Systems use uppercase controlled codes; external IDs are trimmed, case-sensitive.
Supported entity registry: PARTICIPANT, ORGANIZATION, VACANCY.

Polymorphic references have no cross-table foreign key. The service validates
the target and locks it on writes; archived targets reject changes.
Normal domain workflows archive rather than hard-delete. Any future privileged
hard-delete workflow must reconcile references transactionally.

Current endpoints:
- GET /api/v1/external-references?entity_type=...&entity_id=... (cursor pagination)
- GET /api/v1/external-references/{id}
- POST /api/v1/external-references
- PATCH /api/v1/external-references/{id} (expected version)

No global lookup, remapping, deletion, synchronization, or external-data import.
Responses are no-store. Metadata is limited to 4 KiB and five nesting levels.
Do not store credentials, signatures, raw CV text, or sensitive identity data.

## Authorization

New permissions: `external_reference:view` and `external_reference:manage`.
Only ADMIN receives default grants; custom grants still respect explicit DENYs.
Reads also require the referenced resource's :view permission. Writes require
both reference permissions and resource :view/:edit. The business service repeats
these checks independently of route guards and role names.
Metadata never sets permissions, identity, record provenance, or business values.

The new service accepts an AuthorizationContext protocol (permissions and audit
actor); today's authenticated Principal satisfies it. This is not an external
authentication flow. Future clients must obtain a separately authenticated,
server-issued context with approved scopes and record-level rules.

## Provenance

All 13 existing mutable domain Record tables inherit controlled provenance:
- source_system: INTERNAL, HAMIS, EMPLOYER_PORTAL, API
- created_via: STAFF, PARTICIPANT, EMPLOYER, INTEGRATION, SYSTEM

ORM and database defaults are INTERNAL / STAFF. The forward migration applies
those defaults to already-local staff records. Database checks reject arbitrary
strings. Staff write schemas do not accept provenance; future adapters must set
it only from trusted server-side context.
Participant source_type/source_detail describe recruitment attribution, not
system origin. IAM tables and append-only events retain their existing attribution
rather than acquiring a second provenance mechanism.

## Audit Actors and Future Identities

Actor types: USER, PARTICIPANT, EMPLOYER, SYSTEM, INTEGRATION.
Human actor IDs remain canonical UUID strings. SYSTEM permits an unattributed
null ID or a controlled code. INTEGRATION requires a controlled code such as
HAMIS or EMPLOYER_PORTAL. Database constraints enforce the representation.

AuditActor is attribution, not credentials or a permission grant. No endpoint
accepts actor identity from untrusted headers/metadata. Existing UUID and null
audit helper calls remain compatible, and existing UUIDs serialize unchanged.
Append-only audit protection is preserved. Reference events record safe reference
IDs and changed-field names, not raw metadata/external identifiers.

Human users remain distinct from future service identities. This phase does not
implement machine credentials, service-account management, client audiences,
token issuance, or participant/employer login. Those flows must reuse HAPPY
permissions and services without impersonating staff. Existing domain ownership
and human created_by fields must remain separate from integration attribution.

## Integration Boundaries

Integration packages:
- apps/api/app/integrations/cv_parser/
- apps/api/app/integrations/hamis/
- apps/api/app/integrations/employer_portal/

Phase 7 provides the HAPPY-side CV parser job/review boundary; Phase 12 provides
the local HAMIS machine-event adapter; Phase 13 provides the local Employer Portal
submission adapter. No production URL or credential is stored here, and no
browser client holds a machine secret. Both system-of-record adapters map through
existing participants, organizations, contacts, partnerships and vacancies,
not duplicate domain databases.

Phase 7 flow: private document ID/version -> parser job -> adapter -> separate
result/extracted values/confidence -> human review -> approved domain update and
audit. Failure states must not block core workflows. Parser results never
automatically overwrite participant data. No parser repository was copied.

## User-Supplied Reference Systems

These are reference material for later inspection, not current runtime backends:
- [HAMIS repository](https://github.com/Murphy-Richard/happy-kollekt)
- [HAMIS application](https://murphy-richard.github.io/happy-kollekt/)
- [HAMIS backend sheet](https://docs.google.com/spreadsheets/d/15wqqAiJIbw6lfzwZFG_fGiklG-jFMCCpQhkaWVtPSzA/edit?gid=1754979767)
- [Consent backend sheet](https://docs.google.com/spreadsheets/d/1D_LyM6SQFp2GjU88ytXe1yPkePuPxM4OeI0lgpzs8O4/edit?gid=0)
- [Employer Acquisition Portal](https://offgengstudios.github.io/Happy/portal)

07 Oct inspection was read-only: sheet metadata and header rows, public application
HTML labels, and repository overview. No participant rows, signatures, production
imports, backend submissions, or synchronization calls.
The HAMIS header covers the previously supplied intake fields, with local queue
and write-event IDs. The consent header includes consent ID, timestamp, venue,
participant name, phone/email, acceptance, language, programme, and signature.
Neither header establishes approved notice wording/version or mandatory-field
policy. Do not infer programme rules from spreadsheets or legacy code.
The repository README describes a field-collection frontend and Apps Script
backend; a later review must inspect actual code/deployments before any contract
decision. No clone or contract implementation is part of this phase.

## Migration and Risk

Forward revision `0009_integration_readiness` follows applied revision 0008.
It preserves already-local participant HAMIS IDs as external references before
removing the core column; this is schema migration, not importing HAMIS data.
It adds provenance, widens audit actor IDs from UUID to string, and grants the
two reference permissions to ADMIN. Revisions 0001-0008 and their seeds are not
renumbered or semantically rewritten.

Password/session/CSRF behavior and existing role grants remain unchanged.
The shared Record mixin and audit type conversion affect multiple modules:
verify migrations, IAM, Demand, and browser regressions before acceptance.
Production rollout needs a backup and coordinated migration/writer deployment;
the actor-column conversion takes a table lock.
Local CI also identified vulnerabilities in the preserved draft's cryptography
46.x dependency. The requirement is now >=50.0.2,<51; the installed release is
50.0.2. This is a dependency correction, not a change to password hashing or
programme policy. A focused authenticated-encryption recipe test accompanies it.
See the [upstream release notes](https://cryptography.io/en/latest/changelog/)
and [upstream wheel advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-537c-gmf6-5ccf).
Downgrade refuses non-UUID actors or references that cannot fit the legacy
participant column. It is not a general data-loss-free rollback for provenance.
Do not downgrade the working database merely to demonstrate legacy behavior.

## Verification

This is the extension's original acceptance evidence. A subsequent Phase 2
review fixed pending MFA challenge invalidation and passed the full 136-test
backend suite; see [Phase 2 acceptance](28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md).

**Local CI passed on 07 Oct 2026** via `pnpm verify`:
- 133 backend tests passed, including 48 focused readiness/dependency checks.
- Four environment tests and 14 desktop/mobile browser tests passed.
- Python/JavaScript formatting, lint, types, migration, and production build passed.
- Dependency consistency and Python/JavaScript production audits passed.
- `alembic check` reports no model/schema drift.
- Desktop/mobile audit screenshots were visually reviewed without overlap.
- Local API/private-storage readiness returned 200; web home and original-admin
  login returned 200, expected reference grants were present, and logout returned
  204 through the same-origin web proxy. No password was exposed by the check.

Focused tests cover reference uniqueness,
independent UUIDs, multi-system mappings, permission DENYs and metadata isolation,
controlled/default provenance, compatible actor attribution, append-only events,
and forward preservation of synthetic legacy data in disposable test schemas.
Browser checks exercise integration-actor rendering on desktop and mobile.
Later phase reports supersede this original checkpoint: HAMIS and Employer Portal
adapter tests now exist without production synchronization. See
[Phase 12](42-PHASE-12-HAMIS-INTEGRATION.md) and
[Phase 13](43-PHASE-13-EMPLOYER-PORTAL-INTEGRATION.md).

The working database remains at 0009 with one active original administrator and
seven system roles. Existing 15 audit events retained their USER/SYSTEM attribution;
no synthetic test accounts/references or imported participant records were added
to the working schema. Migration preservation/rollback-refusal tests run only
inside disposable schemas; CI removed its browser API and synthetic schema.
The final original-admin smoke check adds ordinary login/logout audit events;
it does not create synthetic users or integration actors in the working database.
Development services are available at http://localhost:3000 (web) and
http://127.0.0.1:8000/api/v1/health/ready (API). Use the root README's startup
commands after reboot; CI's temporary browser server is not the development app.

Non-blocking warning: the current Starlette TestClient warns that httpx support
is deprecated. Tests pass; a future test-tooling upgrade can address this.
Local verification does not establish hosted deployment, production MFA,
Supply acceptance, programme-policy approval, or any external integration.

# Implementation Defaults

These are implementation defaults for Codex so the project is buildable without repeated architectural guessing.

They may be changed by an explicit architecture decision before implementation.

## 1. Monorepo

Use a monorepo.

## 2. Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- accessible component primitives
- TanStack Query for server-state management
- React Hook Form + schema validation for complex forms
- generated API client from backend OpenAPI when practical

Do not duplicate backend business rules in the frontend beyond user-friendly pre-validation.

## 3. Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic migrations
- PostgreSQL

Backend is the authoritative business-rule layer.

## 4. Identifiers

Internal relational primary keys:
- UUID

Human-facing codes:
- immutable strings, unique, separately generated

Examples:
- `HAPPY-2026-001284`
- `VAC-2026-000123`
- `ORG-2026-000045`
- `PLC-2026-000091`

Do not use human-facing codes as relational primary keys.

## 5. Time

- store timestamps as timezone-aware UTC
- render user-facing times in Ghana local time
- user-facing date format: `06 Oct 2026`
- user-facing time format: `10:30 AM`

## 6. Object Storage

Use an S3-compatible private object-storage abstraction.

Local development may use MinIO or equivalent.

Never expose bucket objects publicly by default.

## 7. Authentication

Implement an authentication abstraction supporting:
- individual accounts
- password login initially if SSO is not configured
- MFA support
- secure HttpOnly session/refresh mechanism
- session/device revocation

Do not tie domain authorization to frontend route checks.

## 8. Background Processing

Introduce a worker/queue only when required by:
- CV parsing
- report generation
- malware/file scanning
- notification scheduling
- AI processing

Keep the worker behind an interface so the concrete queue can change.

## 9. Testing

Backend:
- pytest

Frontend:
- unit/component test framework appropriate to the chosen Next.js setup

End-to-end:
- Playwright

## 10. Local Development

Use Docker Compose for infrastructure dependencies:
- PostgreSQL
- object-storage emulator if used
- optional queue/cache when introduced

Application code may run inside or outside containers during development.

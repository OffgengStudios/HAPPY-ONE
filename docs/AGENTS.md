# AGENTS.md — Codex Rules for HAPPY Management Platform

## Read First
1. `00-CODEX-START-HERE.md`
2. `07-BUSINESS-RULES.md`
3. the module-specific spec for the task

## Never Violate
- no WhatsApp integration
- no Google Sheets backend
- no automatic historical migration
- no employer submission before onboarding complete
- no confirmed placement before verified first monthly income
- no auto-reject/select/merge/confirm by AI
- no frontend-only authorization
- no sensitive PII in logs
- no hard delete as normal workflow

## Architecture
- Next.js + TypeScript frontend
- FastAPI + Python backend
- PostgreSQL
- Alembic
- private S3-compatible object storage
- modular monolith

## Workflow
For each feature:
- migration/schema
- service/business rule
- permission
- API
- audit
- UI
- tests

## Testing
Do not mark a task complete without tests for the business rule being implemented.

## Open Decisions
Check `21-OPEN-DECISIONS.md`.
Do not guess programme policy.

## UX
Shared records, role-specific projections:
- Demand
- Supply
- Matching
- M&E/MERL
- Marketing
- Management

## Critical Rule
`Confirmed Placement = Actual Start + Verified First Monthly Income`

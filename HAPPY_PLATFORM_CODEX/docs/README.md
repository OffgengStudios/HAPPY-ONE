# HAPPY Management Platform — Developer Implementation Specification

**Audience:** Codex, software engineers, QA, product owner, technical reviewers  
**Status:** Build baseline  
**Format:** Markdown source-of-truth package

This package translates the approved HAPPY product design into an implementation-grade specification.

## Precedence

When documents conflict, use this order:

1. `00-CODEX-START-HERE.md`
2. `01-PRODUCT-CONTRACT.md`
3. `07-BUSINESS-RULES.md`
4. `06-STATE-MACHINES.md`
5. `05-DATABASE-SCHEMA.md`
6. `08-RBAC-PERMISSIONS.md`
7. `09-API-CONTRACT.md`
8. `10-UI-SCREEN-SPEC.md`
9. remaining files
10. legacy/reference systems

**Do not infer new programme rules from legacy spreadsheets or old code.**

The 07 Oct 2026 architectural sequencing decision is authoritative:
[revised roadmap](20-IMPLEMENTATION-ROADMAP.md), with Phase 2 integration readiness
in [27-INTEGRATION-READINESS.md](27-INTEGRATION-READINESS.md).
HAPPY first; CV Parser Phase 7, HAMIS Phase 12, Employer Portal Phase 13.
Historical acceptance filenames and migration revisions retain their numbering.
All thirteen phases have local implementation acceptance for their documented
scope. Phase 13 evidence is in
[43-PHASE-13-EMPLOYER-PORTAL-INTEGRATION.md](43-PHASE-13-EMPLOYER-PORTAL-INTEGRATION.md).
The current Authentication + RBAC review is recorded in
[28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md](28-PHASE-2-AUTH-RBAC-ACCEPTANCE.md).
The revised Demand checkpoint is locally accepted in
[29-PHASE-3-DEMAND-ACCEPTANCE.md](29-PHASE-3-DEMAND-ACCEPTANCE.md).
Phase 4 Supply passed functional local checks; visual acceptance remains open
following the user's theme feedback. Its policy and rollout gates are
recorded in [30-PHASE-4-SUPPLY.md](30-PHASE-4-SUPPLY.md).
The compact mobile shell/More sheet and desktop sidebar checkpoint are recorded
in [10-UI-SCREEN-SPEC.md](10-UI-SCREEN-SPEC.md). The user confirmed Jobberman-inspired
blue recruitment styling with fluid motion; implementation review and official
logo/font choices remain open in
[21-OPEN-DECISIONS.md](21-OPEN-DECISIONS.md).
The account-menu/grouped-search extension is recorded in that screen specification
and [09-API-CONTRACT.md](09-API-CONTRACT.md). Full local verification passed on
08 Oct 2026: 220 backend, four environment and 68 desktop/mobile browser tests,
including the prototype-aligned theme, motion, action surfaces and intake-owner
permission follow-up.
The supplied participant headers are mapped in
[31-SUPPLY-FIELD-INVENTORY.md](31-SUPPLY-FIELD-INVENTORY.md).
The supplied role-based prototype is documented in
[32-VISUAL-REFERENCE.md](32-VISUAL-REFERENCE.md), including exact palette, shell
mapping, motion/accessibility and boundaries that keep demo data out of HAPPY.

## Non-negotiable decisions

- HAPPY is a programme management platform, not only an ATS.
- Workstreams: Demand, Supply, Matching, and Enablers.
- Enablers include M&E/MERL, Marketing, and Management/PM.
- One central PostgreSQL system of record.
- Files use private object storage.
- Shared records; role-specific views.
- Role shapes default UX; permissions control actual access.
- v1 is greenfield production data.
- No WhatsApp integration in v1.
- Formal candidate submission requires completed HAPPY onboarding.
- Confirmed placement requires actual work start **and** verified first monthly income.
- A later employment exit does not erase historical confirmed placement.
- AI is assistive, never authoritative.

## Package Map

- `00-CODEX-START-HERE.md` — coding instructions and hard constraints
- `01-PRODUCT-CONTRACT.md` — business/product contract
- `02-IMPLEMENTATION-DEFAULTS.md` — default stack and engineering conventions
- `03-REPOSITORY-STRUCTURE.md` — monorepo layout
- `04-DOMAIN-MODEL.md` — aggregates and relationships
- `05-DATABASE-SCHEMA.md` — implementation-level relational schema
- `06-STATE-MACHINES.md` — exact workflow states/transitions
- `07-BUSINESS-RULES.md` — numbered business rules
- `08-RBAC-PERMISSIONS.md` — roles, permissions, field restrictions
- `09-API-CONTRACT.md` — endpoint and API conventions
- `10-UI-SCREEN-SPEC.md` — desktop/mobile screen contract
- `11-VALIDATION-ERROR-CATALOG.md` — validation and errors
- `12-AUDIT-EVENT-CATALOG.md` — required audit events
- `13-REPORTING-KPI-DICTIONARY.md` — KPI formulas and drill-downs
- `14-MARKETING-MERL-TRAINING.md` — specialist Enabler modules
- `15-SECURITY-PRIVACY.md` — security implementation requirements
- `16-FILES-CV-AI.md` — documents, CV parser, AI boundaries
- `17-TESTING-ACCEPTANCE.md` — automated tests and acceptance criteria
- `18-DEVOPS-OBSERVABILITY.md` — environments, CI/CD, backup, logging
- `19-SEED-REFERENCE-DATA.md` — initial enums/reference data
- `20-IMPLEMENTATION-ROADMAP.md` — Codex build sequence
- `21-OPEN-DECISIONS.md` — unresolved items Codex must not invent
- `22-TRACEABILITY-MATRIX.md` — requirement-to-module mapping
- `AGENTS.md` — condensed Codex operating instructions

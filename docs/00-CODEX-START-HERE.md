# Codex — Start Here

## 1. Mission

Implement the HAPPY Management Platform according to this specification.

Do not redesign the business process while coding.  
Do not replace documented rules with assumptions from a generic ATS/CRM.

## 2. Hard Constraints

### C-001 — Greenfield v1
Do not write historical migration pipelines unless explicitly requested later.

Legacy files and systems are **reference material only**.

### C-002 — No WhatsApp
Do not add:
- Meta Cloud API
- WhatsApp chatbot
- WhatsApp group automation
- WhatsApp candidate application flow
- WhatsApp notifications

### C-003 — One system of record
Use PostgreSQL as the relational source of truth.

Do not use Google Sheets as an application backend.

### C-004 — Shared records
Demand, Supply, Matching, M&E, Marketing and Management must work over shared domain records.

Do not create separate participant or vacancy tables per workstream.

### C-005 — Onboarding gate
A candidate cannot be formally submitted to an employer until required HAPPY onboarding is complete.

### C-006 — Placement rule
A confirmed placement requires both:
1. `actual_start_date` present; and
2. first monthly income verified.

`selected != placed`  
`started != placed`

### C-007 — Historical placement
After a placement becomes confirmed, a later exit changes retention/current employment, not the historical placement achievement.

### C-008 — AI advisory
AI may suggest, extract, summarize and draft.
AI must never independently:
- reject a participant
- select a participant
- confirm a placement
- merge duplicate people
- approve an outcome
- overwrite authoritative fields

### C-009 — Server-side authorization
Frontend visibility is not authorization.
Every protected API action must enforce authorization server-side.

### C-010 — Audit
Material state changes, sensitive exports/downloads, permissions, merges, archive/delete, placement confirmation and overrides must create audit events.

## 3. Implementation Discipline

For every feature:
1. define schema/migration;
2. implement domain/service rule;
3. expose API;
4. add permission check;
5. add audit event where required;
6. implement UI;
7. add automated tests;
8. update docs if behavior changes.

## 4. Do Not Guess

If an item appears in `21-OPEN-DECISIONS.md`, do not silently hard-code a policy.

Preferred behavior:
- implement as configuration where safe; or
- leave a clearly documented TODO/blocker; or
- use the implementation default explicitly marked in this package.

## 5. Coding Order

Follow `20-IMPLEMENTATION-ROADMAP.md`.

The 07 Oct 2026 sequencing decision is HAPPY first, integrations second:
Phases 1 through 3 are accepted for their documented local scope. The Supply
local baseline and prototype correction are verified; continue Phase 5 Matching
while keeping visual review and policy/scanner rollout gates explicitly open.
Preserve foundation, IAM, Demand and Supply.
Then CV Parser Phase 7, HAMIS Phase 12, Employer Portal
Phase 13. See `27-INTEGRATION-READINESS.md`. External IDs are references only;
internal UUIDs stay authoritative. Do not renumber applied migration history.

Do not build AI, forecasting, or advanced integrations before core data and workflows are stable.

## 6. Definition of Done

A feature is not complete until:
- required schema exists
- authorization is enforced
- validation is implemented
- audit requirements are implemented
- desktop and mobile behavior is acceptable
- unit/integration tests pass
- critical E2E flow is covered where applicable
- errors are actionable
- no sensitive data leaks to logs

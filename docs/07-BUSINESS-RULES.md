# Business Rule Catalog

## Participants / Supply

### BR-PART-001 — Single participant master
A participant must not be duplicated for each vacancy.

### BR-PART-002 — Minimum intake
Initial participant intake requires at least:
- full name
- active phone
- location

### BR-PART-003 — Formal onboarding gate
Formal employer submission is blocked unless onboarding is complete and required consent is valid.

Error: `ONBOARDING_INCOMPLETE`

### BR-PART-004 — Assisted onboarding
If staff completes onboarding for a participant, record:
- completion mode
- assisting user
- timestamp

### BR-PART-005 — Duplicate detection
Before participant creation, check:
- normalized phone
- government ID hash when available
- email
- high-similarity name + location

Duplicate detection is advisory until an authorized human confirms merge.

### BR-PART-006 — Merge control
Duplicate merge requires explicit permission and audit.
AI must never auto-merge.

---

## Vacancy / Demand

### BR-VAC-001 — Positive headcount
`required_headcount > 0`

### BR-VAC-002 — Outstanding headcount
Operational vacancy outstanding headcount is derived:

`max(required_headcount - started_headcount, 0)`

Do not ask users to manually type outstanding headcount.

### BR-VAC-003 — Programme placement count
Programme placement metrics use `confirmed placements`, not merely starts.

### BR-VAC-004 — Closure reason
Closing/cancelling a vacancy requires a closure reason.

### BR-VAC-005 — Change history
Material changes to salary, location, headcount, working conditions, or key requirements create a vacancy-change record and audit event.

### BR-VAC-006 — Overfill
If starts exceed required headcount:
- block by default; or
- privileged override with reason and audit.

---

## Matching

### BR-MATCH-001 — Vacancy-specific status
Participant status and candidate-vacancy status are separate concepts.

### BR-MATCH-002 — Declining one job
A participant who declines one vacancy remains eligible for other vacancies unless availability/readiness changes.

### BR-MATCH-003 — Human decision
AI match strength is advisory.
Recruiter/human retains decision authority.

### BR-MATCH-004 — Submit gate
Transition to `SUBMITTED` requires:
- active vacancy
- onboarding complete
- required consent active
- candidate not archived/withdrawn

### BR-MATCH-005 — Status history
Every candidate-vacancy status transition is appended to history.

---

## Placement

### BR-PLC-001 — Start
`STARTED` requires `actual_start_date`.

### BR-PLC-002 — Expected first income
Expected first-income date is calculated from:
- actual start date
- payroll frequency
- employer payday/cutoff rule

If payroll rules are insufficient, mark verification scheduling as `EXCEPTION` and require manual due date.

### BR-PLC-003 — Confirmed placement
A placement becomes confirmed only when first income is verified by an authorized user.

### BR-PLC-004 — Historical achievement
After confirmation, later employment exit does not remove the confirmed-placement achievement.

### BR-PLC-005 — Retention
Employment exit updates current employment/retention state and end date.

### BR-PLC-006 — Multiple placements
A participant may have multiple placement records.
Reporting must expose:
- unique participants placed
- total placement records

### BR-PLC-007 — Confirmation correction
Changing/removing a confirmed placement requires elevated permission, reason, and audit.

---

## M&E / MERL

### BR-MERL-001 — Follow-up lineage
Every placement follow-up links to participant and placement.

### BR-MERL-002 — Latest employment state
Current employment status shown on dashboards should use the latest verified outcome/employment status event.

### BR-MERL-003 — Impact story handoff
M&E may identify a potential impact story, but Marketing may only proceed when publication/marketing consent requirements are satisfied.

### BR-MERL-004 — Data-quality issue
Critical data-quality violations create an actionable issue, not only a dashboard count.

---

## Marketing

### BR-MKT-001 — Request lineage
Marketing campaign requests must preserve the requesting workstream and linked business object.

### BR-MKT-002 — Restricted participant access
Marketing receives only data needed for an approved communications workflow.

### BR-MKT-003 — Story consent
Impact story cannot reach `READY_FOR_MARKETING` without required marketing/publication consent.

### BR-MKT-004 — Attribution
Campaign source attribution must never overwrite a participant's authoritative programme history.

---

## Cross-Cutting

### BR-X-001 — Audit
Sensitive or material actions listed in `12-AUDIT-EVENT-CATALOG.md` must emit audit events.

### BR-X-002 — Archive over delete
Use archive for normal operational removal.
Hard delete is privileged.

### BR-X-003 — Optimistic concurrency
When a record changed after a client loaded it, reject stale destructive updates with a concurrency error.

### BR-X-004 — One fact once
Do not create multiple editable copies of the same authoritative fact across modules.

### BR-X-005 — Calculated facts
Age, vacancy age, employment duration, outstanding headcount, target gap and conversion rates are derived, not manually entered.

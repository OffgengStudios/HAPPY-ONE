# HAPPY staging UAT and accessibility acceptance

Status: NOT VERIFIED. No tester or sign-off has been invented. Developer regression results do not substitute for programme acceptance. Run on a pinned deployed staging revision with synthetic data and record HAPPY SHA, UNIJAY SHA, migration head, browser/device and date.

| Role | Scenario | Expected outcome | Tester / result / issue / severity / sign-off |
| --- | --- | --- | --- |
| Supply | Submit through actual UNIJAY, replay, create suspected duplicate, review participant, upload clean CV and review parser suggestions | One participant on replay; duplicate held for human review; Ghana Card protected; selected suggestions approved and at least one rejected; no automatic overwrite | Pending |
| Employer Acquisition | Create Organization, Contact, Partnership, Vacancy, requirements and JD internally | No Employer Portal; private files; version conflicts visible; authorized ownership and audit retained | Pending |
| Recruiter | Match reviewed participant and active vacancy; run Pre-screen → Qualified → Submitted → Interview → Employer Decision → Selected → Started | Human decisions; onboarding/capacity constraints enforced; Started is not confirmed placement | Pending |
| MERL | Record and verify first monthly income after actual start; replay; record follow-up and ended employment | Exactly one confirmed placement; historical outcome preserved; audit retained | Pending |
| Marketing | Use authorized projection and attempt restricted identity/document/export operations | Allowed work succeeds; restricted access denied without sensitive serialization | Pending |
| Management | Inspect dashboard/KPIs and scoped private exports | Confirmed placement counted once; formula input literal; permission scope enforced | Pending |
| Administrator | Provision/deactivate staff, change roles, revoke sessions, inspect operations and resolve incidents | Server-side roles/session revocation; audited changes; safe telemetry; no public operations endpoint | Pending |

For every scenario record tester, role, exact steps, expected/actual result, evidence link, issue, severity and explicit sign-off. A pending row remains NOT VERIFIED. Resolve P0 and blocking P1 before pilot approval.

## Golden flow evidence

Record each step as PASS / FAIL / NOT VERIFIED: actual UNIJAY receipt; Person/Participant; normalized phone/DOB/community; encrypted Ghana Card; consent/interests/source; replay/duplicate review/public enumeration denial; internal Demand; private CV; actual scan; private parser; selected approvals and rejection; matching; recruiter relationship; recruitment transitions; Started unconfirmed; first monthly income verified; one confirmed placement; MERL follow-up/history; management KPI; private formula-safe export. No manual database edits for business transitions.

## Manual accessibility checklist

| Check | Procedure | Result / tester / accepted limitation |
| --- | --- | --- |
| Keyboard | Complete intake, authentication and core staff tasks without a pointer; no trap | Pending |
| Focus | Visible focus, logical order, return to dialog trigger, error-summary focus | Pending |
| Forms/errors | Labels, required fields, instructions, announced inline errors, retained input | Pending |
| Dialogs | Accessible name, modal focus containment, Escape and focus restoration | Pending |
| Tables | Headers, names, sorting status and actions accessible to assistive technology | Pending |
| Mobile | Intake and staff critical flows at narrow width and zoom without lost controls | Pending |
| Screen reader | Read page landmarks, form labels/errors, dialogs and result status | Pending |
| Reduced motion | Respect system preference and avoid essential motion-only information | Pending |

Target reasonable WCAG 2.2 AA alignment. Record device, browser, screen reader and human findings; automated Playwright results alone do not complete this checklist.

## Pilot decision record

Owner approval pending. Record release identity, staff cohort, intake limits, monitoring/response owner, backup/rollback owner, programme privacy approval, approved RPO/RTO, remaining accepted limitations and explicit go/no-go. Keep automatic production deployment disabled. Do not merge or promote production while prerequisites remain open.

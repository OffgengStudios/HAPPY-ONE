# Marketing, M&E/MERL, and Training

## 1. Marketing Request Contract

Required:
- requester
- requesting workstream
- type
- reason
- priority
- linked object where applicable
- due date where known

Examples:
- recruitment promotion for supply gap
- training campaign
- programme awareness
- impact story

## 2. Campaign Assets

Campaign assets are Documents with campaign relationship.

Types may include:
- flyer
- social copy
- photo
- approved participant quote
- video link
- report graphic

Asset approval must not imply participant marketing consent unless consent is explicitly linked.

## 3. Impact Story Data Boundary

Marketing view should receive:
- participant display name if approved
- approved placement/outcome facts
- approved quote/content
- consent status
- approved media

Marketing should not receive by default:
- government ID
- disability data
- internal case notes
- unrelated income history
- unrelated applications

## 4. M&E Follow-Up Scheduling

System should support configurable follow-up templates:
- type
- offset from confirmation/start
- required questions
- role ownership

Do not hard-code 1/3/6/12 month cadence as official until approved.

## 5. Outcome Versioning

Outcomes are time-bound observations.

Do not overwrite historical 3-month outcome when 6-month follow-up occurs.
Create a new observation.

## 6. Training

Training must support:
- internal/external partner
- in-person/virtual/hybrid
- modules
- dates
- location
- attendance
- completion
- certificate
- prior training history at participant level

## 7. Training Attendance

Bulk attendance is allowed.

Each participant attendance remains an individual record.

Statuses:
- PRESENT
- ABSENT
- LATE
- EXCUSED

Completion:
- NOT_STARTED
- IN_PROGRESS
- COMPLETED
- NOT_COMPLETED

## 8. Stipends

Stipend handling is an open business decision.

Do not mix training stipend records with placement salary/first-income logic.

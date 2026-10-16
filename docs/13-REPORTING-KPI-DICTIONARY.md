# Reporting and KPI Dictionary

Every dashboard KPI must map to a code and drill-down query.

## KPI-PLC-001 — Confirmed Placements

**Definition:** Placement records whose first monthly income has been verified and `confirmed_at` falls in the reporting period.

Formula:
`COUNT(placements WHERE confirmed_at in period)`

Drill-down:
placement → participant → vacancy → employer.

## KPI-PLC-002 — Unique Participants Placed

`COUNT(DISTINCT participant_id WHERE placement confirmed_at in period)`

Must be shown separately from total placement records when multiple placements exist.

## KPI-VAC-001 — Positions Required

`SUM(required_headcount)` over selected vacancies.

## KPI-VAC-002 — Started Headcount

Count valid placement records with `actual_start_date` and not failed/cancelled.

Operational employer-fill metric.

## KPI-VAC-003 — Outstanding Positions

Per vacancy:
`max(required_headcount - started_headcount, 0)`

Aggregate:
`SUM(vacancy outstanding)`

## KPI-VAC-004 — Confirmed Placement Headcount

Count confirmed placements linked to vacancy.

Do not confuse with started headcount.

## KPI-VAC-005 — Vacancy Age

If open:
`today - opened_at`

If closed:
`closed_at - opened_at`

## KPI-MATCH-001 — Submission Conversion

`submitted candidates / qualified candidates`

Display denominator and zero-safe behavior.

## KPI-MATCH-002 — Interview Conversion

`interviewed candidates / submitted candidates`

## KPI-MATCH-003 — Start Conversion

`started participants / selected candidates`

## KPI-MATCH-004 — Placement Confirmation Conversion

`confirmed placements / started participants`

## KPI-EMP-001 — Employer Turnaround

Default operational measure:
time from candidate submission to employer decision.

Report median and optionally percentile.

Exact SLA threshold remains configurable.

## KPI-SUP-001 — Onboarding Completion

`participants onboarding COMPLETE / participants registered`

## KPI-SUP-002 — Job Ready

Count participants with:
- readiness `JOB_READY`
- availability `AVAILABLE`
- onboarding complete

## KPI-MERL-001 — Still Working

Latest verified placement employment state = working.

## KPI-MERL-002 — Retention

The platform must support interval-based retention calculation.

Exact official denominator/cadence is an open programme rule.

Implementation should permit:
`working at interval / confirmed placements due for that interval`

## KPI-DQ-001 — Completeness

Required fields populated / required fields expected, according to a versioned completeness rule.

## KPI-DQ-002 — Duplicate Suspects

Open unresolved duplicate-detection cases.

## KPI-MKT-001 — Campaign Leads

Count attributed participant/source leads if source tracking exists.

## KPI-MKT-002 — Campaign Onboarding

Participants whose source is campaign and onboarding completed.

## KPI-MKT-003 — Campaign Placements

Confirmed placements attributable to campaign source, with attribution model clearly documented.

## Management Target Model

Expose:

`Target | Actual | Gap | Forecast`

`Gap = max(Target - Actual, 0)` unless metric direction differs.

Targets live in data/configuration, not code constants.

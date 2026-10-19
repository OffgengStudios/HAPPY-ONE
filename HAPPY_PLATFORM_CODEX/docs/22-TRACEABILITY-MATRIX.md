# Traceability Matrix

| Requirement | Module | API / Service | Test |
|---|---|---|---|
| Employer → MOU → Active | organizations/partnerships | partnership transition | E2E-01 |
| Vacancy required/started/outstanding | vacancies | headcount service | unit + E2E-01 |
| One participant master | participants | participant service | duplicate tests |
| Onboarding submission gate | matching + participants | candidate submit service | E2E-03 |
| CV versioning | files/participants | CV service | integration |
| Candidate vacancy pipeline | matching | transition service | E2E-04 |
| Interview operations | interviews | interview service | E2E-04 |
| Actual start required | placements | confirm-start | unit + E2E-05 |
| First income required | placements | confirm first income | unit + E2E-05 |
| Historical placement preserved | placements | employment end | E2E-06 |
| Multiple placements | placements | placement repository | integration |
| M&E follow-up | merl | follow-up service | E2E-07 |
| Marketing handoff | merl/marketing | request/story service | E2E-07/08 |
| Restricted Marketing PII | IAM + participant projection | serializers/permissions | E2E-09 |
| KPI drill-down | reporting | KPI service | integration |
| Sensitive exports audited | reporting/audit | export service | E2E-10 |
| Vacancy material history | vacancies/audit | update service | integration |
| Role shapes UX | web + IAM | auth/me + navigation config | UI/E2E |

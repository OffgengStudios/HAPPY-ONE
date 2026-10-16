# API Contract

Base path:

`/api/v1`

The backend publishes OpenAPI.

This document is the target contract; not all listed workflows are implemented.
Current authentication remains opaque cookie sessions with exact Origin/CSRF
protection. Future token/client flows require separately authenticated identities.
HAMIS and Employer Portal must reuse the existing HAPPY domain services/APIs;
never introduce duplicate /hamis-participants or portal-only employer databases.
CV parse/approval endpoints below belong to Phase 7 and are not implemented now.

## 1. Conventions

### Authentication
Protected endpoints require authenticated session/token.

### Content
JSON for standard APIs.
Multipart only for file upload.

### IDs
Use UUID in API paths.
Human codes may be search/filter fields.

### Dates
ISO 8601.

### Pagination
List endpoints:
- `limit` default 25, max 100
- `cursor` opaque
- return `next_cursor`

### Sorting
Use explicit allowed sort fields.
Never pass raw SQL column expressions from client.

### Filtering
Use named query parameters.

### Concurrency
Mutable records return `version`.
Update requests include expected `version`.
Stale writes return `409 RECORD_VERSION_CONFLICT`.

### Idempotency
Critical create/confirm actions accept:
`Idempotency-Key`

Use for:
- placement confirmation
- first-income confirmation
- bulk submission
- sensitive imports if added later

## 2. Standard Error Shape

```json
{
  "error": {
    "code": "ONBOARDING_INCOMPLETE",
    "message": "Candidate cannot be submitted because HAPPY onboarding is incomplete.",
    "details": {
      "missing_sections": ["education", "consent"]
    },
    "request_id": "..."
  }
}
```

## 3. Auth / IAM

- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/mfa/verify`
- `GET /auth/me`
- `GET /users`
- `POST /users`
- `GET /users/{id}`
- `PATCH /users/{id}`
- `GET /roles`
- `POST /roles`
- `PATCH /roles/{id}`
- `GET /permissions`

Account password changes and deactivation invalidate existing sessions and
pending MFA challenges. Reusing an invalidated challenge returns
401 MFA_CHALLENGE_EXPIRED; reactivation does not revive it.
This does not configure a production MFA provider or enrollment workflow.

## 4. Employers / Demand

### Organizations
- `GET /organizations`
- `POST /organizations`
- `GET /organizations/{id}`
- `PATCH /organizations/{id}`
- `POST /organizations/{id}/archive`
- `GET /organizations/{id}/activity`

Organization activity requires `organization:view`. Linked partnership events
require `partnership:view`; linked contact events require
`organization_contact:view`. The API filters these events before pagination;
general organization access does not grant access to related audit details.
Explicit DENY overrides apply independently to each resource.

Organization and vacancy activity items include `actor_type` alongside
`actor_id`. Human actors retain internal UUID strings; SYSTEM actors may have
no identifier, and future INTEGRATION actors use controlled identifiers.
These fields are audit attribution, not authentication or permission grants.

### Contacts
- `GET /organizations/{id}/contacts`
- `POST /organizations/{id}/contacts`
- `PATCH /organization-contacts/{contact_id}`

### Partnerships
- `GET /organizations/{id}/partnership`
- `POST /organizations/{id}/partnership`
- `PATCH /partnerships/{id}`
- `POST /partnerships/{id}/transition`

## 5. Vacancies

- `GET /vacancies`
- `POST /vacancies`
- `GET /vacancies/{id}`
- `PATCH /vacancies/{id}`
- `POST /vacancies/{id}/transition`
- `POST /vacancies/{id}/close`
- `GET /vacancies/{id}/changes`
- `GET /vacancies/{id}/activity`
- `POST /vacancies/{id}/requirements`
- `GET /vacancies/{id}/pipeline`
- `GET /vacancies/{id}/headcount`

Headcount response should include:
```json
{
  "required": 20,
  "started": 12,
  "confirmed_placements": 10,
  "outstanding": 8
}
```

## 6. Participants / Supply

- `GET /participants`
- `POST /participants`
- `GET /participants/{id}`
- `PATCH /participants/{id}`
- `POST /participants/{id}/archive`
- `GET /participants/{id}/readiness`
- `POST /participants/duplicate-check`
- `POST /participants/{id}/merge`
- `GET /participants/{id}/applications`
- `GET /participants/{id}/placements`
- `GET /participants/{id}/training`
- `GET /participants/{id}/activity`

### Onboarding
- `GET /participants/{id}/onboarding`
- `PATCH /participants/{id}/onboarding/{section}`
- `POST /participants/{id}/onboarding/complete`
- `POST /participants/{id}/onboarding/transition`

Phase 4 implementation supports basic/contact/demographics/education/employment/
training/review section writes with an expected participant version. Education,
experience and skills are structured arrays, not parser results. Profile changes
reopen onboarding and invalidate a prior review. Completion requires explicitly
approved policy, active programme consent for the current notice, required
sections and configured fields. Missing approval returns ONBOARDING_POLICY_REQUIRED;
unknown policy fields/sections return ONBOARDING_POLICY_INVALID and fail closed.

`GET /participants/{id}/onboarding` includes policy/checklist progress, missing
sections/fields and submission eligibility, but never restricted demographic,
vulnerability, income, identity values or identity lookup hashes.

Additional implemented routes:
- `POST /participants/{id}/readiness`
- `GET|PATCH /participants/{id}/sensitive`
- `PATCH /participants/{id}/identity`
- `GET /supply/dashboard`
- `GET /supply/my-work`
- `GET /supply/owners`

Sensitive routes require separate view/edit grants and audit reads/writes.
Supply activity includes actor_type/actor_id without raw changed values.
Merge, applications, placements and linked training APIs above remain roadmap
contracts, not currently implemented Phase 4 endpoints.

### Consent
- `GET /participants/{id}/consents`
- `POST /participants/{id}/consents`
- `POST /consents/{id}/withdraw`

## 7. CV / Files

- `POST /participants/{id}/cv`
- `GET /participants/{id}/cv`
- `GET /participants/{id}/cv/versions`
- `POST /cv/{id}/parse`
- `GET /cv/{id}/parser-jobs`
- `GET /cv-parser/jobs/{id}`
- `POST /cv-parser/results/{id}/review`

Parsing accepts only an available private CV document. Results remain advisory
until explicit field-level staff review; participant version conflicts reject
stale approvals. Parser failure does not block the underlying CV workflow.
- `POST /cv/{id}/approve-extraction`

Files:
- `POST /files/upload-intent` or direct secured upload flow
- `GET /files/{id}/download-url`
- `POST /files/{id}/archive`

Phase 4 uses direct authenticated multipart `POST /participants/{id}/cv`, with
`file` and expected participant `version`. Downloads use
`GET /files/{id}/download`, an audited no-store attachment rather than a public
storage URL. `POST /files/{id}/rescan` and `POST /cv/{id}/approve` require an
expected participant version and CV edit/view permissions. Pending, rejected
and archived files cannot be approved/downloaded. CV waivers use
`POST /participants/{id}/cv/not-required` with a reason. Parser routes remain
Phase 7 contracts, not implemented integrations.

## 8. Matching

- `GET /candidate-vacancies`
- `POST /candidate-vacancies`
- `GET /candidate-vacancies/{id}`
- `PATCH /candidate-vacancies/{id}`
- `POST /candidate-vacancies/{id}/transition`
- `POST /candidate-vacancies/{id}/pre-screen`
- `POST /candidate-vacancies/{id}/submit`
- `GET /candidate-vacancies/{id}/history`
- `POST /vacancies/{id}/match-suggestions`

`match-suggestions` returns advisory explanations only.

## 9. Interviews

- `GET /interviews`
- `POST /interviews`
- `GET /interviews/{id}`
- `PATCH /interviews/{id}`
- `POST /interviews/{id}/attend`
- `POST /interviews/{id}/no-show`
- `POST /interviews/{id}/reschedule`
- `POST /interviews/{id}/outcome`

## 10. Placements

- `GET /placements`
- `POST /placements`
- `GET /placements/{id}`
- `PATCH /placements/{id}`
- `POST /placements/{id}/confirm-start`
- `POST /placements/{id}/employment-end`
- `GET /placements/{id}/first-income`
- `POST /placements/{id}/first-income/confirm`
- `POST /placements/{id}/first-income/delay`
- `POST /placements/{id}/first-income/exception`
- `POST /placements/{id}/correct-confirmation` privileged

## 11. Training

- `GET /trainings`
- `POST /trainings`
- `GET /trainings/{id}`
- `PATCH /trainings/{id}`
- `POST /trainings/{id}/participants`
- `PATCH /training-attendance/{id}`
- `POST /training-attendance/{id}/certificate`

## 12. M&E / MERL

- `GET /follow-ups`
- `POST /follow-ups`
- `GET /follow-ups/{id}`
- `POST /follow-ups/{id}/complete`
- `GET /outcomes`
- `POST /outcomes`
- `PATCH /outcomes/{id}`
- `GET /data-quality/issues`
- `POST /data-quality/issues/{id}/assign`
- `POST /data-quality/issues/{id}/resolve`

## 13. Marketing

- `GET /marketing/requests`
- `POST /marketing/requests`
- `GET /marketing/requests/{id}`
- `POST /marketing/requests/{id}/transition`

- `GET /campaigns`
- `POST /campaigns`
- `GET /campaigns/{id}`
- `PATCH /campaigns/{id}`
- `POST /campaigns/{id}/transition`
- `POST /campaigns/{id}/metrics`
- `GET /campaigns/{id}/assets`
- `POST /campaigns/{id}/assets`
- `POST /campaign-assets/{id}/review`

Marketing request and campaign payloads may carry a `training_id` for Training
promotion work. Vacancy and Training links are mutually exclusive, and a campaign
linked to a source request must preserve that request's domain lineage. The API
checks `training:view`; metadata cannot bypass authorization.

- `GET /impact-story-candidates`
- `GET /impact-stories`
- `POST /impact-stories`
- `GET /impact-stories/{id}`
- `PATCH /impact-stories/{id}`
- `POST /impact-stories/{id}/transition`
- `GET /impact-stories/{id}/eligible-consents`

## 14. Tasks / Handoffs

- `GET /tasks`
- `POST /tasks`
- `PATCH /tasks/{id}`
- `POST /tasks/{id}/claim`
- `POST /tasks/{id}/complete`

- `GET /handoffs`
- `POST /handoffs`
- `POST /handoffs/{id}/accept`
- `POST /handoffs/{id}/return`
- `POST /handoffs/{id}/complete`

## 15. Reporting

- `GET /reports/dashboard`
- `GET /reports/kpis`
- `GET /reports/kpis/{code}/drilldown`
- `POST /reports/export`
- `POST /reports/export-jobs`
- `GET /reports/export-jobs`
- `GET /reports/export-jobs/{id}`
- `GET /reports/export-jobs/{id}/download`
- `GET /reports/data-quality`
- `GET /reports/targets`
- `POST /reports/targets`
- `PATCH /reports/targets/{id}`

All KPI/dashboard/drilldown requests require an explicit inclusive date range.
Immediate exports are audited, permission checked and capped at 5,000 evidence
rows. Persisted asynchronous jobs generate the full available evidence set into
private object storage. Job inspection/download is requester-scoped. The local
background executor is replaceable; production queue infrastructure remains a
deployment decision rather than part of the API contract.

## 16. Audit

Admin/authorized only:
- `GET /audit-events`
- `GET /audit-events/{id}`

Audit is append-only from application perspective.

## 17. External References (Implemented Foundation)

- GET /external-references?entity_type=...&entity_id=... (cursor/limit)
- GET /external-references/{id}
- POST /external-references
- PATCH /external-references/{id} (metadata + expected version)

POST binds a supported entity's internal UUID to an external system/identifier.
The unique external key cannot be rebound; PATCH changes only metadata.
Reads require external_reference:view plus the entity resource's :view.
Writes additionally require external_reference:manage and entity :edit.
Checks are server-side, repeated inside the service; defaults grant ADMIN only.
Unknown targets return 404, archived writes and duplicate/stale keys return 409.
Metadata is inert and bounded, never a permission or identity source.
No synchronization/portal authentication flow is implemented by these endpoints.
See [integration readiness](27-INTEGRATION-READINESS.md).

## 19. Employer Portal Submission Adapter

- `POST /integrations/employer-portal/submissions` (machine credential)
- `GET /integrations/employer-portal/submissions`
- `GET /integrations/employer-portal/submissions/{id}`
- `POST /integrations/employer-portal/submissions/{id}/convert`
- `POST /integrations/employer-portal/submissions/{id}/review`

The machine endpoint accepts the inspected immutable portal contract and uses its
submission ID for idempotency. Staff reads require `employer_submission:view`;
conversion/review also require `employer_submission:manage`. Conversion maps into
the existing Organization, Contact, Partnership, Vacancy and Requirement services.
It does not create an alternate employer API or bypass domain authorization.

## 18. Global Search (Implemented Shared Shell)

`POST /search` uses the current authenticated session and exact Origin/CSRF
checks. JSON search text stays out of request URLs and ordinary access logs.
The search body is not logged or added to audit metadata.

Request: `q` (trimmed, 2-200 characters), `limit` (25 default, 1-100 per group),
optional `entities` and `cursors` keyed by PARTICIPANT/ORGANIZATION/VACANCY.
Unknown fields/types, duplicate groups, control characters and invalid cursors
are rejected. Wildcard characters are literal text, not query instructions.

Omitting entities returns only groups allowed by participant:view,
organization:view and vacancy:view. Explicitly requesting a forbidden group
or supplying its cursor returns 403. DENY overrides apply through the existing
authorization context; role names and external metadata are not consulted.

Responses are no-store, with `groups` containing `items` and `next_cursor`.
Each item contains only entity_type, authoritative UUID, public code, label
and community context. No identity, vulnerability, income, consent, contact
details or integration metadata is returned, even to administrators.
Participant names/codes/phones and employer/vacancy names/codes are searchable;
archived participants, people, organizations and vacancies are excluded.
Participant public display columns are read in one batch, not per result.

The frontend requests five results per group and replaces each page rather
than downloading every match. Selecting a result opens the existing domain
view, whose API rechecks access independently. Placements and campaigns are
future search groups for Phases 6 and 9, not currently available endpoints.

# Audit Event Catalog

## Training Events

- `training.created`
- `training.updated`
- `training.participants_added`
- `training_attendance.updated`
- `training_attendance.certificate_issued`

Training events use internal UUID entity identifiers and the shared user/system/
integration-aware actor representation.

## Employer Portal Events

- `employer_portal.submission_received`
- `employer_portal.submission_reviewed`
- `employer_portal.submission_converted`

Receipt uses the controlled `INTEGRATION/EMPLOYER_PORTAL` actor. Review and
conversion preserve the authenticated staff user and authoritative HAPPY entity
identifiers.

Audit events are append-only.

Actor types are controlled: USER, PARTICIPANT, EMPLOYER, SYSTEM, INTEGRATION.
Human actor IDs are UUID strings. Non-user actor IDs are controlled codes;
SYSTEM may be unattributed. INTEGRATION does not imply a fake staff account.
AuditActor is attribution only; credentials and server-side authorization remain
separate. Existing user audit events and append-only triggers are preserved.

## Event Naming

`<domain>.<action>`

Examples:
- `participant.created`
- `vacancy.status_changed`
- `placement.first_income_confirmed`

## Mandatory Events

### Authentication / IAM
- `auth.login_success`
- `auth.login_failed`
- `auth.logout`
- `auth.mfa_changed`
- `user.created`
- `user.deactivated`
- `role.assigned`
- `role.removed`
- `permission.override_changed`

### Participant
- `participant.created`
- `participant.updated`
- `participant.archived`
- `participant.merge_started`
- `participant.merged`
- `participant.sensitive_field_viewed` for high-risk fields if policy requires
- `participant.consent_recorded`
- `participant.consent_withdrawn`

### CV / Documents
- `document.uploaded`
- `document.downloaded_sensitive`
- `document.archived`
- `cv.parsed`
- `cv.extraction_approved`

### Employer / Vacancy
- `organization.created`
- `organization.updated`
- `partnership.status_changed`
- `vacancy.created`
- `vacancy.updated_material`
- `vacancy.status_changed`
- `vacancy.closed`
- `vacancy.overfill_override`

### Matching
- `candidate_vacancy.created`
- `candidate_vacancy.status_changed`
- `candidate_vacancy.submitted`
- `interview.created`
- `interview.outcome_recorded`

### Placement
- `placement.created`
- `placement.start_confirmed`
- `placement.first_income_confirmed`
- `placement.confirmation_corrected`
- `placement.employment_ended`

### M&E
- `follow_up.completed`
- `outcome.created`
- `outcome.updated`
- `data_quality_issue.resolved`

### Marketing
- `marketing_request.created`
- `campaign.status_changed`
- `campaign.created`
- `campaign.updated`
- `campaign.metrics_recorded`
- `campaign_asset.created`
- `campaign_asset.reviewed`
- `impact_story.created`
- `impact_story.updated`

### Reporting

- `report.exported`
- `report.export_requested`
- `report.export_completed`
- `report.export_failed`
- `report.export_downloaded`

Request/download preserve the authenticated user. Background completion/failure
uses the controlled SYSTEM actor and the export-job UUID.
- `impact_story.status_changed`
- `impact_story.status_changed`
- `impact_story.published`

### Export / Admin
- `report.exported`
- `report_target.created`
- `report_target.updated`
- `sensitive_export.generated`
- `record.hard_deleted`
- `reference_data.changed`

### External References
- `external_reference.created`
- `external_reference.updated`

Record the internal entity UUID, safe reference UUID/system, actor, request ID,
and changed field names. Do not copy raw external metadata/identifiers into audit.
Future participant.updated/vacancy.created events may have INTEGRATION actors;
that representation does not implement or authorize any synchronization today.

## Audit Payload Rules

Include:
- actor
- entity
- result
- timestamp
- safe before/after diff where useful
- request/correlation ID

Do not include:
- passwords
- tokens
- raw secrets
- complete government ID unless absolutely required
- unnecessary full CV text

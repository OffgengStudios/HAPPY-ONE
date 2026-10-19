# Database Schema

This file defines the target relational schema at implementation level.

## 1. Common Columns

Most mutable domain tables should include:

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | PK |
| `created_at` | timestamptz | required |
| `created_by` | UUID nullable | human user attribution; do not create fake integration users |
| `updated_at` | timestamptz | required |
| `updated_by` | UUID nullable | human user attribution; audit records broader actor context |
| `archived_at` | timestamptz nullable | soft archive |
| `archived_by` | UUID nullable | audit context |
| `source_system` | string | INTERNAL / HAMIS / EMPLOYER_PORTAL / API; default INTERNAL |
| `created_via` | string | STAFF / PARTICIPANT / EMPLOYER / INTEGRATION / SYSTEM; default STAFF |

Use optimistic concurrency via `version` integer or `updated_at` precondition for records with high concurrent-edit risk.

Provenance values are controlled by database checks and the shared Record mixin.
Staff write schemas do not accept them. Recruitment source_type/source_detail
are not system provenance.

### Generic External References

`external_references` contains UUID `id`, `entity_type`, internal UUID
`entity_id`, `external_system`, `external_id`, JSON `external_metadata`,
`created_at`, `updated_at`, and concurrency `version`.
Unique: `(external_system, entity_type, external_id)`.
Supported targets currently PARTICIPANT, ORGANIZATION, VACANCY; the service
validates/locks targets. Internal UUIDs remain primary keys.
Do not add HAMIS/Employer-Portal-specific implementation columns to core tables.
See [integration readiness](27-INTEGRATION-READINESS.md) for API/authorization rules.

Audit actor attribution supports USER, PARTICIPANT, EMPLOYER, SYSTEM, INTEGRATION.
Human actor IDs serialize as UUID strings; controlled non-user codes serialize
as strings. SYSTEM may have no ID. Actor attribution is not authentication.

---

## 2. `users`

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | UUID | yes | PK |
| `email` | citext/string | yes | unique |
| `full_name` | string | yes | |
| `password_hash` | string nullable | no | null if external auth |
| `is_active` | bool | yes | |
| `mfa_enabled` | bool | yes | default false |
| `primary_role_id` | UUID nullable | no | default workspace |
| `last_login_at` | timestamptz | no | |

---

## 3. IAM Tables

### `roles`
`id`, `code`, `name`, `description`, `is_system_role`

System role codes:
- `DEMAND`
- `SUPPLY`
- `MATCHING`
- `MERL`
- `MARKETING`
- `MANAGEMENT`
- `ADMIN`

### `permissions`
`id`, `code`, `resource`, `action`, `description`

### `user_roles`
`user_id`, `role_id`

### `role_permissions`
`role_id`, `permission_id`

### `user_permission_overrides`
`user_id`, `permission_id`, `effect` (`ALLOW|DENY`)

---

## 4. `people`

One human identity.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | UUID | yes | |
| `first_name` | string | yes | |
| `surname` | string | yes | |
| `other_names` | string | no | |
| `date_of_birth` | date | no | |
| `sex` | enum/string | no | reference-data controlled |
| `nationality` | string | no | |
| `phone_raw` | string | yes | never numeric |
| `phone_normalized` | string | yes | indexed |
| `email` | citext/string | no | |
| `government_id_type` | string | no | |
| `government_id_ciphertext` | text | no | sensitive |
| `government_id_hash` | string | no | dedup lookup, indexed |
| `region_code` | string | no | |
| `district_code` | string | no | |
| `community` | string | no | |
| `directions` | text | no | |

Indexes:
- `phone_normalized`
- `email`
- `government_id_hash`
- normalized name search fields

---

## 5. `participants`

Programme relationship.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | UUID | yes | |
| `participant_code` | string | yes | unique, immutable |
| `person_id` | UUID | yes | unique FK person |
| `programme_code` | string | yes | default HAPPY |
| `onboarding_status` | enum | yes | see state machines |
| `cv_status` | enum | yes | |
| `readiness_status` | enum | yes | |
| `availability_status` | enum | yes | |
| `employment_status` | enum/string | no | participant current baseline |
| `current_occupation` | string | no | |
| `current_income_amount` | numeric(12,2) | no | sensitive |
| `current_income_frequency` | enum | no | |
| `implementing_partner` | string | no | |
| `source_type` | enum | no | campaign/referral/etc |
| `source_detail` | string | no | |
| `assigned_team` | string | no | |
| `assigned_user_id` | UUID | no | |
| `profile_completion_pct` | numeric(5,2) | yes | derived/materialized if needed |
| `notes_internal` | text | no | permission controlled |

---

## 6. `consents`

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | yes |
| `participant_id` | UUID | yes |
| `consent_type` | string | yes |
| `status` | enum | yes |
| `consented_at` | timestamptz | no |
| `withdrawn_at` | timestamptz | no |
| `method` | string | no |
| `evidence_document_id` | UUID | no |
| `privacy_notice_version` | string | no |

Marketing/publication consent should use a distinct `consent_type`.

---

## 7. Participant Education / Experience / Skills

### `participant_education`
- `participant_id`
- `education_level`
- `institution`
- `field_of_study`
- `start_year`
- `end_year`
- `is_highest`

### `participant_experience`
- `participant_id`
- `employer_name`
- `role_title`
- `sector`
- `start_date`
- `end_date`
- `description`

### `participant_skills`
- `participant_id`
- `skill_code`
- `skill_name`
- `level`
- `source`
- `verified`

---

## 8. `organizations`

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | yes |
| `organization_code` | string | yes |
| `name` | string | yes |
| `normalized_name` | string | yes |
| `organization_type` | enum | yes |
| `industry_code` | string | no |
| `sector_code` | string | no |
| `region_code` | string | no |
| `district_code` | string | no |
| `community` | string | no |
| `address_text` | text | no |
| `website` | string | no |
| `relationship_owner_id` | UUID | no |
| `status` | enum | yes |

Unique/dedup:
- no hard unique on name alone
- use normalized-name duplicate checks

---

## 9. `organization_contacts`

- `organization_id`
- `full_name`
- `job_title`
- `phone_raw`
- `phone_normalized`
- `email`
- `is_primary`
- `is_active`
- `notes`

At most one active primary contact per organization should be enforced by business rule / partial unique index where possible.

---

## 10. `partnerships`

| Field | Type | Required |
|---|---|---:|
| `partnership_code` | string | yes |
| `organization_id` | UUID | yes |
| `partnership_type` | enum | yes |
| `start_date` | date | yes |
| `end_date` | date | no |
| `status` | enum | yes |
| `mou_required` | bool | yes |
| `mou_sent_at` | timestamptz | no |
| `mou_signed_at` | timestamptz | no |
| `owner_id` | UUID | no |
| `next_action` | string | no |
| `next_action_due_at` | timestamptz | no |

An organization may have multiple dated partnership periods. Controlled types
are `TRAINING`, `RECRUITMENT`, and `COMBINED`; end date cannot precede start date.
Agreement files are immutable versions in `partnership_documents`, keyed by
`partnership_id + version_number`, with private storage metadata, checksum and
fail-closed scan status. Storage keys and hashes are never public API fields.

---

## 11. `vacancies`

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | UUID | yes | |
| `vacancy_code` | string | yes | unique |
| `organization_id` | UUID | yes | |
| `title` | string | yes | |
| `status` | enum | yes | |
| `priority` | enum | yes | |
| `description` | text | no | |
| `location_region_code` | string | no | |
| `location_district_code` | string | no | |
| `location_community` | string | no | |
| `location_directions` | text | no | |
| `salary_min` | numeric | no | |
| `salary_max` | numeric | no | |
| `salary_currency` | char(3) | yes | default GHS |
| `salary_frequency` | enum | no | |
| `work_days_text` | string | no | |
| `work_hours_text` | string | no | |
| `accommodation_available` | bool | no | |
| `required_headcount` | int | yes | > 0 |
| `owner_id` | UUID | no | recruiter |
| `demand_owner_id` | UUID | no | |
| `opened_at` | timestamptz | no | |
| `closed_at` | timestamptz | no | |
| `closure_reason` | enum | no | required when closed/cancelled |
| `closure_note` | text | no | |
| `requirements_json` | jsonb | no | structured non-search-critical extras only |
| `version` | int | yes | optimistic concurrency |

Do not store `outstanding_headcount` as user-entered data.

Derived:
- `started_headcount`
- `confirmed_placement_headcount`
- `outstanding_headcount`

For operational vacancy fill, use `started_headcount` unless the programme explicitly changes this definition.

`outstanding_headcount = max(required_headcount - started_headcount, 0)`

Programme placement reporting uses confirmed placement count, not started count.

Uploaded job descriptions are immutable private records in
`job_description_versions`, keyed by `vacancy_id + version_number`. The mutable
vacancy description remains operational summary text and cannot replace the
versioned source document.

---

## 12. `vacancy_requirements`

Preferred normalized table for matchable criteria:

- `vacancy_id`
- `criterion_type`
- `criterion_key`
- `operator`
- `value_json`
- `is_required`
- `weight`
- `display_order`

Examples:
- manual driving = true
- licence class IN [B,C]
- min experience years >= 2
- preferred location list
- education level

---

## 13. `vacancy_changes`

- `vacancy_id`
- `field_name`
- `old_value_json`
- `new_value_json`
- `reason`
- `changed_by`
- `changed_at`

Material field changes must also emit audit events.

---

## 14. `candidate_vacancies`

Vacancy-specific candidate relationship.

| Field | Type | Required |
|---|---|---:|
| `id` | UUID | yes |
| `participant_id` | UUID | yes |
| `vacancy_id` | UUID | yes |
| `status` | enum | yes |
| `owner_id` | UUID | no |
| `source` | enum | no |
| `match_strength` | enum | no |
| `match_explanation_json` | jsonb | no |
| `pre_screen_result` | enum | no |
| `submitted_at` | timestamptz | no |
| `selected_at` | timestamptz | no |
| `closed_reason` | enum | no |
| `closed_note` | text | no |

Constraint:
- unique active relationship per `(participant_id, vacancy_id)`

---

## 15. `candidate_status_history`

- `candidate_vacancy_id`
- `from_status`
- `to_status`
- `reason`
- `actor_id`
- `occurred_at`

---

## 16. `interviews`

- `candidate_vacancy_id`
- `scheduled_at`
- `timezone`
- `format`
- `location_or_link`
- `status`
- `outcome`
- `notes`
- `created_by`

---

## 17. `placements`

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | UUID | yes | |
| `placement_code` | string | yes | unique |
| `participant_id` | UUID | yes | |
| `candidate_vacancy_id` | UUID | yes | |
| `organization_id` | UUID | yes | denormalized FK for reporting |
| `vacancy_id` | UUID | yes | |
| `status` | enum | yes | |
| `expected_start_date` | date | no | |
| `actual_start_date` | date | no | |
| `salary_amount` | numeric | no | sensitive |
| `salary_currency` | char(3) | yes | default GHS |
| `salary_frequency` | enum | no | |
| `payroll_frequency` | enum | no | |
| `payday_rule_json` | jsonb | no | |
| `expected_first_income_date` | date | no | calculated |
| `confirmed_at` | timestamptz | no | set only after first income |
| `employment_end_date` | date | no | |
| `employment_end_reason` | enum | no | |
| `currently_working` | bool | no | latest verified value |

---

## 18. `first_income_verifications`

- `placement_id` unique
- `status`
- `verification_due_date`
- `actual_income_received_date`
- `verified_at`
- `verified_by`
- `amount_received`
- `evidence_document_id`
- `exception_reason`
- `notes`

---

## 19. `employment_status_history`

- `placement_id`
- `status`
- `effective_date`
- `source`
- `verified_by`
- `notes`

---

## 20. Training Tables

### `trainings`
- `training_code`
- `title`
- `training_type`
- `partner_organization_id`
- `trainer_type`
- `mode`
- `start_date`
- `end_date`
- `location_*`
- `modules_json`
- `status`

### `training_attendance`
- `training_id`
- `participant_id`
- `attendance_status`
- `completion_status`
- `certificate_issued`
- `certificate_document_id`

Unique `(training_id, participant_id)`.

---

## 21. `follow_ups`

- `participant_id`
- `placement_id`
- `follow_up_type`
- `scheduled_for`
- `status`
- `completed_at`
- `completed_by`
- `contact_result`
- `notes`

---

## 22. `outcomes`

- `participant_id`
- `placement_id`
- `follow_up_id`
- `as_of_date`
- `currently_working`
- `current_income_amount`
- `income_frequency`
- `job_satisfaction`
- `challenges_text`
- `progress_text`
- `skills_gained_text`
- `household_community_effects_text`
- `support_needed_text`
- `impact_story_potential`
- `verified_by`

---

## 23. Marketing

### `marketing_requests`
- `request_code`
- `requesting_workstream`
- `requesting_user_id`
- `request_type`
- `vacancy_id` nullable
- `training_id` nullable
- `participant_id` nullable only for approved story flow
- `reason`
- `priority`
- `status`
- `due_at`
- `owner_id`

### `campaigns`
- `campaign_code`
- `title`
- `campaign_type`
- `status`
- `owner_id`
- `vacancy_id` nullable
- `training_id` nullable
- `marketing_request_id` nullable
- `audience`
- `channels_json`
- `planned_publish_at`
- `published_at`
- `metrics_json`

### `campaign_assets`
- `campaign_id`
- `asset_type`
- `title`
- `document_id` nullable, never a participant CV
- `external_url` nullable
- `content_text` nullable
- `approval_status`
- `consent_id` nullable

### `impact_stories`
- `participant_id`
- `source_outcome_id`
- `marketing_consent_id`
- `status`
- `owner_id`
- `draft_text`
- `approved_at`
- `published_at`

---

## 24. Reporting

### `report_targets`
- `kpi_code`
- `period_start`
- `period_end`
- `dimension_key` (`GLOBAL` in the current approved contract)
- `target_value`
- `forecast_value` nullable
- `notes` nullable
- controlled provenance and audit columns

The active KPI/period/dimension tuple is unique. Actuals are computed from domain
tables and are not copied into target records.

---

## 25. Cross-Cutting Tables

### `tasks`
- `task_code`
- `title`
- `description`
- `status`
- `priority`
- `owner_user_id`
- `owner_team`
- `due_at`
- polymorphic record reference via `entity_type`,`entity_id`
- `completed_at`

### `handoffs`
- `from_workstream`
- `to_workstream`
- `entity_type`
- `entity_id`
- `reason`
- `status`
- `sent_by`
- `assigned_to`
- `sent_at`
- `accepted_at`
- `completed_at`

### `activities`
- `activity_type`
- `entity_type`
- `entity_id`
- `actor_id`
- `summary`
- `details`
- `occurred_at`

### `documents`
- `document_code`
- `document_type`
- `entity_type`
- `entity_id`
- `storage_key`
- `original_filename`
- `mime_type`
- `size_bytes`
- `sha256`
- `version_number`
- `scan_status`
- `uploaded_by`

### `audit_events`
- `event_code`
- `actor_type`
- `actor_id`
- `action`
- `entity_type`
- `entity_id`
- `result`
- `before_json` nullable
- `after_json` nullable
- `metadata_json`
- `ip_address` nullable
- `occurred_at`

Do not store secrets or unnecessary sensitive raw values in audit JSON.

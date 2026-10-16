# Domain Model

## 1. Aggregates

### Identity / IAM
- User
- Role
- Permission
- UserRole
- RolePermission
- UserPermissionOverride
- Session

### Employer / Demand
- Organization
- OrganizationContact
- Partnership
- Vacancy
- VacancyChange

### Participant / Supply
- Person
- Participant
- Consent
- ParticipantSkill
- ParticipantEducation
- ParticipantExperience
- CVDocument

### Matching
- CandidateVacancy
- CandidateStatusHistory
- Screening
- Interview

### Placement
- Placement
- FirstIncomeVerification
- EmploymentStatusHistory

### Training
- Training
- TrainingAttendance
- Certificate

### M&E / MERL
- FollowUp
- Outcome
- DataQualityIssue

### Marketing
- MarketingRequest
- Campaign
- CampaignAsset
- ImpactStory

### Cross-Cutting
- Task
- Handoff
- Activity
- Document
- AuditEvent
- ExternalReference
- Notification

ExternalReference binds a supported internal UUID to a unique
(external_system, entity_type, external_id) key. Participant, Organization, and
Vacancy remain authoritative; integration IDs never become their primary keys.
Controlled record provenance is shared, not a collection of portal-specific fields.
Audit actors include non-user/system attribution without fake human accounts.
See [integration readiness](27-INTEGRATION-READINESS.md) for implemented boundaries.

## 2. Cardinalities

```text
Person 1 ── 0..1 Participant
Participant 1 ── * Consent
Participant 1 ── * ParticipantEducation
Participant 1 ── * ParticipantExperience
Participant * ── * Vacancy        via CandidateVacancy
CandidateVacancy 1 ── * Interview
Participant 1 ── * Placement
Vacancy 1 ── * Placement
Organization 1 ── * Vacancy
Organization 1 ── * OrganizationContact
Organization 1 ── * Partnership
Placement 1 ── * FollowUp
Placement 1 ── * Outcome
Participant * ── * Training       via TrainingAttendance
MarketingRequest 0..1 ── 1 Vacancy/Training/Outcome reference
Campaign 0..* ── 0..1 Vacancy
Campaign 0..* ── 0..1 Training
ImpactStory * ── 1 Participant
```

## 3. Aggregate Ownership

- Organization owns contacts and partnership relationships.
- Vacancy owns recruitment-demand state and headcount.
- Participant owns readiness profile and programme relationship.
- CandidateVacancy owns vacancy-specific recruitment progression.
- Placement owns employment event and first-income lifecycle.
- FollowUp/Outcome own post-placement evidence.
- Campaign owns marketing-production state.

## 4. Shared-Record Rule

There must be one participant record across Supply, Matching and M&E.

There must be one vacancy record across Demand, Supply, Matching, Marketing and Management.

Role-specific UI projections must not be implemented as duplicate domain records.

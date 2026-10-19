# RBAC and Permissions

Phase 2 adds `external_reference:view` and `external_reference:manage`, with
default ADMIN grants only. Both are independent of entity access: reads require
entity :view; writes require entity :view and :edit as well as both reference
permissions. Explicit DENY takes precedence. External metadata cannot grant access.
See [integration readiness](27-INTEGRATION-READINESS.md).

## 1. Permission Naming

Use:

`<resource>:<action>`

Actions:
- `view`
- `create`
- `edit`
- `approve`
- `assign`
- `export`
- `download`
- `merge`
- `archive`
- `delete`
- `manage`

Examples:
- `participant:view`
- `participant_sensitive:view`
- `vacancy:edit`
- `placement:confirm`
- `report:export`
- `user:manage`

## 2. Baseline Role Matrix

Legend:
- `E` = edit/create operationally
- `V` = view
- `R` = restricted/aggregated
- `A` = approve/manage
- `-` = no default access

| Resource | Demand | Supply | Matching | M&E | Marketing | Management | Admin |
|---|---|---|---|---|---|---|---|
| Employers | E | V-limited | V | V | V-limited | V | A |
| Partnerships/MOU | E | - | V | V | - | V | A |
| Partnership documents | E/download | - | - | - | - | V/download | A |
| Vacancies | E | V | E | V | V | V | A |
| Job descriptions | E/download | - | V/download | - | - | V/download | A |
| Participant basic | R | E | V/E workflow | V | R | R/V | A |
| Participant sensitive | - | permitted | permitted subset | permitted subset | - | restricted | A |
| CV | - | E | V | V if needed | - | - | A |
| Candidate pipeline | V | V-limited | E | V | - | V aggregate | A |
| Interviews | V | - | E | V | - | V aggregate | A |
| Placement | V | V | E | V | - | V | A |
| First income | - | - | E | V | - | V aggregate | A |
| Follow-ups/outcomes | - | - | V | E | R approved | V | A |
| Training/attendance | - | E | V | E | V | V | A |
| Employer Portal submissions | E | - | - | - | - | - | A |
| Marketing requests | create/view own | create/view own | create/view own | create/view own | E | V | A |
| Campaigns | V | V | V | V | E | V | A |
| Impact stories | - | - | - | E handoff | E | V | A |
| Reports | V scope | V scope | V scope | E scope | V scope | V all | A |
| Sensitive export | - | controlled | controlled | controlled | - | controlled | A |
| User/role admin | - | - | - | - | - | - | A |

This matrix is a baseline, not a substitute for endpoint-level permission checks.

## 3. Sensitive Field Groups

### Identity Restricted
- government ID full value
- ID documents

### Employment Restricted
- current income
- placement income

### Vulnerability Restricted
- disability data
- displacement/refugee details if collected

### Internal Restricted
- private admin notes
- security/audit metadata

Implement field serializers/projections so unauthorized callers never receive restricted fields.

Organization activity is also a permission-limited projection. An
`organization:view` grant alone does not expose linked partnership or contact
events: their respective view permissions are checked server-side before
pagination. Role names and hidden frontend tabs are not security boundaries.

Do not merely hide them in the UI.

## 4. Search Permission

Global search must filter results by:
- resource permission
- record scope if applicable
- sensitive-field projection

Marketing searching a participant must not receive hidden sensitive fields.

## 5. Exports

Export permission is separate from view permission.

All sensitive exports require:
- permission check
- privacy warning acknowledgement
- audit event
- server-side field projection

## 6. Privileged Actions

Require specific permissions:
- `participant:merge`
- `placement:confirm`
- `placement:correct_confirmation`
- `vacancy:overfill_override`
- `record:hard_delete`
- `report:sensitive_export`
- `role:manage`
- `partnership_document:view`, `partnership_document:edit`, `partnership_document:download`
- `job_description:view`, `job_description:edit`, `job_description:download`

# Validation and Error Catalog

## Error Shape

See `09-API-CONTRACT.md`.

## Core Errors

| Code | HTTP | Meaning |
|---|---:|---|
| `VALIDATION_ERROR` | 422 | field validation failed |
| `NOT_FOUND` | 404 | entity not found |
| `FORBIDDEN` | 403 | lacks permission |
| `UNAUTHENTICATED` | 401 | login/session required |
| `RECORD_VERSION_CONFLICT` | 409 | stale update |
| `DUPLICATE_SUSPECTED` | 409/422 | probable duplicate needs review |
| `ONBOARDING_INCOMPLETE` | 422 | cannot submit |
| `CONSENT_REQUIRED` | 422 | required consent missing/withdrawn |
| `VACANCY_NOT_ACTIVE` | 422 | operation needs active vacancy |
| `INVALID_STATUS_TRANSITION` | 422 | state machine violation |
| `HEADCOUNT_EXCEEDED` | 422 | start would overfill vacancy |
| `START_DATE_REQUIRED` | 422 | cannot mark started |
| `FIRST_INCOME_NOT_VERIFIED` | 422 | cannot confirm placement |
| `PLACEMENT_ALREADY_CONFIRMED` | 409 | duplicate confirmation |
| `MARKETING_CONSENT_REQUIRED` | 422 | story cannot progress |
| `FILE_TYPE_NOT_ALLOWED` | 422 | upload blocked |
| `FILE_TOO_LARGE` | 413 | upload too large |
| `FILE_SCAN_PENDING` | 409 | file unavailable pending scan |
| `EXPORT_NOT_PERMITTED` | 403 | export permission missing |
| `IDEMPOTENCY_CONFLICT` | 409 | key used with different payload |

## Validation Examples

### Phone
- store raw
- normalize to E.164 where possible
- reject obviously invalid length/structure
- never coerce to numeric

### Email
- validate shape
- case-insensitive comparison

### Salary
- must be >= 0
- min <= max

### Headcount
- integer > 0

### Dates
- actual start cannot be after employment end
- first income received cannot precede actual start
- follow-up `as_of_date` cannot precede placement start where linked

### Government ID
Do not expose precise validation details that aid enumeration.
Validate supported formats server-side.

## Concurrency UX

On `RECORD_VERSION_CONFLICT`:
- fetch latest record
- show what changed where practical
- user retries intentionally
- never silently overwrite

# State Machines

State transitions are validated server-side.

## 1. Partnership / Employer Relationship

States:
- `LEAD`
- `CONTACTED`
- `ENGAGED`
- `INTERESTED`
- `MOU_PENDING`
- `MOU_SIGNED`
- `ACTIVE`
- `INACTIVE`
- `DECLINED`

Typical path:

`LEAD → CONTACTED → ENGAGED → INTERESTED → MOU_PENDING → MOU_SIGNED → ACTIVE`

Allowed exceptions:
- `LEAD|CONTACTED|ENGAGED|INTERESTED → DECLINED`
- `ACTIVE → INACTIVE`
- `INACTIVE → ACTIVE` with reason

MOU may be skipped only if configuration/business rule explicitly marks it not required.

---

## 2. Vacancy

States:
- `DRAFT`
- `PENDING_CONFIRMATION`
- `ACTIVE`
- `PARTIALLY_FILLED`
- `ON_HOLD`
- `FULLY_FILLED`
- `CLOSED`
- `CANCELLED`

Transitions:
- `DRAFT → PENDING_CONFIRMATION`
- `DRAFT → ACTIVE` if confirmation not required
- `PENDING_CONFIRMATION → ACTIVE`
- `ACTIVE → PARTIALLY_FILLED`
- `PARTIALLY_FILLED → FULLY_FILLED`
- `ACTIVE|PARTIALLY_FILLED → ON_HOLD`
- `ON_HOLD → ACTIVE|PARTIALLY_FILLED`
- `ACTIVE|PARTIALLY_FILLED|ON_HOLD → CLOSED`
- `DRAFT|PENDING_CONFIRMATION|ACTIVE|PARTIALLY_FILLED|ON_HOLD → CANCELLED`

`CLOSED` and `CANCELLED` require closure reason.

System may automatically recommend, but not silently enforce, `PARTIALLY_FILLED/FULLY_FILLED` based on headcount unless configured.

---

## 3. Participant Status Dimensions

Do not use one giant participant state.

### Onboarding
- `NOT_STARTED`
- `IN_PROGRESS`
- `COMPLETE`
- `BLOCKED`
- `WITHDRAWN`

### CV
- `MISSING`
- `UPLOADED`
- `PARSING`
- `REVIEW_REQUIRED`
- `READY`
- `NOT_REQUIRED`

### Readiness
- `NOT_ASSESSED`
- `DEVELOPING`
- `JOB_READY`
- `NOT_JOB_READY`

### Availability
- `UNKNOWN`
- `AVAILABLE`
- `TEMPORARILY_UNAVAILABLE`
- `UNAVAILABLE`

Formal employer submission requires:
- onboarding `COMPLETE`
- not withdrawn
- required consent active

---

## 4. Candidate–Vacancy

Primary states:
- `POTENTIAL_MATCH`
- `RECRUITER_REVIEW`
- `PRE_SCREEN`
- `QUALIFIED`
- `SUBMITTED`
- `INTERVIEW`
- `EMPLOYER_DECISION`
- `SELECTED`
- `STARTED`
- `AWAITING_FIRST_INCOME`
- `CONFIRMED_PLACEMENT`

Terminal/exception states:
- `NOT_INTERESTED`
- `UNREACHABLE`
- `NO_SHOW`
- `REJECTED`
- `WITHDRAWN`
- `SALARY_DECLINED`
- `LOCATION_DECLINED`
- `FAILED_TO_START`
- `EMPLOYER_CANCELLED`

Happy path:

`POTENTIAL_MATCH → RECRUITER_REVIEW → PRE_SCREEN → QUALIFIED → SUBMITTED → INTERVIEW → EMPLOYER_DECISION → SELECTED → STARTED → AWAITING_FIRST_INCOME → CONFIRMED_PLACEMENT`

Rules:
- `SUBMITTED` requires onboarding gate.
- `STARTED` requires placement record with actual start date.
- `CONFIRMED_PLACEMENT` requires verified first income.

---

## 5. Interview

States:
- `SCHEDULED`
- `ATTENDED`
- `NO_SHOW`
- `RESCHEDULED`
- `CANCELLED`
- `COMPLETED`

Outcome:
- `PASSED`
- `REJECTED`
- `PENDING_EMPLOYER_DECISION`
- `NOT_APPLICABLE`

---

## 6. Placement

States:
- `START_PENDING`
- `STARTED`
- `AWAITING_FIRST_INCOME`
- `CONFIRMED`
- `ENDED`
- `FAILED_TO_START`
- `CANCELLED`

Transitions:
- `START_PENDING → STARTED`
- `START_PENDING → FAILED_TO_START`
- `START_PENDING → CANCELLED`
- `STARTED → AWAITING_FIRST_INCOME`
- `AWAITING_FIRST_INCOME → CONFIRMED`
- `STARTED|AWAITING_FIRST_INCOME → ENDED` if participant leaves before confirmation
- `CONFIRMED → ENDED`

Once `CONFIRMED`, `confirmed_at` is immutable except privileged correction with audit.

---

## 7. First Income Verification

States:
- `NOT_SCHEDULED`
- `UPCOMING`
- `DUE`
- `OVERDUE`
- `CONFIRMED`
- `PAYMENT_DELAYED`
- `CANDIDATE_LEFT`
- `EXCEPTION`

A scheduler/service derives `UPCOMING/DUE/OVERDUE` from dates.

Only authorized human verification sets `CONFIRMED`.

---

## 8. Task

- `OPEN`
- `IN_PROGRESS`
- `BLOCKED`
- `COMPLETED`
- `CANCELLED`

---

## 9. Handoff

- `SENT`
- `ACCEPTED`
- `IN_PROGRESS`
- `COMPLETED`
- `RETURNED`
- `CANCELLED`

---

## 10. Marketing Request

- `REQUESTED`
- `ACCEPTED`
- `IN_PRODUCTION`
- `AWAITING_REVIEW`
- `APPROVED`
- `PUBLISHED`
- `COMPLETED`
- `CANCELLED`

---

## 11. Campaign

- `DRAFT`
- `IN_PRODUCTION`
- `AWAITING_REVIEW`
- `APPROVED`
- `SCHEDULED`
- `PUBLISHED`
- `COMPLETED`
- `CANCELLED`

---

## 12. Impact Story

- `IDENTIFIED`
- `CONSENT_PENDING`
- `READY_FOR_MARKETING`
- `DRAFTING`
- `REVIEW`
- `APPROVED`
- `PUBLISHED`
- `REJECTED`
- `CANCELLED`

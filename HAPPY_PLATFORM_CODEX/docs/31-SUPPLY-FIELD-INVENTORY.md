# Supply Onboarding Field Inventory

User direction recorded 07 Oct 2026: use the supplied participant information
headers for Supply onboarding. This approves the field inventory as the working
reference, not privacy-notice wording or an inferred all-fields-mandatory policy.
No spreadsheet rows, production participants or HAMIS synchronization are imported.

Updated 29 October 2026 for the user-authorized participant lifecycle changes.
See [current lifecycle behavior and reporting](52-PARTICIPANT-LIFECYCLE.md).

| Supplied Header | HAPPY Representation | Treatment |
| --- | --- | --- |
| PARTICIPANT ID | Participant UUID / participant_code | Generated, immutable HAPPY identity |
| HAMIS ID | ExternalReference, external_system HAMIS | Reference only; never the primary key |
| ONBOARDING DATE | Participant onboarding_date | Explicit programme business date, separate from creation and completion audit timestamps |
| IMPLEMENTING PARTNER | implementing_partner | Staff-recorded partner |
| REGION / DISTRICT / COMMUNITY | Person region_code / district_code / community | Contact/location section |
| LOCATION STATUS | Person location_status | Contact/location section |
| SURNAME / FIRST NAME / OTHER NAMES | Person surname / first_name / other_names | Basic section |
| SEX / DOB / NATIONALITY | Person sex / date_of_birth / nationality | Separate sensitive permissions; demographics write |
| AGE | DOB to today or the relevant onboarding/training/placement date | Read-only current and event-specific ages; future onboarding/training ages are projected |
| PARTICIPANT TYPE AGE | No invented category | Age-band definition requires programme policy |
| TELEPHONE | phone_raw / phone_normalized | String input and E.164 normalization |
| ID TYPE / GHANA CARD ID / VOTER ID | Independent protected Ghana Card and Voter's ID slots with lookup hashes | Both coexist; ordinary APIs return presence only; full values require an explicitly selected authorized sensitive export |
| REFUGEE STATUS | SensitiveProfile refugee_status | Restricted |
| DISPLACEMENT STATUS / REASON | SensitiveProfile displacement_status / displacement_reason | Restricted, conditional applicability needs policy |
| ORIGINAL / HOST COMMUNITY | SensitiveProfile original_community / host_community | Restricted displacement context |
| DISABILITY STATUS / SPECIFY | SensitiveProfile disability_status / disability_specify | Restricted; Yes requires specification at completion |
| EDUCATION LEVEL | ParticipantEducation education_level | Historical qualifications, explicit highest flag |
| EMPLOYMENT STATUS / CURRENT OCCUPATION | Participant employment_status / current_occupation | Employment baseline |
| MONTHLY INCOME / INCOME FREQUENCY | SensitiveProfile current_income_amount / income_frequency | Restricted; entered frequency is authoritative, not an assumed monthly conversion |
| SECTOR / INDUSTRY / JOB TYPE / JOB ROLE | Participant sector_code / industry_code / job_type / job_role | Employment section; no official taxonomy invented |
| WORK REGION / DISTRICT / COMMUNITY | Participant work_region_code / work_district_code / work_community | Employment section |
| LOCAL QUEUE ID / WRITE EVENT ID | Future integration metadata | No core-table integration fields added |
| Repeated PARTICIPANT ID / blank columns | No duplicate field | Ignore presentation-only duplicates/blanks |

## Completion Policy

Initial intake requires first name, surname, valid telephone and community.
Required formal-onboarding sections/fields are configuration, with explicit
programme approval and current programme consent. Derived IDs, calculated age,
queue metadata and blank columns cannot be made mandatory participant inputs.
Sensitive data is not made universally mandatory merely because its header
exists. The user confirmed Ghana Card as required at completion, while permitting
drafts. Refugee Yes requires nationality and disability Yes requires specification.
Other mandatory-field and approved privacy-notice settings remain independently
controlled. The localhost self-test notice is synthetic, not production consent approval.

## Outstanding Mapping Decisions

Confirm age-band boundaries/reference dates, Outreach support classification,
income-band boundaries and official location/occupation taxonomy. These decisions
must not be silently inferred from a spreadsheet. Independent identity storage
and the explicit onboarding date have been implemented under the user's direction.

HAMIS mapping/synchronization belongs to Phase 12. Any later source rows must map
into the same HAPPY domain services, permissions and business rules, with separate
integration metadata and conflict/source-of-truth rules agreed at that phase.

## Kollekt Reference Review

Read-only source review on 07 Oct 2026, commit
`0389cbac919844a2e13b34ea74b2775a03ce005a` (31 Aug 2026).
No deployment endpoint was called and no spreadsheet rows or signatures were read.

The [existing consent screen](https://github.com/Murphy-Richard/happy-kollekt/blob/0389cbac919844a2e13b34ea74b2775a03ce005a/index.html#L321)
explains programme purposes, collected data, sharing and participant rights,
with a link to the Mastercard Foundation privacy policy. Its participant form
marks onboarding date, implementing partner, region, district, location status,
surname, first name, sex, date of birth, telephone, education level and employment
status as required. These are legacy form requirements, not new HAPPY policy.

[Consent validation and submission](https://github.com/Murphy-Richard/happy-kollekt/blob/0389cbac919844a2e13b34ea74b2775a03ce005a/js/app.js#L508)
require venue, surname, first name, phone, signature and an agreement checkbox.
The payload carries time, language and request ID, but no notice-version field.
The [consent log writer](https://github.com/Murphy-Richard/happy-kollekt/blob/0389cbac919844a2e13b34ea74b2775a03ce005a/apps-script/Code.gs#L2153)
also has no notice-version value in its row mapping.

Existing wording is a concrete candidate for reuse, pending user confirmation.
The source commit identifies the reviewed artifact; it is not a policy approval
date or proof of programme approval. If approved, HAPPY must retain its own
versioned consent records, server-side gates and private storage. Do not copy
the Sheets/Drive backend or interpret a programme consent as marketing consent.

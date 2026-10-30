# Participant lifecycle and programme reporting

Implemented for local validation on 28 October 2026. This does not approve outstanding programme classifications or a hosted release.

## Shared records and navigation

The participant profile has Overview, Onboarding, Capacity Building, Placements & Employment, Documents and Activity. Onboarding sections retain the existing draft-save, consent, review and readiness workflows. Training and placement lists link to the same participant UUID. Enrolments and employment observations are individual records; neither duplicates the participant master.

## Registration and identity

`participants.onboarding_date` is the programme business date, separate from creation and completion timestamps. `support_type` is recorded separately from age classification. No dates or classifications are invented for existing participants.

Ghana Card is now always a completion/submission requirement. Drafts remain available. The configured privacy notice, consent and required-section checks continue to apply. Refugee Yes requires nationality at completion; disability Yes requires disability specification. Previously recorded conditional details are retained when the controlling answer changes.

Migration 0040 adds a separate protected Voter's ID ciphertext/HMAC slot. Existing Voter's ID ciphertext is moved intact out of the legacy typed slot, leaving Ghana Card and Voter's ID independently writable. This is a structural migration of existing application records, not an import of workbook participants. Existing Ghana Card encryption material and lookup behavior are retained. Ordinary APIs return presence indicators only. Updates remain explicitly saved, permission checked and audited.

On first successful onboarding completion, employment status, occupation and income are captured as the baseline. Reopening onboarding, editing current income or recording an employment observation does not replace that baseline. Existing completed records with no captured baseline remain incomplete for that reporting detail; their baseline is not guessed from later data.

## Calculated ages

All ages are completed calendar years from DOB, subtracting one before the birthday:

| Projection | Reference date |
| --- | --- |
| Current Age | Today in Africa/Accra |
| Age at Onboarding | Onboarding Date |
| Age at Training Start | Each training event's Start Date |
| Age at Placement Start | Actual placement start |

Missing dates produce no age. Events before DOB are rejected. Future onboarding and scheduled training ages are labelled projected. An actual placement start cannot be in the future; its expected-start workflow remains separate. Historical ages remain fixed as time passes, but audited corrections to DOB or event dates recalculate affected projections. Previous onboarding dates/DOB are retained in restricted onboarding revisions; training date changes retain their previous dates in audit history.

The technical calendar convention treats 29 February birthdays as advancing on 1 March in a non-leap year. Programme approval of this convention remains open.

Age classifications are explicitly pending. The workbook's age-36 discrepancy, support-type-dependent formula and the proposed onboarding-age cohort anchor have not been silently turned into policy.

## Training

Existing Training and TrainingAttendance remain authoritative. Agriculture Sector extends event metadata. Received and completed module lists belong to each enrolment; completing a course does not populate either list automatically. Completed modules must also be received. Shared curriculum is edited on the training event, while individual learning is edited on attendance. Existing certificate linkage remains available in Training and now rejects evidence that has not passed scanning.

## Placement and employment

Placement metadata supports the 16 supplied labels, with independent work location, placing partner, sector, industry, job type, role, employment type/category, pay, employer, contract and work hours. Income needs an explicit frequency. Currency is explicit. The current hours control explicitly accepts hours per week, with a nonnegative limit of 168; no existing unlabelled hours are backfilled or interpreted.

Actual start and verified first income remain separate actions. Entering salary or classifying employment does not confirm a placement. Confirmed metadata corrections require the existing elevated correction permission and a reason. A later exit preserves the historical confirmation.

Independent verified employment observations use the existing MERL Outcome model with a nullable placement link. They support self-employment and improved/additional work without fabricated employers or vacancies. Their genuine employment start, observation date and staff verification are recorded. Corrections retain outcome revisions. They are excluded from existing placement-based KPIs pending agreement on programme population rules.

Agriculture outcome measures use a typed conditional form with explicit units, including a required unit when harvest volume is entered. No agriculture fields are indiscriminately added to recruitment placement entry.

Migration 0041 separates known, unknown, not-recorded and not-applicable income. An actual zero remains numeric zero. A non-amount status cannot contain an amount; known income requires an amount and frequency. Baseline income availability is preserved alongside the amount.

## Programme reports

- `GET /api/v1/reports/programme?date_from=...&date_to=...` returns separate distinct-person and record counts, actionable participant DQA links and reporting definitions.
- `GET /api/v1/reports/programme/export?...` downloads an XLSX with the exact 26 onboarding, 26 capacity-building and 33 employment headers, plus the separate 16-column Placements sheet and Report Notes.
- Dates in each Age column are event-specific. Identity, demographics and income remain permission scoped. Sensitive exports require sensitive-export permission, sensitive participant access and privacy acknowledgement. Full ID numbers require an additional explicit opt-in and are audited; ordinary exports leave them blank.
- XLSX text is encoded as literal inline strings, preventing formula execution. Numeric ages, amounts and quantities remain numeric. Headers wrap, the first row is frozen, and notes preserve row grain and placement-to-participant references.
- Onboarding rows use onboarding dates; capacity rows use training start dates; recruitment placement rows use actual starts. Employment rows include placements confirmed by period end with the latest observation available at that date, plus independent verified observations in the selected observation period. These are operational export rules, not an approved programme KPI definition.
- Current working state for placement rows uses dated employment evidence, rather than a later exit applied retrospectively. Missing onboarding dates are excluded from dated onboarding rows and shown in DQA. The DQA queue includes undated records across the programme.
- Monthly income reports only directly compatible GHS monthly amounts. Other frequencies/currencies are not silently converted. Unknown and not-applicable income remain distinct labels. Income-band boundaries remain pending.
- Exports are capped at 5,000 rows per section. Narrow the period when the cap is reached. Reporting-period locking and official multi-job population rules remain open; generated notes identify the officer, period and revision timestamp.

The supplied source workbook is read-only. Its header order and unchanged SHA-256 were verified; no participant rows were imported. PostgreSQL remains the system of record.

## Local verification

Use the existing optimized local launcher with `.local/runtime/self-test.env`. The local helper recognises migration 0041 and retains the explicit Ghana Card requirement. Live synthetic records are archived and verified absent from active worklists/reports, preserving immutable audit and outcome revisions. Isolated integration schemas are disposed by their fixtures.

Validation evidence and any remaining limitations are reported with the task result. No push, merge or hosted deployment is authorized by this work.

### Verification checkpoint — 29 October 2026

- Broad backend regression: 391 passed, two skipped. Final focused lifecycle checks: 11 passed, including all placement metadata, verification gating, event ages, preserved baseline and restricted exports.
- Optimized desktop/mobile browser journeys: two passed, with screenshot review and no browser errors or horizontal overflow. These exercise separate IDs, individual training modules, self-employment observations and workbook download.
- Python formatting/lint/mypy and frontend ESLint/TypeScript passed. Local schema is at 0041 with no migration drift; private pre-migration backups were verified.
- An independent Excel reader verified the downloaded workbook's exact headers/order, styles, frozen header rows and literal text content. The source workbook's SHA-256 and all three source header sequences were verified unchanged.
- Five live synthetic participant records and eight training events were archived. No active records from these fixtures remain; immutable audit and outcome revisions are preserved.
- Programme age classification, Outreach support treatment, income bands and official outcome-counting policy remain explicitly pending. This is local functional verification, not hosted-production certification.

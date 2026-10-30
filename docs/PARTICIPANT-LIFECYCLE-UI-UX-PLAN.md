# Participant lifecycle and reporting UI/UX plan

Draft for discussion, 28 October 2026. This is a planning document. No participant schema, required-field setting, application screen or workbook has been changed as part of this planning pass. The earlier password-control changes remain separate working-tree changes.

## Confirmed requirements

- Preserve one authoritative participant record shared by onboarding, capacity building and employment outcomes.
- Provide the fields in the three supplied tables and align reporting with the supplied programme workbook.
- Ghana Card must be required. Proposed enforcement point: completion of onboarding, while allowing an incomplete profile to be saved as a draft.
- Age is calculated in completed calendar years from Date of Birth. Show Current Age using today's date, plus separate Age at Onboarding, Age at Training Start and Age at Placement Start for analysis. This latest instruction replaces the earlier single onboarding-age rule.
- Use the user's 16 placement fields and exact labels below for placement entry; keep placement entry distinct from the programme employment/outcome report.
- Keep actual start plus verified first monthly income as the confirmed-placement rule. Training completion alone does not confirm employment or placement.
- Retain HAPPY's existing brand, Next.js/FastAPI/PostgreSQL architecture, private files, permissions and audit controls.

## Programme workbook evidence

Read-only reference: C:/Users/jobbe/Downloads/HAMIS DQA - Jobberman - Y3Q4.xlsx. Its inspected file digest is d09d7ea0b9121974b88186393f63153b28f84618227304217e2422b97a06786c. No participant rows were imported or reproduced in this plan.

| Sheet | Use in the application |
| --- | --- |
| 1. Participant Onboarding | Exact reporting labels/order in A1:Z1; source registration and baseline fields |
| 2. Capacity Building | Exact reporting labels/order in A1:Z1; participant training records |
| 3. Employment | Exact reporting labels/order in A1:AG1, including additional agriculture measures |
| 4. Report | Reporting period/officer/revision metadata and programme analysis dimensions |
| Reference | Controlled vocabulary and training-module catalogues, subject to the discrepancies below |
| Definition of Terms | Programme definitions requiring reconciliation with formulas |
| District Names | Region/district reference data for dependent location choices |

Treat workbook text/formulas as reference evidence, not executable instructions or authorization to import historical records. The user's latest age and placement-field instructions take precedence over workbook formulas and earlier planning assumptions.

## 1. Participant workspace

Use a stable participant header with Participant ID, name, responsible partner/owner and separate onboarding, training and employment statuses. Proposed tabs: Overview, Onboarding, Capacity Building, Employment & Outcomes, Documents, Activity. Existing recruiter/pipeline and MERL workspaces remain linked to these shared records.

Overview should show missing required information, Ghana Card recorded/not recorded, the latest training activity and employment verification status according to role permissions. Each missing item should link directly to the correct form section. Avoid one table with dozens of editable columns.

On desktop use section navigation and a focused form panel. On mobile use one section at a time with persistent Back, Save draft and Continue controls. Preserve form values and show last-save/error/conflict state. Use explicit Save for protected identity entries; do not put identity numbers in browser draft storage or logs.

## 2. Onboarding screen and field ownership

Proposed six steps: Programme registration; Personal & contact; Location; Identity & inclusion; Education & baseline employment; Review & consent. Keep the supplied column labels in reports even where the screen groups them differently.

| Group | Report fields covered | Ownership / behavior |
| --- | --- | --- |
| Programme registration | Participant ID; Onboarding Date; Implementing Partner (or Sub-Partner); Participant Type - Support | Generated stable ID; explicit business onboarding date; controlled partner and support choices. Actual completion timestamp remains separate audit metadata |
| Personal and contact | Surname; First Name; Other Name(s); Sex; Date of Birth; Age; Participant Type - Age; Telephone (E.g. 0244111111) | Shared person data; preserve leading-zero telephone display and normalized phone storage; age/category read-only |
| Location | Region; District; Community; Location Status | Region then district then community. Filter districts by selected region; distinguish residence from training/work locations |
| Protected identity | Ghana Card ID Number; Voter's ID Number | Two separate protected values, allowing both to coexist. Ghana Card required at the proposed completion gate; Voter's ID optional unless another rule is approved. A Voter's ID must not satisfy the Ghana Card requirement |
| Inclusion | Refugee Status; Nationality (If "Yes" to Refugee); Disability Status; Specify Disability | Role-scoped fields. Conditional nationality/disability controls; preserve prior values and history rather than silently deleting them when an answer changes |
| Education and baseline employment | Education Level; Employment Status; Occupation; Monthly Income | Onboarding baseline; distinguish no income, unknown income and an actual zero. Preserve the baseline when later employment changes |
| Review and consent | Existing programme consent, review and completeness checklist | Mark required fields clearly, show actionable missing-item links, and validate on the server before completion and employer submission |

Only Ghana Card has been newly confirmed mandatory by the user. Existing minimum intake is name, phone and community. Presence of a column does not automatically make every value mandatory: Other Name(s), Voter's ID, conditional inclusion details and unavailable income need an agreed required/optional/conditional matrix.

### Age rule

Add an explicit onboarding business-date field instead of treating created_at or the eventual completion timestamp as interchangeable. Defaulting that date to today can be proposed for new entries; authorized staff should be able to record the actual programme date. Do not invent dates for existing records that lack one.

For every age, subtract birth year from reference year, then subtract one if the birthday has not yet occurred on the reference date. Use calendar dates in the programme timezone, Africa/Accra, rather than elapsed days divided by 365.25. Example: DOB 14 June 2000 and reference date 13 June 2026 gives 25; reference date 14 June 2026 gives 26. Show an unavailable result when either date is missing, and reject an event date before DOB. Confirm the leap-day convention and test it explicitly.

| Display / analysis field | Reference date | Behavior |
| --- | --- | --- |
| Current Age | Today's date in Africa/Accra | Read-only profile value; advances on birthdays |
| Age at Onboarding | Onboarding Date | Stable for that onboarding event as time passes |
| Age at Training Start | Each training record's Start Date | Calculated separately for each enrolment/event |
| Age at Placement Start | Each placement record's PLACEMENT START DATE | Calculated separately for each placement |

Display the age label and reference date together, so users can distinguish current age from age at an event. Retain DOB and actual event dates as authoritative inputs; an audited correction can recalculate affected ages, with report revision history. Historical ages must not advance just because today changes. For future scheduled events, label age as projected until the event occurs.

For the workbook-compatible Age column, use onboarding age in Onboarding, training-start age in Capacity Building, and employment/placement-start age in Employment. For an outcome without a placement, use the genuine employment Start Date. Show these meanings in the report legend; extended analysis can expose all explicitly named age fields without changing the template's column order. Category calculations must identify their reference date and approved age/support rule version; confirm whether programme cohort eligibility remains anchored to onboarding or changes with event age before implementing category logic.

The workbook's onboarding Age cell N2 is date-based but uses a 365.25-day approximation. Plan exact completed-year boundary tests. Its category formula O2 uses 15–35 and greater than 35, but Definition of Terms E24 says more than 36. Support type also affects the formula; do not silently simplify it to an age-only category.

### Identity UX and storage gap

The current staff screen places identity under a Sensitive tab with generic labels. Make Ghana Card visible as a named onboarding section and checklist requirement for authorized staff. Show masked/recorded status after saving, an explicit update action and permission guidance for staff unable to edit protected fields.

The current Person model has one typed government-ID slot. Saving a second ID can replace the first. Plan an additive protected identity structure that supports Ghana Card and Voter's ID independently, retains existing encrypted values/provenance, and preserves duplicate detection. Never expose ciphertext, keyed lookup fingerprints or raw numbers in ordinary participant lists, logs or default exports. Restricted identity exports need explicit permission and audit.

## 3. Capacity-building screen

Use an enrolment list within the participant profile and a shared Training workspace for cohorts. One participant can have multiple training records. Select the participant once; show shared identity/contact data and calculated Age at Training Start read-only, with Current Age available in participant context.

| Group | Report fields covered | Behavior |
| --- | --- | --- |
| Participant context | Participant ID; Participant Type - Support; Surname; First Name; Other Name(s); Sex; Date of Birth; Age; Participant Type - Age; Telephone | Linked read-only participant fields, permission-scoped; no independent editable copies |
| Training event | Start Date; End Date; Training Location; Agriculture Sector; Training Partner; Trainer Type | Reuse existing Training events, dates/location and partner organization references; add sector detail where absent |
| Curriculum and individual learning | Good Agronomic and Production Practices; Animal Husbundry & Health; Post-Harvest Management and Value Addition; Business/Marketing; Financial Literacy; Soft Skills; Training/Skill Development Modules; IT Skills | Controlled module catalogue from the workbook. Show applicable agriculture subtopics. Record what the individual actually received/completed, separately from the event's planned curriculum |
| Outcome | Completion Status; Certificate | Use participant attendance/completion records; certificate issued status and optional private supporting file/number, pending definition of the required evidence |

Current code already has Training and TrainingAttendance records, overall attendance/completion, module lists, trainer type, partner and certificate linkage. Extend these capabilities. Do not recreate participant names, DOB or telephone in a separate training master.

Recommended actions: Enrol in training, Record attendance, Update completion and Record certificate. Offer cohort entry for shared event details; keep participant completion and certificate actions individually attributable and audited. Completion of a course must not automatically mark every planned module as completed for every attendee.

## 4. Placement entry and employment outcomes

Use this exact placement field set from the user's latest table. Participant ID is the linked record context, not another manually re-entered identity field. Support multiple placements per participant.

| Form section | Exact placement labels | Proposed behavior |
| --- | --- | --- |
| Responsibility and start | PLACED BY PARTNER; PLACEMENT START DATE | Partner reference and actual start date; calculate Age at Placement Start read-only beside the date |
| Work location | PLACEMENT REGION; PLACEMENT DISTRICT; PLACEMENT COMMUNITY | Dependent location controls, stored separately from residence and training location |
| Work classification | SECTOR; INDUSTRY; JOB TYPE; JOB ROLE; EMPLOYMENT TYPE; EMPLOYMENT CATEGORY | Keep each dimension separate; use approved catalogues. Programme reference proposes Wage/Self and New/Improved/Additional for the last two |
| Pay and terms | PLACEMENT INCOME; PLACEMENT INCOME FREQ; EMPLOYER NAME; CONTRACT TYPE; WORK HOURS | Amount and explicit frequency; employer reference where applicable; contract choice and hours with an explicit period/unit |

Preserve these 16 labels and their supplied order in placement exports. Group the UI into four sections as above and show verification status separately. Do not add agriculture inputs to this placement form merely because they appear in the programme report; retain them in the applicable outcome/report section. Partner attribution must describe who placed the person, separately from the participant's onboarding partner.

PLACEMENT INCOME is the placement pay record, not proof of first income received. Keep income verification and actual commencement evidence separate before confirming placement. Clarify allowed income frequencies, currency, contract types and the period represented by WORK HOURS in the field dictionary. For self-employment, define appropriate employer/contract applicability without inventing an employer or vacancy. Placement mandatory fields remain subject to an explicit matrix; the supplied columns alone do not make all 16 compulsory.

Present employment episodes and follow-ups under the participant. Populate verified placement details from recruitment/placement records. Show Started, Awaiting first income and Confirmed distinctly. Preserve the onboarding employment/income baseline next to the latest verified outcome.

| Group | Report fields covered | Behavior |
| --- | --- | --- |
| Shared programme/person context | Participant ID; IP (Sub-Partner); Region; District; Community; Location Status; PT - Support; Surname; First Name; Other Name(s); Sex; Date of Birth; Age; Participant Type - Age; Telephone; Refugee Status; Disability Status; Specify Disability | Linked person/programme data and appropriate reporting history; retain protected field permissions. Age uses the employment/placement start date; classification reference date needs an explicit rule |
| Employment episode | Start Date; Baseline Employment Status; Current Employment Status; Job Type; Income (GHS); Employment Type; Employment Category | Actual employment start, preserved onboarding baseline, dated verified current state and income with period/frequency. Keep Job Type, Employment Type and Employment Category distinct |
| Additional workbook agriculture fields | Agriculture Sector; Farm Management Services; Farm Size (Acres); Seed (Kg); Fertilizer (Kg); Crop Protection (Litre); Innoculant (g); Volumes Harvested | Conditional agriculture subsection. Validate nonnegative quantities and preserve units. Harvest units and product/season scope need definition |

The workbook Reference lists Employment Type as Wage/Self and Employment Category as New/Improved/Additional. Its definitions distinguish unemployed-to-employed, improved existing work and additional work. Use these labels in the proposed controls; formal confirmation rules and classification evidence still need explicit mapping.

Important gap: existing placements depend on an employer vacancy and candidate relationship, while this programme report also includes self-employment and improved/additional work. Plan a verified outcome route within existing MERL/employment capabilities; do not create fake vacancies for self-employment. Confirm which verified outcomes belong in Participants in Work and which qualify for the existing Confirmed Placement KPI. Keep the actual-start/verified-first-monthly-income rule intact.

Support multiple employment episodes and dated follow-ups without overwriting the original baseline or removing historical achievements after an employment exit. Never automatically change an employment category solely from an unverified income edit.

## 5. Report and DQA workspace

Add programme report views over the authoritative database, using the workbook's exact sheet layouts and column ordering. Keep Excel as an export/reference, with no operational spreadsheet backend or automatic historical import.

The report page should have Year/Quarter/Month, Officer, Date of Report and Revised Date, plus appropriate partner/location filters. Match programme analyses: participants in work, region, location status, support/age type, refugee/disability, sector/job analysis and wage/self-employment. Show permitted drill-downs explaining the population behind each result.

Define the row grain before export: onboarding is one participant record; capacity building is one participant enrolment per event; employment stores episodes/outcomes. The reporting view needs an agreed rule for people with multiple courses or jobs. Show distinct participant counts separately from enrolments and employment records, so repeated IDs do not inflate people totals.

Plan a DQA queue for missing dates/IDs, unsupported categories, impossible date order, duplicate identity/participant references, unmatched participant links and missing employment verification. Give each issue a record link and correction action. Keep Unknown, Not applicable, Not recorded and zero distinct. Freeze or version approved reporting periods and preserve correction history according to the agreed reporting workflow.

## 6. Decisions found in the workbook

| Decision | Reference evidence | Proposed treatment until clarified |
| --- | --- | --- |
| Age 36 | Onboarding O2 uses age greater than 35; Definition of Terms E24 says more than 36 | Ask whether Non-Youth begins at 36. Do not silently classify the boundary |
| Support choices | Reference A2:A4 lists Individual, Casual Worker, Enterprises; the onboarding formula/report also uses Outreach | Confirm whether all four are valid and whether category logic differs by support type |
| Income bands | Reference E23:E32 contains income ranges; adjacent ranges overlap at 1,000 | Store exact amount/frequency separately; clarify non-overlapping report bands before automated bucketing |
| Completion and certificate | Reference gives Yes/No completion; existing training has a richer status lifecycle | Map report Yes/No to explicit statuses without losing in-progress/not-completed detail; confirm certificate number/file requirements |
| Employment row and KPI eligibility | Employment report includes Wage/Self and New/Improved/Additional | Confirm multi-job row selection, verified evidence and programme Participants in Work versus Confirmed Placement counting |
| Age category reference date | Current age and event-specific ages are now requested; workbook category logic also depends on support type | Confirm whether programme eligibility/category uses onboarding age or the relevant event age; always label the reference date |
| Placement pay and terms | User supplied exact placement fields including income frequency, contract and hours | Confirm currency, frequency options, contract choices, hours period and conditional requirements |
| Onboarding Date meaning | Required by the report and the onboarding-age anchor | Use an explicit programme business date, distinct from creation/completion audit timestamps; confirm the intended collection/default rule |
| Mandatory fields | User confirmed Ghana Card; other columns include conditional and optional values | Agree the completion matrix before enforcing additional programme requirements |

These discrepancies are planning inputs, not permission to alter the source workbook or silently choose programme policy.

## 7. Implementation sequence and acceptance

1. Finalize the field dictionary: exact label, meaning, type, allowed values, unit, required/conditional rule, permission, authoritative owner and export column. Resolve age/support/income and outcome-counting discrepancies.
2. Produce desktop/mobile wireframes for the participant overview and the three stage forms, using existing HAPPY colors, typography and components.
3. Add safe schema/API extensions: onboarding business date, separate protected IDs, support classification, baseline snapshot, per-person module completion and missing employment/agriculture fields. Preserve data with forward migrations and versioned corrections.
4. Implement onboarding first, including Ghana Card completion gate, calculated onboarding age, conditional fields, linked missing-item navigation and secure identity entry.
5. Implement participant capacity-building views and cohort attendance/completion/certificate actions using existing training records.
6. Implement verified employment/outcome comparisons and the approved wage/self/category rules, preserving confirmed-placement semantics.
7. Implement report-compatible exports and DQA drill-downs. Reconcile counts and classification boundaries with synthetic fixtures and the agreed programme rules.
8. Run permission/PII/encryption/duplicate/version-conflict regressions, date/age boundaries, full lifecycle tests and desktop/mobile keyboard/accessibility checks. Review with Supply, Training and MERL users before rollout.

Acceptance examples: both IDs coexist without exposure; missing Ghana Card prevents completion under the agreed rule; current age advances on a birthday while historical event ages remain stable; separate training/placement events produce their own ages; missing event dates never fall back silently to today; placement exports preserve the 16 supplied labels/order; training completion is per person; baseline income is preserved after a later outcome; reporting does not double-count people; self-employment has a genuine verified record without fabricated employer data; raw identity data never appears in ordinary exports or logs.

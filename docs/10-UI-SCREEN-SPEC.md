# UI Screen Specification

## 1. Global Shell

### Desktop
- left navigation
- global search
- profile/account menu
- role/workspace label
- main content
- optional breadcrumb
- responsive right drawer for detail/quick edits

### Mobile
- compact top bar
- role/workspace context
- bottom navigation
- `More` menu
- role-specific quick-add floating action
- bottom sheets / full-screen drawers for actions

## 2. Role Navigation

### Demand
`Dashboard | My Work | Employers | Vacancies | Marketing Requests`

### Supply
`Dashboard | My Work | Participants | Vacancies | Training/Reports`

### Matching
`Dashboard | My Work | Vacancies | Participants | Interviews | First Income`

### M&E / MERL
`Dashboard | My Work | Participants | Outcomes | Reports`

### Marketing
`Dashboard | My Work | Campaigns | Requests | Impact Stories`

### Management
`Dashboard | Attention | Performance | Reports | Administration(if permitted)`

## 3. Dashboard Screen

Each role gets:
- 4 primary KPI cards
- Needs Attention
- role-specific queue
- drill-down links

Do not render generic cross-role cards to everyone.

## 4. My Work

Sections:
- Overdue
- Due Today
- Upcoming
- High Priority
- Recently Assigned

Each row/card:
- title
- related entity
- priority
- due state
- owner
- next action
- open/action button

Management version is labeled `Attention & Approvals` and prioritizes escalations.

## 5. Employers

Views:
`Pipeline | Active | MOU Pending | Inactive | All`

Employer record tabs:
- Overview
- Contacts
- Partnership / MOU
- Partnership history and agreement versions
- Vacancies
- Activity
- Documents

Header:
- name
- relationship status
- owner
- next action
- due date
- last activity

## 6. Vacancies

Views differ by role.

### Demand
Tabs:
`Overview | Employer | Job descriptions | Requirements | Changes | Activity`

### Supply
Tabs:
`Overview | Supply Gap | Candidate Pool | Requirements`

### Matching
Tabs:
`Overview | Pipeline | Interviews | Placements | Activity`

### Marketing
Tabs:
`Overview | Campaigns | Assets`

### M&E
Tabs:
`Overview | Placements | Outcomes`

### Management
Summary first:
- required
- started
- confirmed placements
- outstanding
- age
- bottleneck
- risk

Vacancy card must show:
- role
- employer
- location
- status
- required
- started/filled
- outstanding
- age
- next action

## 7. Participants

### Supply
Tabs:
`Overview | Onboarding | CV | Training | Applications | Activity`

Primary actions:
- Complete profile
- Create/upload CV
- Call
- Mark readiness/availability

### Matching
Tabs:
`Overview | Applications | CV | Screening | Placements | Activity`

Primary actions:
- Match to vacancy
- Pre-screen
- Open CV
- Send to Supply if onboarding incomplete

### M&E
Tabs:
`Overview | Placements | Follow-Ups | Outcomes | Training | Activity`

### Demand
Aggregated supply intelligence by default, not unrestricted participant browsing.

### Marketing
Only approved impact-story/consent context.

## 8. Participant Onboarding

Stepper:
1. Basic
2. Contact & Location
3. Demographics
4. Education
5. Employment
6. Training
7. Consent
8. CV
9. Review

UX:
- autosave
- completion percentage
- missing fields
- staff-assisted indicator
- save draft
- connection/saving state

## 9. Matching Pipeline

Desktop:
- Kanban/pipeline view
- table view toggle
- filters
- bulk actions

Mobile:
- stage filter
- stacked cards
- no compressed horizontal table

Stages follow `06-STATE-MACHINES.md`.

## 10. Interview Day

List by time.

Quick actions:
- Attended
- No-show
- Reschedule
- Outcome
- Employer decision pending

## 11. First-Income Queue

Sections:
- Overdue
- Due Today
- Upcoming
- Exceptions

Card:
- participant
- employer
- vacancy
- start date
- expected first-income date
- days overdue
- salary if user permitted

Actions:
- Confirm Paid
- Payment Delayed
- Candidate Left
- Other Exception

Confirm action requires confirmation dialog.

## 12. M&E Follow-Up

Form:
- still working?
- current role/employer
- current income
- employment duration shown derived
- satisfaction
- challenges
- progress
- skills gained
- household/community effects
- support needed
- impact story potential
- next follow-up

## 13. Marketing

### Campaigns
Views:
`Requests | Production | Approval | Scheduled | Published | Performance`

Campaign record:
- linked source request
- linked vacancy/training
- audience
- channels
- assets
- owner
- next action
- due date
- publish date
- metrics

### Impact Stories
Views:
`Identified | Consent Pending | Ready | Drafting | Review | Approved | Published`

## 14. Management Performance

Must include:
- Target → Actual → Gap → Forecast
- placement trend
- outstanding positions
- risk cards
- vacancy bottlenecks
- employer turnaround
- M&E follow-up
- data quality

Every KPI is clickable to drill-down.

## 15. Search

Always permission-aware.

Grouped result types:
- Participants
- Employers
- Vacancies
- Placements
- Campaigns

Do not return inaccessible entities.

## 16. Error UX

Every blocked action should state:
- why
- required fix
- next action

Example:

> Cannot Submit Candidate  
> HAPPY onboarding must be completed before employer submission.  
> [Send to Supply]

## 17. Mobile Performance

- avoid large client bundles
- lazy load heavy views
- do not download large tables until opened
- paginate lists
- compress preview assets

## 18. Shared Shell Checkpoint (07 Oct 2026)

The existing desktop sidebar is preserved. The authenticated mobile header
shows HAPPY with the full platform name retained as the accessible heading.
Workspace context remains above content rather than a large wrapped menu.
Mobile uses up to three permitted primary views and a More button in a fixed
bottom band. Overflow views, account security and permitted administration
actions open in a modal bottom sheet; no second permission catalog is created.
Desktop uses the same allowed views in its sidebar.

The bottom band and content padding include safe-area spacing. The native
modal handles focus isolation and Escape; More explicitly restores focus to
its trigger on dismissal. Switching to desktop dismisses an open mobile sheet
and focuses the selected sidebar item. Session expiry removes both authenticated navigation and
the sheet. Existing API permissions remain the security boundary.

All six shared-shell browser cases passed in full local CI across desktop/mobile,
including a 320 px sheet, overflow access, workspace changes, keyboard dismissal,
focus restoration, resize and server-denied administration. Full CI passed with
219 backend, four environment and 48 browser tests, build/lint/types and clean
dependency audits. A later development-only badge correction passed lint/types
and live desktop/mobile preview checks; navigation hit tests confirm controls
are unobscured. Live screenshots were inspected, and sign-in/sign-out passed
without changing staff credentials or programme records.
This is not acceptance of the provisional
colours/font, nor completion of all requirements in this specification.
The shared header now has an account menu with identity/workspace context,
Account security and Sign out. It uses keyboard navigation, Escape dismissal,
outside dismissal, resize handling and a retryable sign-out failure state.
Existing sessions and security settings are reused.

Global search groups the implemented Participants, Employers and Vacancies.
Requests are debounced and abort superseded work; input/results stay in memory,
not URLs or a persistent PII cache. Each group has bounded cursor paging,
loading, empty and retry states. Choosing a result opens its existing UUID-backed
domain view and focuses workspace content; dismissal returns focus to Search.
The server filters groups by resource permissions independently of role/workspace.
Employers navigation likewise follows organization:view across workspaces;
roles still determine the default primary navigation.

All twelve desktop/mobile header cases passed in the fresh full CI checkpoint.
Coverage includes account-menu keyboard/dismissal/resize behavior and failure
recovery, bounded paging, UUID-backed read-only record opening, stale responses,
retry, permission denials and real session expiry. A browser regression exposed
native search-input Escape clearing before dialog cancellation; the input now
dismisses on one press and restores Search focus on desktop and mobile.
Screenshots were inspected. Live preview checks passed at 1440, 412 and 320 px
using the existing local account: menu/search framing, empty states, focus,
sign-in/sign-out and unobscured navigation, with no page errors or overflow.
This does not resolve the final colours/font
decision. Placement/campaign search remains required in
Phases 6/9. Role-specific quick-add, broader drawer/sheet coverage and remaining
workstream views were still outstanding at that checkpoint.

## 19. Blue Recruitment Theme and Motion (07 Oct 2026)

User direction: Jobberman-inspired blue accents and recruitment styling, with
Apple-like fluidity. HAPPY keeps its identity and shared operational records.
The subsequently supplied `index-1.html` prototype provides the concrete reference:
#004AB9 blue, #003A92 hover, #E7F0FF soft blue, #101A38 full-height desktop sidebar,
#F5F8FB background, white search/account bar and blue initials avatar. Arial matches
the prototype's actual fallback; no external font request or installation of the
ZIP's third-party logo/RedMERL name is made. KPI items have light borders/shadows;
shared sections stay unframed and compact controls retain the established radius.
The search button expands on desktop but still opens the existing accessible
search dialog; it shrinks safely at the 768 px desktop breakpoint. Mobile keeps
the compact header, bottom navigation and permission-filtered More sheet.

Motion is brief and eased: 160 ms control feedback, 260 ms surface/workspace
entrances and 360 ms drawers/sheets. Desktop actions enter from the right; mobile
actions enter from below. Only opacity/transform are animated for surfaces, not
layout dimensions. No scroll takeover, delayed authorization, staggered rows or
decorative continuous animation is added. Reduced-motion preferences remove
entrances/transitions and spinning indicators; live preference changes cancel
workspace animation. Closing remains immediate, so focus and authenticated UI
teardown never wait on animation.

Mobile quick-add shows only implemented commands permitted by effective resource
view/create grants. Workspace determines ordering, not security. A single action
opens directly; multiple actions use a native modal sheet. Reference data must be
ready before a form opens, with retry/cancel on failure. Creators outside eligible
staff workspaces start with an unassigned owner. DENY overrides remove commands
and the API still independently rejects prohibited writes.

Existing staff forms share a desktop right drawer/mobile full-screen action
panel, sticky header/actions and safe-area spacing. Resizing preserves unsaved
form state; cancellation restores a visible opener or workspace content. Existing
save/autosave/concurrency guards remain in force. No new domain APIs, migration,
permission catalog, integration client or programme policy is introduced.

The design direction is confirmed; rendered visual acceptance awaits user review.
Full local CI passed on 08 Oct 2026: 219 backend, four environment and 66 browser
tests, with clean dependency audits. Live checks at 1440, 800, 768,
412 and 320 px passed for overflow, header/menu/search framing, focus and logout.
Screenshot inspection caught a white navigation background inherited inside the
dark sidebar; its background and select-text contrast are now explicitly styled
and regression-tested. Twelve quick-add/action-surface cases and ten theme/motion
cases cover responsive framing, permission overrides, reference-data retry,
unsaved-state preservation and focus restoration. Historical test counts above
describe the preceding
implementation, not this change. See [visual-reference boundaries](32-VISUAL-REFERENCE.md).

## 20. Intake Owner Permission Follow-Up (08 Oct 2026)

New participant and quick-add share the staff-options wait/retry/cancel path.
The initial owner is the creator only when the server's eligible-owner options
include that user; otherwise intake starts unassigned. Supply workspace access
does not override an effective participant-edit DENY. API assignment checks and
edit authorization remain unchanged. Fourteen quick-add/action-surface cases
now include denied-editor intake and preserved defaults for eligible staff.
Full local CI passed: 220 backend, four environment and 68 browser tests, plus
dependency audits. User visual acceptance and operational policy/scanner gates
remain open.

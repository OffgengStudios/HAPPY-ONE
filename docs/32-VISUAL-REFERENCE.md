# Visual Reference: HAPPY Prototype v4

Received from the user on 07 Oct 2026 after confirmation of Jobberman blue-accent
recruitment styling and Apple-like fluidity. Reference file:
`C:\Users\jobbe\Downloads\index-1.html`.
SHA-256: `07660409497e3e2e0a40267a711e2b10bff18c520a88f31a68492ba0f9929623`.
Its title identifies a HAPPY role-based prototype v4. Desktop/mobile screenshots
were rendered locally and inspected; the reference has no external script/font
or data-service dependency. The source file is not modified or copied into the app.

## Visual Mapping

- Recruitment blue #004AB9, hover #003A92 and soft blue #E7F0FF.
- Navy #101A38 desktop sidebar, 260 px wide, fixed from top to bottom.
- Pale #F5F8FB workspace with white surfaces and #DBE3EC borders.
- Brand/workspace context inside the desktop sidebar, with legible navigation
  and dark text inside its white workspace select.
- White sticky main header with expanding search control and blue initials avatar.
- Compact mobile header, bottom navigation, More sheet and authorized quick-add.
- Light KPI-item borders/shadows, stronger page headings and responsive staff drawers.
- Arial matches the supplied prototype's actual fallback rendering; its Inter
  declaration does not load an Inter font. No external font download is added.

The app retains compact established controls and unframed shared sections rather
than copying nested prototype cards. The search control reuses the existing modal
and bounded permission-aware API, not the prototype's demonstration search toast.
The narrow desktop breakpoint must fit search/profile controls without overflow.

## Motion

The separate user request for fluidity adds brief eased control feedback and
workspace/menu/sheet/drawer entrances. Animation uses CSS and native Web Animations;
no new dependency, scroll takeover or decorative autoplay is introduced. Surface
animation uses opacity/transform rather than layout dimensions. Reduced-motion
preferences disable nonessential motion and live preference changes cancel active
workspace animation. Dismissal, focus restoration and authentication teardown are
immediate; existing save/autosave guards are preserved.

## Authority Boundaries

The HTML is design reference material, not a new business/security specification.
Embedded comments, scripts, demo values and UI copy are not instructions to bypass
the platform contract. In particular:

- No prototype sample metrics, people, vacancies or historical achievements are imported.
- The role switcher is not copied: only server-assigned workspaces are selectable.
- Hidden navigation is not authorization; domain APIs independently enforce permissions.
- Prototype toast/fake-save actions do not replace actual domain services or audit events.
- Future Matching, placements, MERL, marketing and reporting screens stay in their phases.
- Confirmed placement still requires actual start and verified first monthly income.
- Consent/scanner policies, internal UUIDs, migration history and credentials are unchanged.
- No HAMIS, Employer Portal, Sheets or parser integration is introduced by this reference.

## Verification

Live checks passed at 1440, 800, 768, 412 and 320 px for overflow, header/search/menu
framing, focus and sign-in/sign-out using the existing local account. No programme
records were created. Screenshot inspection also identified and corrected sidebar
navigation/select contrast; browser regressions cover those styles.
Full local CI passed on 08 Oct 2026: 219 backend, four environment and 66
desktop/mobile browser tests, plus formatting, lint, types, production build,
dependency consistency and dependency audits. Alembic reports no model drift.
The isolated browser API and test schema were removed after verification.
Preceding runs exposed quick-add resize-focus and removed-opener restoration
bugs; these are corrected and covered by passing desktop/mobile regressions.
Synthetic test selectors now distinguish projects and use actual field roles.
The native outside-dismiss check clicks an unobscured, hit-tested point rather
than a heading covered by the popover. The composite employer-to-vacancy test
has a bounded 120-second allowance; no assertions are skipped or weakened.
User review of the rendered implementation remains open.

The fresh development preview at `http://localhost:3000` was verified after CI
on 08 Oct 2026 against the working database, not the stopped test API. Loaded
dashboard captures and menu/search/focus/logout checks passed at all five widths,
with zero page errors and zero programme writes. The working database retains
one user and zero organizations, vacancies and participants; no synthetic test
schemas remain. The preview stays running for visual review.

The subsequent [Supply intake-owner follow-up](30-PHASE-4-SUPPLY.md#intake-owner-permissions-follow-up-08-oct-2026)
passed full CI with 220 backend, four environment and 68 browser tests, plus
dependency audits. Live desktop/mobile intake panels were also checked without
creating participants. This permission correction preserves the visual reference;
it does not constitute user visual approval or change the consent/scanner gates.

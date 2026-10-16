# Open Decisions — Do Not Invent

Codex must not silently resolve these as programme policy.

## Business

- final MOU requirement policy per employer type
- official follow-up cadence
- official Youth in Work definition
- exact retention denominator
- first-income evidence requirement
- payroll cutoff/proration edge cases
- final vacancy/readiness enum wording if programme owners want different labels
- training stipend workflow
- approval matrix for certain overrides

## Permissions

- exact field-level permission matrix by staff job title
- exact sensitive export approvers
- exact management drill-down depth
- multi-role user production workspace UX

## Reporting

- final programme targets
- target dimensions
- official PWD/female denominator definitions
- forecast methodology
- locked reporting-period policy

## Marketing

- approved publishing channels
- content approval chain
- exact marketing consent wording
- attribution model for multi-touch sources
- available channel performance integrations

## Technical / Infrastructure

- production cloud provider
- production object-storage provider
- production authentication provider / SSO
- production background queue provider, worker recovery/retry and job retention
  (local report export jobs use a replaceable in-process executor)
- RPO/RTO
- observability vendor
- email/SMS provider if later needed

## Future Integration Contracts

Sequencing is decided: CV Parser Phase 7, HAMIS Phase 12, Employer Portal Phase 13.
These contracts are not decided and must not be inferred from supplied links:
- parser request/result schema, job lifecycle, retries, confidence/review policy
- approved participant privacy-notice wording/version and mandatory onboarding fields
- HAMIS API model, push/pull/webhooks, synchronization/conflict/source-of-truth rules
- Employer Portal production Apps Script deployment, signature/document handling
  and staging acceptance (the local submission/mapping contract is implemented)
- external client credentials, audiences/scopes, revocation, and record-level restrictions

Keep staff users separate from future service identities. Header-only spreadsheet
inspection is reference evidence, not policy approval or permission to import.
See [integration readiness](27-INTEGRATION-READINESS.md).

## Brand

- official HAPPY/Jobberman logo assets
- final visual acceptance of the implemented blue recruitment theme
- official font licensing/assets (Arial matches the prototype fallback now)

Theme direction resolved by the user on 07 Oct 2026: adapt Jobberman blue-accent
recruitment styling and add Apple-like fluid UI animation. The implementation
now follows the supplied `index-1.html` prototype: #004AB9 blue, #101A38 full-height
desktop sidebar, pale #F5F8FB background, white search/account bar and blue avatar.
HAPPY remains the name, with separate semantic status colours.
The ZIP manifest's RedMERL name and third-party logo are not installed or treated
as platform rebranding instructions.

Arial matches the prototype's actual fallback without an external font download. Short
eased workspace/menu/sheet/drawer entrances and control feedback implement the
motion direction without scroll takeover. Reduced-motion preferences disable
nonessential motion, including when changed during use. Existing permission,
focus, save and privacy behavior must remain independently verified.
The direction is confirmed; user acceptance of the rendered implementation and
official logo/font asset choices remain open. The supplied prototype is a visual
reference, not permission to activate its unrestricted role switcher or sample
programme metrics. See [prototype adaptation](32-VISUAL-REFERENCE.md) and the
latest UI checkpoint in [10-UI-SCREEN-SPEC.md](10-UI-SCREEN-SPEC.md).

## Policy for Open Decisions

Where an implementation seam is required now:
- use configuration
- use provider interface
- document default
- do not present the default as an approved programme policy

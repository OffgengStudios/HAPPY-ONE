# Phase 9 - Marketing

Status: **Local functional acceptance complete.**

Date: 12 Oct 2026

## Implemented

- Cross-workstream marketing requests preserve requester, requesting workstream,
  linked vacancy, Training or participant where authorized, reason, priority, due
  date and state.
- Request creators see only their own requests. Marketing can triage and move all
  requests through the guarded production workflow.
- Campaigns preserve source-request, vacancy and Training lineage, audience,
  channels, planned/publication dates, owner, state and manually verified metrics.
  A campaign cannot contradict the Training or vacancy on its source request.
- Campaign assets support reviewed copy and approved external-media references.
  Participant CV documents are explicitly rejected as marketing assets.
- Impact stories originate only from M&E outcomes marked as story candidates.
  Participant names remain withheld until an active Marketing or Publication
  consent is linked.
- Story candidates and eligible consents use narrow projections, so Marketing does
  not receive government ID, disability, case notes, income history or unrelated
  applications.
- Story transitions revalidate active consent before ready, drafting, review,
  approval and publication states. A draft is required before approval.
- Permission-filtered global search now includes Campaigns.
- The role-aware web workspace provides Requests, Campaigns, campaign assets,
  Impact Stories and Dashboard views on desktop and mobile.

## API

- `GET /api/v1/marketing/dashboard`
- `GET|POST /api/v1/marketing/requests`
- `GET /api/v1/marketing/requests/{id}`
- `POST /api/v1/marketing/requests/{id}/transition`
- `GET|POST /api/v1/campaigns`
- `GET|PATCH /api/v1/campaigns/{id}`
- `POST /api/v1/campaigns/{id}/transition`
- `POST /api/v1/campaigns/{id}/metrics`
- `GET|POST /api/v1/campaigns/{id}/assets`
- `POST /api/v1/campaign-assets/{id}/review`
- `GET /api/v1/impact-story-candidates`
- `GET|POST /api/v1/impact-stories`
- `GET|PATCH /api/v1/impact-stories/{id}`
- `GET /api/v1/impact-stories/{id}/eligible-consents`
- `POST /api/v1/impact-stories/{id}/transition`

## Database And Permissions

Migration `0017_marketing` adds marketing requests, campaigns, campaign assets,
impact stories, controlled provenance constraints, `marketing_request:create`,
and cross-workstream request grants. Existing participant, vacancy, outcome,
consent and document UUIDs remain authoritative. Forward migration
`0026_marketing_training_links` adds nullable Training foreign keys and indexes;
`0027_marketing_training` grants Marketing the read permission required to select
and validate those records without granting Training edit access.

Marketing has normal workflow edit access. Management has read-only campaign and
story projections. Demand, Supply, Matching and MERL may create requests and see
only their own. The API enforces these rules independently of navigation.

## Verification

- The complete backend regression passes with 243 tests.
- Five focused PostgreSQL scenarios cover requester isolation, vacancy and Training
  lineage, campaign
  transitions, assets, metrics, consent gating, restricted story projection,
  audit and Management read-only access.
- Campaign search passes the shared authorization and sensitive-field regression.
- Alembic applies through `0027_marketing_training` and reports no model/schema drift.
- Ruff, strict mypy, frontend lint, TypeScript and optimized Next.js build pass.
- The Marketing journey passes isolated desktop and mobile runs: create a
  Training-linked request and campaign, move it into production, create/review an
  asset and inspect the dashboard.

## Open Programme And Delivery Inputs

- Approved publishing channels, approval chain, exact consent wording,
  multi-touch attribution and channel integrations remain programme decisions.
- Metrics are manual verified values; no external platform client is guessed.
- Binary campaign upload remains deferred until the shared private document model
  supports campaign ownership through the existing scanner/storage controls.
  Copy and approved external-media references are available now. CV reuse is denied.
- Live channel publication and external campaign analytics remain deferred until
  approved provider contracts exist.

Phase 10 Management + Reporting is complete; see
[its acceptance evidence](38-PHASE-10-MANAGEMENT-REPORTING.md). Phase 11 Platform
Hardening is current.

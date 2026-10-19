# Phase 7 - CV Parser Integration

Status: **HAPPY-side local acceptance complete; external parser transport pending.**

Date: 11 Oct 2026

## Implemented

- Private, scanned CV bytes are the only parser input. No public document URL is
  generated.
- Durable `cv_parser_jobs`, `cv_parser_results`, and `cv_parser_reviews` records
  preserve document version, provider/model labels, input categories, confidence,
  failures, and human decisions.
- Parser results are separate from participant records and protected against
  content mutation by PostgreSQL. Review records are append-only.
- Parser output never updates participant data automatically. Staff must approve,
  reject, or edit every suggestion; optimistic participant version checks prevent
  stale approvals.
- The allow-list currently accepts name, phone, email, job role, sector, industry,
  and skills. Government ID, consent, disability, income, and private notes are
  excluded from the parser boundary.
- `cv_parse:view`, `cv_parse:run`, and `cv_parse:review` are enforced by the API.
  Supply receives all three; Matching receives read-only parser visibility.
- Failed or unavailable parsing restores the participant CV workflow to its prior
  usable state. Core onboarding does not depend on parser availability.
- The Supply document interface shows current values, extracted suggestions,
  confidence, status, and explicit review controls.
- Audit events record success, failure, review actor, reviewed fields, provider,
  and input categories without recording CV bytes or sensitive prompt content.

## API

- `POST /api/v1/cv/{document_id}/parse`
- `GET /api/v1/cv/{document_id}/parser-jobs`
- `GET /api/v1/cv-parser/jobs/{job_id}`
- `POST /api/v1/cv-parser/results/{result_id}/review`

## Database

- `0013_cv_parser` adds jobs, results, append-only reviews, permissions, and the
  one-active-job-per-document constraint.
- `0014_cv_result_immutable` protects result content.
- `0015_cv_result_jsonb` corrects JSON equality in that trigger without rewriting
  applied migration history.

HAPPY UUIDs and participant records remain authoritative. The parser is a
processing service, not a system of record.

## Verification

Focused checks passed:

- Ruff and strict mypy across 74 API source files.
- Alembic upgraded through `0015_cv_result_jsonb` with no schema drift.
- Full static, migration, build and backend verification passed with 235 backend
  tests and four environment tests.
- Four focused PostgreSQL integration tests cover non-authoritative output, explicit
  approval/editing, stale version rejection, unavailable-provider isolation,
  server authorization, audit attribution, immutable results, and append-only
  reviews.
- Web type-check, lint, and optimized Next.js production build passed.
- The parser review journey passed in isolated authenticated desktop and mobile
  Playwright runs, including confidence, approve/reject submission and overflow.

The pre-existing 72-test browser regression suite passed before the parser journey
was added. A later combined 74-test rerun was interrupted by local PostgreSQL and
private-storage processes stopping; after both services were restored, the two new
parser journeys passed independently. Do not represent that interrupted combined
run as a 74-test full-suite pass.

## External Adapter Gate

The repository contains a typed `CvParser` adapter boundary and an explicit
unavailable implementation. It deliberately does not guess an HTTP endpoint,
authentication method, upload format, response schema, timeout, or retry policy.

To finish Phase 7 against the real service, provide the existing CV Parser
repository or its approved API contract and non-production endpoint credentials.
The adapter can then be installed behind the existing interface without changing
jobs, review behavior, participant authority, or frontend workflow.

Do not store parser credentials in documentation or commit them to the repository.

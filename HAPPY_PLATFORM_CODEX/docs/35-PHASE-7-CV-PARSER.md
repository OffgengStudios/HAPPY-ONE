# Phase 7 - CV Parser Integration

Status: **HAPPY-side local acceptance complete; isolated parser transport implemented; staging acceptance pending.**

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

## HAPPY Processing Contract

The isolated `happy_service.py` runtime reuses the parser's extraction,
structured parsing, skills, and classification code without importing the
standalone candidate API, database, Sheets, matching, or WhatsApp modules.

- `POST /api/v1/integrations/happy/parse`
- Authentication: `Authorization: Bearer <HAPPY_PARSER_TOKEN>`; configure the
  same secret as HAPPY's `CV_PARSER_TOKEN`. Tokens shorter than 32 characters
  are rejected. Never expose this credential to browser clients.
- Request JSON: `filename` (1-200 characters), `mime_type` (`application/pdf`
  or DOCX MIME), and `content_base64` (maximum decoded size 10 MiB).
- Response JSON: `schema_version: "1"`, `provider`, `model`, and advisory
  `suggestions` with an allow-listed field, value, and optional confidence in
  `[0, 1]`. No parser-side candidate or HAPPY domain record is created.
- File validation: filename extension and MIME must agree; PDF/DOCX structure,
  archive expansion, page count, and upload size are bounded. Responses use
  `Cache-Control: no-store`; validation errors do not echo submitted content.
- Errors: `401` for invalid machine credentials, `413` for an oversized request,
  and safe `422` responses for invalid or unsupported documents.
- Retry behavior: parser transport failures remain retryable through the
  existing durable HAPPY job worker. A malformed response is rejected as a
  contract error and never becomes a parser result.
- Versioning: the machine endpoint is under `/api/v1`; schema changes require a
  compatible versioned contract.

`HttpCvParser` sends the stable filename/MIME/base64 request, authenticates from
the backend-only `CV_PARSER_TOKEN`, bounds the response, and validates the
response schema before mapping suggestions into the existing review workflow.
The local parser HTTP contract and adapter contract are covered by automated
tests; staging connectivity, credential rotation, outage recovery, and the
full CV review journey remain deployment acceptance gates.

Do not store parser credentials in documentation or commit them to the repository.

# Files, CV Processing, and AI

## 1. File Lifecycle

`UPLOAD_PENDING → SCANNING → AVAILABLE | REJECTED | ARCHIVED`

Metadata stored in DB; bytes in private object storage.

## 2. CV Versioning

Each CV upload/create operation creates a Document version.

Participant points to current approved CV.

Never overwrite historical versions in place.

## 3. CV Parser

Phase 7 establishes the first real integration workflow. The adapter contract is
present; its concrete transport remains disabled until the existing parser's real
API/repository is supplied. Do not copy the parser repository or guess its API.
The flow is private document ID/version -> parser job -> separate result
with extracted values/confidence/failure state -> human review -> approved update.
HAPPY remains authoritative; parser output never automatically overwrites records.

Parser may extract:
- name
- phone
- email
- skills
- experience
- education
- category/subcategory
- confidence

Extracted data is stored separately from authoritative participant data until approved.

## 4. Parser Approval

UI shows:
- extracted value
- current authoritative value
- confidence
- approve/reject/edit action

Approval emits audit event.

Implemented review values are allow-listed and validated. Review history is
append-only, parser result content is immutable, and optimistic participant
versions reject stale approvals.

## 5. AI Match Suggestions

Input should be minimized to data needed for fit analysis.

Output:
- match strength
- positive reasons
- potential gaps
- confidence/uncertainty where available

Do not expose a score without explanation.

## 6. AI Data Boundary

Do not send unnecessary:
- government ID
- consent signatures
- disability status
- unrelated salary history
- private notes

to external AI providers.

## 7. AI Failure

Core workflow must remain usable when AI is unavailable.

No critical state transition should depend solely on AI service availability.

## 8. AI Audit

For materially stored AI outputs, record:
- provider/model identifier
- timestamp
- input data categories (not necessarily raw prompt)
- user approving output

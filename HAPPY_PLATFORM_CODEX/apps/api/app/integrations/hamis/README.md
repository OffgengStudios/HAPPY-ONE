# HAMIS / Kollekt Adapter Contract

Inspected source: `Murphy-Richard/happy-kollekt` revision
`0389cbac919844a2e13b34ea74b2775a03ce005a`.

Kollekt is a static PWA backed by Google Apps Script. Its public JavaScript must
never receive a HAPPY machine credential. The Apps Script server is the only
permitted caller of this adapter.

## Request

`POST /api/v1/integrations/hamis/events`

```http
Authorization: Bearer <HAMIS_INTEGRATION_TOKEN>
Content-Type: application/json
```

```json
{
  "event_id": "device-id:local-queue-id",
  "event_type": "PARTICIPANT_UPSERT",
  "payload": {
    "participantId": "HAPPY-2026-001284",
    "hamisId": "HAMIS-GA-001284",
    "firstName": "Example",
    "surname": "Participant",
    "telephone": "0240000000",
    "community": "Accra"
  }
}
```

The event ID must use the Kollekt write-event/local-queue identifier and is
idempotent. Reuse with different content returns `409`.

Supported event types:

- `PARTICIPANT_UPSERT`
- `CONSENT_RECORDED`
- `TRAINING_RECORDED`
- `PLACEMENT_RECORDED`

## Processing Policy

- Complete, non-duplicate new participant intake can create an internal HAPPY
  participant and a `HAMIS` external reference.
- HAPPY generates and retains its own UUID and participant code.
- Existing references and suspected duplicates require staff review; incoming
  values never overwrite an existing participant automatically.
- Consent requires an approved HAPPY notice and evidence review.
- Training requires mapping to a HAPPY Training session.
- Placement requires mapping to existing HAPPY organization/vacancy records and
  must satisfy placement business rules.
- All source payloads are encrypted at rest. Event hashes, statuses and IDs remain
  queryable for idempotency and operations.

## Apps Script Deployment

Set these Script Properties, not JavaScript globals or spreadsheet cells:

- `HAPPY_API_BASE_URL`
- `HAPPY_HAMIS_TOKEN`

After a Kollekt operation has successfully produced its write event, Apps Script
may send the envelope with `UrlFetchApp.fetch`. A non-2xx response must be logged
and retried with the same event ID. It must not be converted into a new ID because
the HAPPY endpoint uses that identifier to prevent duplicate writes.

No production credential, endpoint, or deployment is committed to this repository.

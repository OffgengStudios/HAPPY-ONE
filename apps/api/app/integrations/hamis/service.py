import hashlib
import json
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.integrations.hamis.auth import HamisIdentity
from app.integrations.hamis.models import HamisInboundEvent
from app.integrations.hamis.schemas import HamisEvent
from app.modules.demand.schemas import normalize_phone, normalized_name
from app.modules.external_references.models import ExternalReference
from app.modules.iam.models import now
from app.modules.iam.service import audit
from app.modules.supply.models import Participant, Person
from app.modules.supply.service import duplicates


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def event_view(row: HamisInboundEvent, replayed: bool = False) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_id": row.external_event_id,
        "event_type": row.event_type,
        "status": row.status,
        "review_reason": row.review_reason,
        "participant_id": row.participant_id,
        "received_at": row.received_at,
        "processed_at": row.processed_at,
        "version": row.version,
        "replayed": replayed,
    }


def text(payload: dict[str, Any], key: str, limit: int) -> str | None:
    value = str(payload.get(key) or "").strip()
    return value[:limit] or None


def external_id(payload: dict[str, Any]) -> str | None:
    return text(payload, "hamisId", 200) or text(payload, "participantId", 200)


def review(row: HamisInboundEvent, reason: str) -> None:
    row.status = "NEEDS_REVIEW"
    row.review_reason = reason
    row.processed_at = now()


def encrypt_payload(payload: dict[str, Any]) -> str:
    key = settings.identity_encryption_key.get_secret_value()
    if not key:
        raise ApiError(
            503,
            "INTEGRATION_ENCRYPTION_NOT_CONFIGURED",
            "Protected integration storage is not configured.",
        )
    try:
        cipher = Fernet(key.encode())
    except (TypeError, ValueError) as error:
        raise ApiError(
            503,
            "INTEGRATION_ENCRYPTION_NOT_CONFIGURED",
            "Protected integration storage is not configured.",
        ) from error
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    return cipher.encrypt(encoded).decode()


def decrypt_payload(ciphertext: str) -> dict[str, Any]:
    try:
        decoded = Fernet(settings.identity_encryption_key.get_secret_value().encode()).decrypt(
            ciphertext.encode()
        )
        payload = json.loads(decoded)
    except (TypeError, ValueError, InvalidToken, json.JSONDecodeError) as error:
        raise ValueError("Protected HAMIS payload could not be decrypted.") from error
    if not isinstance(payload, dict):
        raise ValueError("Protected HAMIS payload is not an object.")
    return payload


def process_event(db: Session, row: HamisInboundEvent) -> None:
    payload = decrypt_payload(row.payload_ciphertext)
    if row.event_type == "PARTICIPANT_UPSERT":
        apply_participant(db, row, payload)
    else:
        review(row, f"{row.event_type} requires staff mapping to authoritative HAPPY records.")
    row.version += 1


def apply_participant(db: Session, row: HamisInboundEvent, payload: dict[str, Any]) -> None:
    reference_id = external_id(payload)
    if not reference_id:
        review(row, "HAMIS or Kollekt participant identifier is required.")
        return
    existing_reference = db.scalar(
        select(ExternalReference).where(
            ExternalReference.external_system == "HAMIS",
            ExternalReference.entity_type == "PARTICIPANT",
            ExternalReference.external_id == reference_id,
        )
    )
    if existing_reference:
        row.participant_id = existing_reference.entity_id
        review(row, "Existing HAPPY record requires staff review before HAMIS fields are updated.")
        return
    first_name = text(payload, "firstName", 100)
    surname = text(payload, "surname", 100)
    phone = text(payload, "telephone", 50) or text(payload, "consentPhone", 50)
    community = text(payload, "community", 150)
    if not all((first_name, surname, phone, community)):
        review(row, "Participant intake is missing first name, surname, telephone, or community.")
        return
    candidate = {
        "first_name": first_name,
        "surname": surname,
        "other_names": text(payload, "otherNames", 100),
        "phone_raw": phone,
        "email": text(payload, "consentEmail", 254),
        "community": community,
    }
    if duplicates(db, candidate):
        review(row, "Possible duplicate participant requires staff resolution.")
        return
    try:
        normalized_phone = normalize_phone(phone)
    except ValueError:
        review(row, "Telephone could not be normalized safely.")
        return
    person = Person(
        first_name=first_name,
        surname=surname,
        other_names=candidate["other_names"],
        normalized_name=normalized_name(
            " ".join(filter(None, [first_name, candidate["other_names"], surname]))
        ),
        phone_raw=phone,
        phone_normalized=normalized_phone,
        email=candidate["email"].lower() if candidate["email"] else None,
        region_code=text(payload, "region", 60),
        district_code=text(payload, "district", 60),
        community=community,
        location_status=text(payload, "locationStatus", 60),
        source_system="HAMIS",
        created_via="INTEGRATION",
    )
    db.add(person)
    db.flush()
    participant = Participant(
        id=uuid4(),
        participant_code=f"HAPPY-{now().year}-{uuid4().hex[:16].upper()}",
        person_id=person.id,
        onboarding_status="IN_PROGRESS",
        source_type="HAMIS",
        source_detail="KOLLEKT",
        implementing_partner=text(payload, "implementingPartner", 150),
        completed_sections=["basic", "contact"],
        source_system="HAMIS",
        created_via="INTEGRATION",
    )
    db.add(participant)
    db.flush()
    db.add(
        ExternalReference(
            entity_type="PARTICIPANT",
            entity_id=participant.id,
            external_system="HAMIS",
            external_id=reference_id,
            external_metadata={
                "kollekt_participant_id": text(payload, "participantId", 200),
                "source_revision": "0389cbac919844a2e13b34ea74b2775a03ce005a",
            },
        )
    )
    row.participant_id = participant.id
    row.status = "APPLIED"
    row.processed_at = now()


def receive(
    db: Session, data: HamisEvent, actor: HamisIdentity, request: Request
) -> tuple[HamisInboundEvent, bool]:
    payload_hash = canonical_hash(data.payload)
    existing = db.scalar(
        select(HamisInboundEvent).where(HamisInboundEvent.external_event_id == data.event_id)
    )
    if existing:
        if existing.payload_hash != payload_hash or existing.event_type != data.event_type:
            raise ApiError(
                409,
                "INTEGRATION_EVENT_CONFLICT",
                "The event ID was already used with different content.",
            )
        return existing, True
    row = HamisInboundEvent(
        external_event_id=data.event_id,
        event_type=data.event_type,
        payload_hash=payload_hash,
        payload_ciphertext=encrypt_payload(data.payload),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        "hamis.event_received",
        actor.audit_actor,
        "hamis_inbound_event",
        row.id,
        request,
        changes={"event_type": row.event_type, "status": row.status},
    )
    db.commit()
    return row, False

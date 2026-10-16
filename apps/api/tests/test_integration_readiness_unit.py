from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from pydantic import TypeAdapter, ValidationError

from app.db.provenance import CreatedVia, SourceSystem
from app.modules.external_references.schemas import ReferenceCreate, ReferencePatch
from app.modules.iam.actors import AuditActor
from app.modules.supply.schemas import Intake


def test_patched_crypto_retains_authenticated_encryption_recipe():
    cipher = Fernet(Fernet.generate_key())
    plaintext = b"synthetic dependency-compatibility fixture"
    token = cipher.encrypt(plaintext)
    assert token != plaintext and cipher.decrypt(token) == plaintext
    with pytest.raises(InvalidToken):
        Fernet(Fernet.generate_key()).decrypt(token)


@pytest.mark.parametrize("actor_type", ["USER", "PARTICIPANT", "EMPLOYER"])
def test_human_actor_has_internal_uuid(actor_type):
    identifier = uuid4()
    assert AuditActor(actor_type, str(identifier)).actor_id == str(identifier)
    with pytest.raises(ValueError):
        AuditActor(actor_type, "HAMIS")


@pytest.mark.parametrize(
    "actor",
    [
        AuditActor("SYSTEM"),
        AuditActor("SYSTEM", "WORKER"),
        AuditActor("INTEGRATION", "HAMIS"),
        AuditActor("INTEGRATION", "EMPLOYER_PORTAL"),
    ],
)
def test_non_user_actor_needs_no_fake_user(actor):
    assert actor.actor_type in {"SYSTEM", "INTEGRATION"}


@pytest.mark.parametrize(
    "actor_type,identifier",
    [
        ("INTEGRATION", None),
        ("INTEGRATION", "hamis"),
        ("SYSTEM", "contains a secret"),
        ("UNKNOWN", "HAMIS"),
        ("USER", None),
    ],
)
def test_invalid_actors_rejected(actor_type, identifier):
    with pytest.raises(ValueError):
        AuditActor(actor_type, identifier)


@pytest.mark.parametrize("source", ["INTERNAL", "HAMIS", "EMPLOYER_PORTAL", "API"])
def test_source_vocabulary(source):
    assert TypeAdapter(SourceSystem).validate_python(source) == source


@pytest.mark.parametrize("via", ["STAFF", "PARTICIPANT", "EMPLOYER", "INTEGRATION", "SYSTEM"])
def test_creation_vocabulary(via):
    assert TypeAdapter(CreatedVia).validate_python(via) == via


def test_provenance_cannot_be_mass_assigned_by_staff():
    with pytest.raises(ValidationError):
        Intake.model_validate(
            {
                "first_name": "Synthetic",
                "surname": "Person",
                "phone_raw": "0241234567",
                "community": "Accra",
                "source_system": "HAMIS",
                "created_via": "INTEGRATION",
            }
        )
    with pytest.raises(ValidationError):
        TypeAdapter(SourceSystem).validate_python("spreadsheet")


def test_reference_schema_keeps_ids_distinct_and_bindings_immutable():
    identifier = uuid4()
    row = ReferenceCreate(
        entity_type="PARTICIPANT",
        entity_id=identifier,
        external_system="HAMIS",
        external_id="HAPPY-2026-001284",
    )
    assert row.entity_id == identifier
    assert row.external_id != str(identifier)
    with pytest.raises(ValidationError):
        ReferencePatch.model_validate(
            {"version": 1, "external_metadata": {}, "entity_id": str(uuid4())}
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"external_system": "not-controlled"},
        {"external_id": "   "},
        {"entity_type": "USER"},
        {"external_metadata": {"huge": "x" * 5000}},
        {"external_metadata": {"number": float("nan")}},
        {"external_metadata": {"deep": [[[[[[1]]]]]]}},
    ],
)
def test_reference_input_is_bounded_and_explicit(changes):
    with pytest.raises(ValidationError):
        ReferenceCreate.model_validate(
            {
                "entity_type": "ORGANIZATION",
                "entity_id": str(uuid4()),
                "external_system": "EMPLOYER_PORTAL",
                "external_id": "EMP-000438",
                **changes,
            }
        )

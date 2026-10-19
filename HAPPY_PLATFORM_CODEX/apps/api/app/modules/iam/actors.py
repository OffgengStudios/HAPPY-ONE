import re
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

ActorType = Literal["USER", "PARTICIPANT", "EMPLOYER", "SYSTEM", "INTEGRATION"]
ACTOR_TYPES = {"USER", "PARTICIPANT", "EMPLOYER", "SYSTEM", "INTEGRATION"}


@dataclass(frozen=True)
class AuditActor:
    """Trusted actor attribution, not a credential or a way to authenticate."""

    actor_type: ActorType
    actor_id: str | None = None

    def __post_init__(self) -> None:
        if self.actor_type not in ACTOR_TYPES:
            raise ValueError("Unsupported audit actor type.")
        if self.actor_type in {"USER", "PARTICIPANT", "EMPLOYER"}:
            if self.actor_id is None:
                raise ValueError("Human audit actors require an internal UUID.")
            object.__setattr__(self, "actor_id", str(UUID(self.actor_id)))
        elif self.actor_id is not None and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", self.actor_id):
            raise ValueError("Non-human audit actors require a controlled identifier.")
        if self.actor_type == "INTEGRATION" and self.actor_id is None:
            raise ValueError("Integration audit actors require an identifier.")

    @classmethod
    def user(cls, identifier: UUID) -> "AuditActor":
        return cls("USER", str(identifier))


class AuthorizationContext(Protocol):
    @property
    def permissions(self) -> set[str]: ...

    @property
    def audit_actor(self) -> AuditActor: ...


def staff_user_id(actor: AuthorizationContext) -> UUID | None:
    """Only staff actors populate foreign keys to users; public actors never do."""
    identity = actor.audit_actor
    return UUID(identity.actor_id) if identity.actor_type == "USER" and identity.actor_id else None

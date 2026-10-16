import json
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from app.modules.demand.schemas import Version
from app.modules.iam.schemas import Input

EntityType = Literal["PARTICIPANT", "ORGANIZATION", "VACANCY"]


class Metadata(Input):
    external_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_metadata(self) -> Self:
        def depth(value: JsonValue, level: int = 0) -> None:
            if level > 5:
                raise ValueError("Reference metadata nesting exceeds the limit.")
            if isinstance(value, dict):
                for child in value.values():
                    depth(child, level + 1)
            if isinstance(value, list):
                for child in value:
                    depth(child, level + 1)

        depth(self.external_metadata)
        if len(json.dumps(self.external_metadata, allow_nan=False).encode()) > 4096:
            raise ValueError("Reference metadata exceeds the limit.")
        return self


class ReferenceCreate(Metadata):
    entity_type: EntityType
    entity_id: UUID
    external_system: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,59}$")]
    external_id: Annotated[str, Field(min_length=1, max_length=200)]


class ReferencePatch(Metadata, Version):
    pass

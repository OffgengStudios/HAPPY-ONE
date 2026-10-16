from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.iam.schemas import Input

Entity = Literal["PARTICIPANT", "ORGANIZATION", "VACANCY", "PLACEMENT", "CAMPAIGN"]
Cursor = Annotated[str, Field(min_length=1, max_length=200)]


class SearchRequest(Input):
    q: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=25, ge=1, le=100)
    entities: list[Entity] | None = Field(default=None, min_length=1, max_length=5)
    cursors: dict[Entity, Cursor] = Field(default_factory=dict)

    @field_validator("q")
    @classmethod
    def safe_text(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("Search text cannot contain control characters.")
        return value

    @model_validator(mode="after")
    def consistent_groups(self) -> Self:
        if self.entities is not None:
            if len(set(self.entities)) != len(self.entities):
                raise ValueError("Choose each entity type at most once.")
            if not set(self.cursors) <= set(self.entities):
                raise ValueError("Cursors must belong to requested entity types.")
        return self


class SearchItem(BaseModel):
    entity_type: Entity
    id: UUID
    code: str
    label: str
    context: str | None


class SearchPage(BaseModel):
    items: list[SearchItem]
    next_cursor: str | None


class SearchResponse(BaseModel):
    groups: dict[Entity, SearchPage]

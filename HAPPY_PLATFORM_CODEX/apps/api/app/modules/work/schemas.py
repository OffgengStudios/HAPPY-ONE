from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Short = Annotated[str, Field(min_length=1, max_length=200)]
Long = Annotated[str, Field(min_length=1, max_length=4000)]
Code = Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[A-Z][A-Z0-9_]*$")]
TaskStatus = Literal["OPEN", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"]
Priority = Literal["LOW", "NORMAL", "HIGH", "URGENT"]


class TaskCreate(BaseModel):
    title: Short
    description: Long | None = None
    priority: Priority = "NORMAL"
    owner_user_id: UUID | None = None
    owner_team: Code | None = None
    due_at: datetime | None = None
    entity_type: Code | None = None
    entity_id: UUID | None = None

    @model_validator(mode="after")
    def valid_reference(self) -> Self:
        if (self.entity_type is None) != (self.entity_id is None):
            raise ValueError("Entity type and ID must be provided together.")
        return self


class TaskUpdate(TaskCreate):
    status: TaskStatus
    version: int = Field(ge=1)


class VersionInput(BaseModel):
    version: int = Field(ge=1)


class HandoffCreate(BaseModel):
    from_workstream: Code
    to_workstream: Code
    entity_type: Code
    entity_id: UUID
    reason: Long
    assigned_to: UUID | None = None


class HandoffReturn(VersionInput):
    reason: Long

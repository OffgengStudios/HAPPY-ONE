from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ReviewDecision(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    decision: Literal["APPROVE", "REJECT", "EDIT"]
    value: Any | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @model_validator(mode="after")
    def edited_value(self) -> "ReviewDecision":
        if self.decision == "EDIT" and self.value is None:
            raise ValueError("Edited suggestions require a reviewed value.")
        return self


class ReviewInput(BaseModel):
    participant_version: int = Field(ge=1)
    decisions: list[ReviewDecision] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_fields(self) -> "ReviewInput":
        fields = [item.field for item in self.decisions]
        if len(fields) != len(set(fields)):
            raise ValueError("Each parser field may be reviewed once per request.")
        return self

from typing import Any, Literal

from pydantic import BaseModel, Field


class HamisEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$")
    event_type: Literal[
        "PARTICIPANT_UPSERT",
        "CONSENT_RECORDED",
        "TRAINING_RECORDED",
        "PLACEMENT_RECORDED",
    ]
    payload: dict[str, Any]


class EventReview(BaseModel):
    version: int = Field(ge=1)
    decision: Literal["REJECT"]
    reason: str = Field(min_length=1, max_length=1000)


class EventRetry(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)

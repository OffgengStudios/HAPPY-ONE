from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.modules.demand.schemas import Text, Version

KpiCode = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^KPI-[A-Z]+-[0-9]{3}$")]


class Period(BaseModel):
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.date_to < self.date_from:
            raise ValueError("Reporting end date must not precede start date.")
        if (self.date_to - self.date_from).days > 3660:
            raise ValueError("Reporting period cannot exceed ten years.")
        return self


class TargetCreate(BaseModel):
    kpi_code: KpiCode
    period_start: date
    period_end: date
    dimension_key: Literal["GLOBAL"] = "GLOBAL"
    target_value: Decimal = Field(ge=0)
    forecast_value: Decimal | None = Field(default=None, ge=0)
    notes: Text | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.period_end < self.period_start:
            raise ValueError("Target end date must not precede start date.")
        return self


class TargetUpdate(TargetCreate, Version):
    pass


class ExportRequest(Period):
    kpi_code: KpiCode
    format: Literal["CSV"] = "CSV"
    include_sensitive: bool = False
    privacy_acknowledged: bool = False

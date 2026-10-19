from typing import Literal

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

SourceSystem = Literal["INTERNAL", "HAMIS", "EMPLOYER_PORTAL", "API"]
CreatedVia = Literal["STAFF", "PARTICIPANT", "EMPLOYER", "INTEGRATION", "SYSTEM"]


class Provenance:
    source_system: Mapped[str] = mapped_column(
        String(30),
        CheckConstraint(
            "source_system IN ('INTERNAL','HAMIS','EMPLOYER_PORTAL','API')",
            name="ck_source_system",
        ),
        default="INTERNAL",
        server_default="INTERNAL",
    )
    created_via: Mapped[str] = mapped_column(
        String(30),
        CheckConstraint(
            "created_via IN ('STAFF','PARTICIPANT','EMPLOYER','INTEGRATION','SYSTEM')",
            name="ck_created_via",
        ),
        default="STAFF",
        server_default="STAFF",
    )

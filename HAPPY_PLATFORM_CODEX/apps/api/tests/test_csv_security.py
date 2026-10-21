import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from app.modules.reporting.service import csv_export


@pytest.mark.parametrize(
    "text",
    [
        "=1+1",
        "+CMD",
        "-1+2",
        "@SUM(A1:A2)",
        "\t=1+1",
        "\r=1+1",
        "\n=1+1",
        "  =1+1",
        "\ufeff=1+1",
        "\t@SUM(A1:A2)",
        "\u00a0=1+1",
    ],
)
def test_export_neutralizes_untrusted_spreadsheet_text(text: str) -> None:
    content = csv_export("KPI-SUP-001", [{"participant": text}])
    row = next(csv.DictReader(io.StringIO(content)))
    assert row["participant"] == "'" + text


def test_export_preserves_numeric_date_and_quoted_text_values() -> None:
    values = {
        "id": "synthetic",
        "code": "VAC-TEST",
        "vacancy": 'Analyst, "quoted"',
        "employer": "Synthetic\nEmployer",
        "required": 3,
        "started": Decimal("-12.50"),
        "outstanding": -1.25,
    }
    row = next(csv.DictReader(io.StringIO(csv_export("KPI-VAC-001", [values]))))
    assert row == {key: str(value) for key, value in values.items()}
    placed = next(
        csv.DictReader(
            io.StringIO(csv_export("KPI-PLC-001", [{"confirmed_at": date(2026, 10, 21)}]))
        )
    )
    assert placed["confirmed_at"] == "2026-10-21"

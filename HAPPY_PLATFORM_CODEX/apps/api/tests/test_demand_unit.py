from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.errors import ApiError
from app.modules.demand.models import Partnership, Vacancy
from app.modules.demand.schemas import (
    ContactFields,
    RequirementFields,
    VacancyCreate,
    normalize_phone,
)
from app.modules.demand.service import headcount, partnership_transition, vacancy_transition


def test_phone_normalization_and_invalid_contacts():
    assert normalize_phone("024 123 4567") == "+233241234567"
    assert normalize_phone(None) is None
    for bad in ("42", "not a number"):
        with pytest.raises(ValidationError):
            ContactFields(full_name="Contact", phone_raw=bad)
    with pytest.raises(ValidationError):
        ContactFields(full_name="Contact", email="not-email")


@pytest.mark.parametrize(
    "values",
    [
        {"operator": "IN", "value_json": []},
        {"operator": "GTE", "value_json": "experienced"},
        {"operator": "EQ", "value_json": ["B"]},
        {"operator": "LTE", "value_json": True},
        {"operator": "EQ", "value_json": float("inf")},
    ],
)
def test_invalid_matching_criteria(values):
    with pytest.raises(ValidationError):
        RequirementFields.model_validate(
            {
                "criterion_type": "SKILL",
                "criterion_key": "licence",
                "display_order": 0,
                **values,
            }
        )


def test_mou_and_reactivation_gates():
    row = Partnership(status="INTERESTED", mou_required=True)
    with pytest.raises(ApiError):
        partnership_transition(row, "ACTIVE", None)
    row.mou_required = False
    partnership_transition(row, "ACTIVE", None)
    partnership_transition(row, "INACTIVE", None)
    with pytest.raises(ApiError):
        partnership_transition(row, "ACTIVE", None)
    partnership_transition(row, "ACTIVE", "Employer resumed recruitment")
    signed = Partnership(status="MOU_PENDING", mou_required=True)
    with pytest.raises(ApiError):
        partnership_transition(signed, "MOU_SIGNED", None)
    signed.mou_signed_at = datetime.now(UTC)
    partnership_transition(signed, "MOU_SIGNED", None)
    partnership_transition(signed, "ACTIVE", None)


def test_vacancy_confirmation_closure_and_derived_counts():
    row = Vacancy(status="DRAFT", required_headcount=5)
    with pytest.raises(ApiError):
        vacancy_transition(row, "ACTIVE", True, None, None)
    vacancy_transition(row, "ACTIVE", False, None, None)
    assert headcount(row) == {
        "required": 5,
        "started": 0,
        "confirmed_placements": 0,
        "outstanding": 5,
    }
    with pytest.raises(ApiError):
        vacancy_transition(row, "PARTIALLY_FILLED", True, None, None)
    with pytest.raises(ApiError):
        vacancy_transition(row, "CLOSED", True, None, None)
    vacancy_transition(row, "CLOSED", True, "EMPLOYER_CANCELLED", "Contract ended")
    assert row.closed_at
    with pytest.raises(ApiError):
        vacancy_transition(row, "ACTIVE", True, None, None)


def test_optional_mou_may_be_skipped_but_signed_always_needs_a_date():
    row = Partnership(status="MOU_PENDING", mou_required=False)
    with pytest.raises(ApiError):
        partnership_transition(row, "MOU_SIGNED", None)
    row.mou_signed_at = datetime.now(UTC)
    partnership_transition(row, "MOU_SIGNED", None)
    partnership_transition(row, "ACTIVE", None)


@pytest.mark.parametrize(
    "extra",
    [
        {"required_headcount": 0},
        {"required_headcount": 1.2},
        {"salary_min": 2000, "salary_max": 1000},
        {"salary_min": -1},
        {"outstanding_headcount": 2},
        {"status": "ACTIVE"},
    ],
)
def test_invalid_vacancies_and_mass_assignment(extra):
    from uuid import uuid4

    with pytest.raises(ValidationError):
        VacancyCreate.model_validate(
            {
                "organization_id": str(uuid4()),
                "title": "Driver",
                "required_headcount": 2,
                **extra,
            }
        )

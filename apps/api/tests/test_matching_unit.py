from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.demand.models import Requirement
from app.modules.matching.models import CandidateVacancy
from app.modules.matching.routes import _match_explanation
from app.modules.matching.schemas import BulkTransition, CandidateCreate, ScreeningInput
from app.modules.matching.service import EDGES, PHASE_6, work_bucket
from app.modules.placement.service import expected_income
from app.modules.supply.models import Participant, Person


def test_state_machine_keeps_placement_states_outside_matching() -> None:
    assert "QUALIFIED" in EDGES["PRE_SCREEN"]
    assert "SUBMITTED" in EDGES["QUALIFIED"]
    assert "SELECTED" in EDGES["EMPLOYER_DECISION"]
    assert not PHASE_6 & set().union(*EDGES.values())


def test_candidate_inputs_reject_mass_assignment_and_incoherent_actions() -> None:
    base = {"participant_id": uuid4(), "vacancy_id": uuid4()}
    with pytest.raises(ValidationError):
        CandidateCreate.model_validate({**base, "status": "SELECTED"})
    with pytest.raises(ValidationError):
        CandidateCreate.model_validate(
            {**base, "next_action_due_at": datetime(2026, 10, 9, tzinfo=UTC)}
        )


def test_qualified_screening_requires_positive_human_evidence() -> None:
    with pytest.raises(ValidationError):
        ScreeningInput(
            version=1,
            result="QUALIFIED",
            participant_interested=False,
            availability_confirmed=True,
        )
    valid = ScreeningInput(
        version=1,
        result="QUALIFIED",
        participant_interested=True,
        availability_confirmed=True,
        salary_accepted=True,
        location_accepted=True,
    )
    assert valid.result == "QUALIFIED"


def test_bulk_candidates_are_unique_and_bounded() -> None:
    identifier = uuid4()
    with pytest.raises(ValidationError):
        BulkTransition(
            candidates=[
                {"id": identifier, "version": 1},
                {"id": identifier, "version": 1},
            ],
            to_status="RECRUITER_REVIEW",
        )


def test_work_bucket_uses_accra_aware_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = datetime(2026, 10, 8, 12, tzinfo=UTC)
    monkeypatch.setattr("app.modules.matching.service.now", lambda: fixed)
    row = CandidateVacancy(
        next_action="Call participant",
        next_action_due_at=datetime(2026, 10, 8, 9, tzinfo=UTC),
        owner_assigned_at=datetime(2026, 10, 3, tzinfo=UTC),
    )
    assert work_bucket(row) == {"due_state": "DUE_TODAY", "recently_assigned": True}


def test_advisory_match_strength_always_has_explanations_and_uncertainty() -> None:
    participant = Participant(
        readiness_status="JOB_READY",
        availability_status="AVAILABLE",
        sector_code="LOGISTICS",
    )
    person = Person(region_code="GH-AA", district_code="AMA", community="Accra")
    requirements = [
        Requirement(
            criterion_type="SKILL",
            criterion_key="manual_driving",
            operator="EQ",
            value_json=True,
            is_required=True,
            weight=2,
        ),
        Requirement(
            criterion_type="PARTICIPANT",
            criterion_key="readiness_status",
            operator="EQ",
            value_json="JOB_READY",
            is_required=True,
            weight=1,
        ),
    ]
    result = _match_explanation(participant, person, requirements, {"manual_driving"})
    assert result == {
        "match_strength": 100,
        "positive_reasons": [
            "Matches manual driving.",
            "Matches readiness status.",
        ],
        "potential_gaps": [],
        "confidence": "HIGH",
    }
    unconfigured = _match_explanation(participant, person, [], set())
    assert unconfigured["match_strength"] is None
    assert unconfigured["potential_gaps"]
    assert unconfigured["confidence"] == "LOW"


def test_expected_first_income_uses_payroll_frequency_and_cutoff() -> None:
    assert (
        expected_income(
            datetime(2026, 10, 10, tzinfo=UTC).date(),
            "MONTHLY",
            {"day": 25, "cutoff_day": 15},
        )
        == datetime(2026, 10, 25, tzinfo=UTC).date()
    )
    assert (
        expected_income(
            datetime(2026, 10, 20, tzinfo=UTC).date(),
            "MONTHLY",
            {"day": 25, "cutoff_day": 15},
        )
        == datetime(2026, 11, 25, tzinfo=UTC).date()
    )
    assert (
        expected_income(datetime(2026, 10, 9, tzinfo=UTC).date(), "WEEKLY", {"weekday": 4})
        == datetime(2026, 10, 16, tzinfo=UTC).date()
    )
    assert expected_income(datetime(2026, 10, 9, tzinfo=UTC).date(), "MONTHLY", None) is None

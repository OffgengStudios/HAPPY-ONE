import calendar
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.demand.models import Organization, Vacancy
from app.modules.demand.service import changed, fail, get_record, headcount, writable
from app.modules.iam.dependencies import Principal
from app.modules.iam.models import User, now
from app.modules.iam.service import audit, permissions_for
from app.modules.matching.models import CandidateVacancy
from app.modules.matching.service import history as candidate_history
from app.modules.placement import schemas as data
from app.modules.placement.models import (
    EmploymentStatusHistory,
    FirstIncomeVerification,
    Placement,
    PlacementHistory,
)
from app.modules.supply.models import Participant, Person
from app.modules.supply.service import full_name


def expected_income(start: date, frequency: str | None, rule: dict[str, Any] | None) -> date | None:
    if frequency == "DAILY":
        return start
    if frequency == "WEEKLY" and rule and isinstance(rule.get("weekday"), int):
        delta = (int(rule["weekday"]) - start.weekday()) % 7
        return start + timedelta(days=delta or 7)
    if frequency == "BIWEEKLY" and rule and isinstance(rule.get("anchor_date"), str):
        try:
            anchor = date.fromisoformat(rule["anchor_date"])
        except ValueError:
            return None
        if anchor >= start:
            return anchor
        periods = ((start - anchor).days + 13) // 14
        return anchor + timedelta(days=periods * 14)
    if frequency == "MONTHLY" and rule and isinstance(rule.get("day"), int):
        payday = int(rule["day"])
        cutoff = rule.get("cutoff_day", payday)
        if not 1 <= payday <= 31 or not isinstance(cutoff, int) or not 1 <= cutoff <= 31:
            return None
        year, month = start.year, start.month
        if start.day > cutoff:
            month += 1
            if month == 13:
                year, month = year + 1, 1
        day = min(payday, calendar.monthrange(year, month)[1])
        result = date(year, month, day)
        if result < start:
            month += 1
            if month == 13:
                year, month = year + 1, 1
            result = date(year, month, min(payday, calendar.monthrange(year, month)[1]))
        return result
    return None


def due_status(row: FirstIncomeVerification, today: date | None = None) -> str:
    if row.status in {"CONFIRMED", "PAYMENT_DELAYED", "CANDIDATE_LEFT", "EXCEPTION"}:
        return row.status
    if not row.verification_due_date:
        return "NOT_SCHEDULED"
    current = today or date.today()
    if row.verification_due_date < current:
        return "OVERDUE"
    if row.verification_due_date == current:
        return "DUE"
    return "UPCOMING"


def placement_history(
    db: Session,
    row: Placement,
    previous: str | None,
    actor: Principal,
    reason: str | None,
) -> None:
    db.add(
        PlacementHistory(
            placement_id=row.id,
            from_status=previous,
            to_status=row.status,
            reason=reason,
            actor_type=actor.audit_actor.actor_type,
            actor_id=actor.audit_actor.actor_id,
        )
    )


def save(
    db: Session, row: Placement, actor: Principal, request: Request, code: str, changes: list[str]
) -> None:
    audit(
        db,
        code,
        actor.audit_actor,
        "PLACEMENT",
        row.id,
        request,
        changes={key: True for key in changes},
    )
    db.commit()
    db.refresh(row)


def locked(db: Session, identifier: UUID, version: int) -> Placement:
    row = db.scalar(select(Placement).where(Placement.id == identifier).with_for_update())
    if not row:
        fail("NOT_FOUND", "Placement not found.", 404)
    assert row
    writable(row, version)
    return row


def verification(db: Session, placement_id: UUID, *, lock: bool = False) -> FirstIncomeVerification:
    query = select(FirstIncomeVerification).where(
        FirstIncomeVerification.placement_id == placement_id
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        fail("NOT_FOUND", "First-income verification not found.", 404)
    assert row
    row.status = due_status(row)
    return row


def placement_view(
    db: Session, row: Placement, permissions: set[str] | None = None
) -> dict[str, Any]:
    candidate = get_record(db, CandidateVacancy, row.candidate_vacancy_id)
    vacancy = get_record(db, Vacancy, row.vacancy_id)
    organization = get_record(db, Organization, row.organization_id)
    participant = get_record(db, Participant, row.participant_id)
    person = get_record(db, Person, participant.person_id)
    owner = db.get(User, row.owner_id) if row.owner_id else None
    income = db.scalar(
        select(FirstIncomeVerification).where(FirstIncomeVerification.placement_id == row.id)
    )
    income_view = None
    if income:
        income_view = {
            key: getattr(income, key)
            for key in (
                "id",
                "version",
                "status",
                "verification_due_date",
                "actual_income_received_date",
                "verified_at",
                "verified_by",
                "amount_received",
                "evidence_document_id",
                "exception_reason",
                "notes",
            )
        }
        income_view["status"] = due_status(income)
        if permissions is not None and "participant_sensitive:view" not in permissions:
            income_view["amount_received"] = None
    result = {
        **{
            key: getattr(row, key)
            for key in (
                "id",
                "version",
                "placement_code",
                "participant_id",
                "candidate_vacancy_id",
                "organization_id",
                "vacancy_id",
                "status",
                "expected_start_date",
                "actual_start_date",
                "salary_amount",
                "salary_currency",
                "salary_frequency",
                "payroll_frequency",
                "payday_rule_json",
                "expected_first_income_date",
                "confirmed_at",
                "employment_end_date",
                "employment_end_reason",
                "currently_working",
                "owner_id",
                "created_at",
                "updated_at",
            )
        },
        "participant_name": full_name(person),
        "participant_code": participant.participant_code,
        "vacancy_title": vacancy.title,
        "organization_name": organization.name,
        "owner_name": owner.full_name if owner else None,
        "candidate_status": candidate.status,
        "first_income": income_view,
    }
    if permissions is not None and "participant_sensitive:view" not in permissions:
        result["salary_amount"] = None
    return result


def create(
    db: Session, values: data.PlacementCreate, actor: Principal, request: Request
) -> Placement:
    candidate = db.scalar(
        select(CandidateVacancy)
        .where(CandidateVacancy.id == values.candidate_vacancy_id)
        .with_for_update()
    )
    if not candidate:
        fail("NOT_FOUND", "Candidate relationship not found.", 404)
    assert candidate
    if values.candidate_version is not None:
        writable(candidate, values.candidate_version)
    if candidate.status != "SELECTED":
        fail("SELECTED_CANDIDATE_REQUIRED", "Only a selected candidate can be placed.", 422)
    if db.scalar(select(Placement.id).where(Placement.candidate_vacancy_id == candidate.id)):
        fail("PLACEMENT_EXISTS", "This selected candidate already has a placement.", 409)
    vacancy = get_record(db, Vacancy, candidate.vacancy_id)
    if vacancy.status not in {"ACTIVE", "PARTIALLY_FILLED"}:
        fail("VACANCY_NOT_ACTIVE", "The vacancy is not open for placement.", 422)
    if values.owner_id:
        owner = db.get(User, values.owner_id)
        if not owner or "placement:edit" not in permissions_for(owner):
            fail("INVALID_OWNER", "Choose an active placement owner.", 422)
    row = Placement(
        placement_code="PLC-" + str(uuid4()).split("-")[0].upper(),
        participant_id=candidate.participant_id,
        candidate_vacancy_id=candidate.id,
        organization_id=vacancy.organization_id,
        vacancy_id=vacancy.id,
        expected_start_date=values.expected_start_date,
        salary_amount=values.salary_amount,
        salary_currency=values.salary_currency,
        salary_frequency=values.salary_frequency,
        payroll_frequency=values.payroll_frequency,
        payday_rule_json=values.payday_rule_json,
        expected_first_income_date=values.manual_first_income_date,
        owner_id=values.owner_id or actor.user.id,
        created_by=actor.user.id,
        updated_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    db.add(
        FirstIncomeVerification(
            placement_id=row.id,
            status="EXCEPTION" if values.manual_first_income_date else "NOT_SCHEDULED",
            verification_due_date=values.manual_first_income_date,
            exception_reason=values.exception_reason,
            created_by=actor.user.id,
            updated_by=actor.user.id,
        )
    )
    placement_history(db, row, None, actor, None)
    save(db, row, actor, request, "placement.created", ["candidate_vacancy_id"])
    return row


def confirm_start(
    db: Session, identifier: UUID, values: data.Start, actor: Principal, request: Request
) -> Placement:
    row = locked(db, identifier, values.version)
    if row.status != "START_PENDING":
        fail("INVALID_PLACEMENT_TRANSITION", "Only a pending start can be confirmed.", 422)
    vacancy = get_record(db, Vacancy, row.vacancy_id)
    if (
        headcount(vacancy, db)["started"] >= vacancy.required_headcount
        and "vacancy:overfill_override" not in actor.permissions
    ):
        fail("VACANCY_HEADCOUNT_REACHED", "Vacancy headcount has already been reached.", 409)
    if row.expected_start_date and values.actual_start_date < row.expected_start_date - timedelta(
        days=365
    ):
        fail("INVALID_START_DATE", "Actual start date is implausibly early.", 422)
    due = values.manual_first_income_date or expected_income(
        values.actual_start_date, row.payroll_frequency, row.payday_rule_json
    )
    if due is None and not values.exception_reason:
        fail(
            "PAYROLL_SCHEDULE_REQUIRED",
            "Configure a payroll rule or provide a manual due date and exception reason.",
            422,
        )
    if due is not None and due < values.actual_start_date:
        fail("INVALID_FIRST_INCOME_DATE", "First income cannot predate the actual start.", 422)
    first = verification(db, row.id, lock=True)
    first.verification_due_date = due
    first.exception_reason = values.exception_reason
    first.status = "EXCEPTION" if values.exception_reason else due_status(first)
    changed(first, actor.user.id)
    previous = row.status
    row.actual_start_date = values.actual_start_date
    row.expected_first_income_date = due
    row.currently_working = True
    row.status = "AWAITING_FIRST_INCOME"
    changed(row, actor.user.id)
    candidate = db.get(CandidateVacancy, row.candidate_vacancy_id)
    assert candidate
    candidate_previous = candidate.status
    candidate.status = "AWAITING_FIRST_INCOME"
    changed(candidate, actor.user.id)
    candidate_history(db, candidate, candidate_previous, actor, values.notes)
    db.add(
        EmploymentStatusHistory(
            placement_id=row.id,
            status="WORKING",
            effective_date=values.actual_start_date,
            verified_by=actor.user.id,
            notes=values.notes,
        )
    )
    placement_history(db, row, previous, actor, values.notes)
    db.flush()
    counts = headcount(vacancy, db)
    if vacancy.status in {"ACTIVE", "PARTIALLY_FILLED"}:
        next_status = (
            "FULLY_FILLED" if counts["started"] >= counts["required"] else "PARTIALLY_FILLED"
        )
        if vacancy.status != next_status:
            vacancy.status = next_status
            changed(vacancy, actor.user.id)
            audit(
                db,
                "vacancy.headcount_status_changed",
                actor.audit_actor,
                "VACANCY",
                vacancy.id,
                request,
                changes={"status": next_status},
            )
    save(db, row, actor, request, "placement.start_confirmed", ["actual_start_date"])
    return row


def confirm_income(
    db: Session,
    identifier: UUID,
    values: data.FirstIncomeConfirm,
    actor: Principal,
    request: Request,
) -> Placement:
    row = db.scalar(select(Placement).where(Placement.id == identifier).with_for_update())
    if not row:
        fail("NOT_FOUND", "Placement not found.", 404)
    assert row
    first = verification(db, row.id, lock=True)
    if (
        first.status == "CONFIRMED"
        and first.actual_income_received_date == values.actual_income_received_date
        and first.amount_received == values.amount_received
    ):
        return row
    writable(first, values.version)
    if row.status != "AWAITING_FIRST_INCOME" or first.status == "CONFIRMED":
        fail("INVALID_PLACEMENT_TRANSITION", "First income is not awaiting confirmation.", 422)
    if row.actual_start_date and values.actual_income_received_date < row.actual_start_date:
        fail("INVALID_FIRST_INCOME_DATE", "Income cannot predate the actual start.", 422)
    first.status = "CONFIRMED"
    first.actual_income_received_date = values.actual_income_received_date
    first.amount_received = values.amount_received
    first.evidence_document_id = values.evidence_document_id
    first.notes = values.notes
    first.verified_at = now()
    first.verified_by = actor.user.id
    changed(first, actor.user.id)
    previous = row.status
    row.status = "CONFIRMED"
    row.confirmed_at = now()
    changed(row, actor.user.id)
    candidate = db.get(CandidateVacancy, row.candidate_vacancy_id)
    assert candidate
    candidate_previous = candidate.status
    candidate.status = "CONFIRMED_PLACEMENT"
    changed(candidate, actor.user.id)
    candidate_history(db, candidate, candidate_previous, actor, values.notes)
    placement_history(db, row, previous, actor, values.notes)
    save(db, row, actor, request, "placement.first_income_confirmed", ["confirmed_at"])
    return row


def end(
    db: Session, identifier: UUID, values: data.End, actor: Principal, request: Request
) -> Placement:
    row = locked(db, identifier, values.version)
    if row.status not in {"STARTED", "AWAITING_FIRST_INCOME", "CONFIRMED"}:
        fail("INVALID_PLACEMENT_TRANSITION", "This placement cannot be ended.", 422)
    if not row.actual_start_date or values.employment_end_date < row.actual_start_date:
        fail("INVALID_END_DATE", "Employment end cannot predate the start.", 422)
    previous = row.status
    row.status = "ENDED"
    row.employment_end_date = values.employment_end_date
    row.employment_end_reason = values.reason
    row.currently_working = False
    changed(row, actor.user.id)
    first = verification(db, row.id, lock=True)
    if first.status != "CONFIRMED":
        first.status = "CANDIDATE_LEFT"
        changed(first, actor.user.id)
    db.add(
        EmploymentStatusHistory(
            placement_id=row.id,
            status="ENDED",
            effective_date=values.employment_end_date,
            verified_by=actor.user.id,
            notes=values.reason,
        )
    )
    placement_history(db, row, previous, actor, values.reason)
    save(db, row, actor, request, "placement.employment_ended", ["employment_end_date"])
    return row


def start_outcome(
    db: Session,
    identifier: UUID,
    values: data.StartOutcome,
    actor: Principal,
    request: Request,
) -> Placement:
    row = locked(db, identifier, values.version)
    if row.status != "START_PENDING":
        fail("INVALID_PLACEMENT_TRANSITION", "Only a pending start can be closed.", 422)
    previous = row.status
    row.status = values.outcome
    row.currently_working = False
    changed(row, actor.user.id)
    first = verification(db, row.id, lock=True)
    first.status = "CANDIDATE_LEFT"
    first.exception_reason = values.reason
    changed(first, actor.user.id)
    candidate = db.get(CandidateVacancy, row.candidate_vacancy_id)
    assert candidate
    candidate_previous = candidate.status
    candidate.status = (
        "FAILED_TO_START" if values.outcome == "FAILED_TO_START" else "EMPLOYER_CANCELLED"
    )
    candidate.closed_reason = candidate.status
    candidate.closed_note = values.reason
    changed(candidate, actor.user.id)
    candidate_history(db, candidate, candidate_previous, actor, values.reason)
    db.add(
        EmploymentStatusHistory(
            placement_id=row.id,
            status=values.outcome,
            effective_date=values.effective_date,
            verified_by=actor.user.id,
            notes=values.reason,
        )
    )
    placement_history(db, row, previous, actor, values.reason)
    save(db, row, actor, request, "placement.start_closed", ["status"])
    return row


def correct_confirmation(
    db: Session,
    identifier: UUID,
    values: data.CorrectConfirmation,
    actor: Principal,
    request: Request,
) -> Placement:
    row = locked(db, identifier, values.version)
    first = verification(db, row.id, lock=True)
    previous = row.status
    candidate = db.get(CandidateVacancy, row.candidate_vacancy_id)
    assert candidate
    candidate_previous = candidate.status
    if values.confirmed:
        if not values.actual_income_received_date:
            fail(
                "INCOME_DATE_REQUIRED",
                "A received date is required to restore confirmation.",
                422,
            )
        first.status = "CONFIRMED"
        first.actual_income_received_date = values.actual_income_received_date
        first.amount_received = values.amount_received
        first.verified_at = now()
        first.verified_by = actor.user.id
        first.notes = values.reason
        row.confirmed_at = now()
        if row.status != "ENDED":
            row.status = "CONFIRMED"
        candidate.status = "CONFIRMED_PLACEMENT"
    else:
        first.status = "CANDIDATE_LEFT" if row.status == "ENDED" else due_status(first)
        if first.status == "CONFIRMED":
            first.status = "EXCEPTION"
        first.actual_income_received_date = None
        first.amount_received = None
        first.verified_at = None
        first.verified_by = None
        first.notes = values.reason
        row.confirmed_at = None
        if row.status == "CONFIRMED":
            row.status = "AWAITING_FIRST_INCOME"
            candidate.status = "AWAITING_FIRST_INCOME"
    changed(first, actor.user.id)
    changed(row, actor.user.id)
    changed(candidate, actor.user.id)
    if candidate.status != candidate_previous:
        candidate_history(db, candidate, candidate_previous, actor, values.reason)
    placement_history(db, row, previous, actor, values.reason)
    save(db, row, actor, request, "placement.confirmation_corrected", ["confirmed_at"])
    return row

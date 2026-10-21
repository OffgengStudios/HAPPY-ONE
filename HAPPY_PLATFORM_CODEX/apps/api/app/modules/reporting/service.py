import csv
import io
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.demand.models import Organization, Vacancy
from app.modules.demand.service import changed, writable
from app.modules.iam.dependencies import Principal
from app.modules.iam.service import audit
from app.modules.matching.models import CandidateHistory, CandidateVacancy, EmployerDecision
from app.modules.merl.models import DataQualityIssue, Outcome
from app.modules.placement.models import Placement
from app.modules.reporting import schemas as data
from app.modules.reporting.models import ReportExportJob, ReportTarget
from app.modules.supply.models import Participant, Person
from app.modules.supply.service import full_name

KPI_LABELS = {
    "KPI-PLC-001": "Confirmed placements",
    "KPI-PLC-002": "Unique participants placed",
    "KPI-VAC-001": "Positions required",
    "KPI-VAC-002": "Started headcount",
    "KPI-VAC-003": "Outstanding positions",
    "KPI-VAC-004": "Confirmed placement headcount",
    "KPI-MATCH-001": "Submission conversion",
    "KPI-MATCH-002": "Interview conversion",
    "KPI-MATCH-003": "Start conversion",
    "KPI-MATCH-004": "Placement confirmation conversion",
    "KPI-EMP-001": "Median employer turnaround (days)",
    "KPI-SUP-001": "Onboarding completion",
    "KPI-SUP-002": "Job ready",
    "KPI-MERL-001": "Latest verified still working",
    "KPI-MERL-002": "Retention",
    "KPI-DQ-001": "Completeness",
    "KPI-DQ-002": "Open duplicate suspects",
    "KPI-MKT-001": "Campaign leads",
    "KPI-MKT-002": "Campaign onboarding",
    "KPI-MKT-003": "Campaign placements",
}
OPEN_VACANCY = ["PENDING_CONFIRMATION", "ACTIVE", "PARTIALLY_FILLED", "ON_HOLD"]
FORMULA_PREFIX = re.compile(r"^[\s\ufeff]*[=+\-@]")
EXPORT_FIELDS = {
    "PLACEMENT": ["id", "code", "participant", "vacancy", "employer", "confirmed_at"],
    "VACANCY": ["id", "code", "vacancy", "employer", "required", "started", "outstanding"],
    "MATCH_STAGE": ["id", "stage", "occurred_at", "vacancy_id"],
    "MATCH_START": ["id", "code", "participant", "actual_start_date"],
    "TURNAROUND": ["id", "decision", "submitted_at", "decision_at", "days"],
    "SUPPLY": ["id", "code", "participant", "onboarding", "readiness", "availability"],
    "MERL": ["id", "participant", "as_of_date", "role"],
    "DATA_QUALITY": ["id", "code", "severity", "status", "description"],
}


def bounds(period: data.Period) -> tuple[datetime, datetime]:
    start = datetime.combine(period.date_from, datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(period.date_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    return start, end


def count(db: Session, query: Any) -> int:
    return int(db.scalar(query) or 0)


def target_view(row: ReportTarget) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "version",
            "kpi_code",
            "period_start",
            "period_end",
            "dimension_key",
            "target_value",
            "forecast_value",
            "notes",
            "created_at",
            "updated_at",
        )
    }


def target_for(db: Session, code: str, period: data.Period) -> ReportTarget | None:
    return db.scalar(
        select(ReportTarget).where(
            ReportTarget.kpi_code == code,
            ReportTarget.period_start == period.date_from,
            ReportTarget.period_end == period.date_to,
            ReportTarget.dimension_key == "GLOBAL",
            ReportTarget.archived_at.is_(None),
        )
    )


def metric(
    db: Session,
    period: data.Period,
    code: str,
    value: int | float | Decimal | None,
    *,
    numerator: int | None = None,
    denominator: int | None = None,
    unavailable_reason: str | None = None,
    basis: str = "PERIOD",
) -> dict[str, Any]:
    target = target_for(db, code, period)
    actual = Decimal(str(value)) if value is not None else None
    target_value = target.target_value if target else None
    return {
        "code": code,
        "label": KPI_LABELS[code],
        "value": actual,
        "numerator": numerator,
        "denominator": denominator,
        "available": unavailable_reason is None,
        "unavailable_reason": unavailable_reason,
        "basis": basis,
        "target": target_value,
        "gap": max(target_value - actual, Decimal(0))
        if target_value is not None and actual is not None
        else None,
        "forecast": target.forecast_value if target else None,
        "has_drilldown": unavailable_reason is None,
    }


def stage_count(db: Session, status: str, start: datetime, end: datetime) -> int:
    return count(
        db,
        select(func.count(func.distinct(CandidateHistory.candidate_vacancy_id))).where(
            CandidateHistory.to_status == status,
            CandidateHistory.occurred_at >= start,
            CandidateHistory.occurred_at < end,
        ),
    )


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def kpis(db: Session, period: data.Period) -> list[dict[str, Any]]:
    start, end = bounds(period)
    confirmed = count(
        db,
        select(func.count())
        .select_from(Placement)
        .where(
            Placement.confirmed_at >= start,
            Placement.confirmed_at < end,
            Placement.archived_at.is_(None),
        ),
    )
    unique_placed = count(
        db,
        select(func.count(func.distinct(Placement.participant_id))).where(
            Placement.confirmed_at >= start,
            Placement.confirmed_at < end,
            Placement.archived_at.is_(None),
        ),
    )
    open_vacancies = list(
        db.scalars(
            select(Vacancy).where(Vacancy.status.in_(OPEN_VACANCY), Vacancy.archived_at.is_(None))
        )
    )
    started_by_vacancy = dict(
        db.execute(
            select(Placement.vacancy_id, func.count(Placement.id))
            .where(
                Placement.actual_start_date.is_not(None),
                Placement.status.not_in(["FAILED_TO_START", "CANCELLED"]),
                Placement.archived_at.is_(None),
            )
            .group_by(Placement.vacancy_id)
        ).all()
    )
    positions = sum(row.required_headcount for row in open_vacancies)
    started_current = sum(started_by_vacancy.get(row.id, 0) for row in open_vacancies)
    outstanding = sum(
        max(row.required_headcount - started_by_vacancy.get(row.id, 0), 0) for row in open_vacancies
    )
    qualified = stage_count(db, "QUALIFIED", start, end)
    submitted = stage_count(db, "SUBMITTED", start, end)
    interviewed = stage_count(db, "INTERVIEW", start, end)
    selected = stage_count(db, "SELECTED", start, end)
    started_period = count(
        db,
        select(func.count())
        .select_from(Placement)
        .where(
            Placement.actual_start_date >= period.date_from,
            Placement.actual_start_date <= period.date_to,
            Placement.status.not_in(["FAILED_TO_START", "CANCELLED"]),
            Placement.archived_at.is_(None),
        ),
    )
    turnaround = [
        (decision.created_at - candidate.submitted_at).total_seconds() / 86400
        for decision, candidate in db.execute(
            select(EmployerDecision, CandidateVacancy)
            .join(CandidateVacancy, CandidateVacancy.id == EmployerDecision.candidate_vacancy_id)
            .where(
                EmployerDecision.created_at >= start,
                EmployerDecision.created_at < end,
                CandidateVacancy.submitted_at.is_not(None),
                EmployerDecision.decision.in_(["SELECTED", "REJECTED"]),
            )
        )
        if candidate.submitted_at
    ]
    registered = count(
        db,
        select(func.count())
        .select_from(Participant)
        .where(
            Participant.created_at >= start,
            Participant.created_at < end,
            Participant.archived_at.is_(None),
        ),
    )
    completed = count(
        db,
        select(func.count())
        .select_from(Participant)
        .where(
            Participant.created_at >= start,
            Participant.created_at < end,
            Participant.completed_at.is_not(None),
            Participant.completed_at < end,
            Participant.archived_at.is_(None),
        ),
    )
    job_ready = count(
        db,
        select(func.count())
        .select_from(Participant)
        .where(
            Participant.onboarding_status == "COMPLETE",
            Participant.readiness_status == "JOB_READY",
            Participant.availability_status == "AVAILABLE",
            Participant.archived_at.is_(None),
        ),
    )
    ranked = (
        select(
            Outcome.currently_working,
            func.row_number()
            .over(
                partition_by=Outcome.placement_id,
                order_by=(Outcome.as_of_date.desc(), Outcome.created_at.desc(), Outcome.id.desc()),
            )
            .label("rank"),
        )
        .where(Outcome.as_of_date <= period.date_to, Outcome.archived_at.is_(None))
        .subquery()
    )
    still_working = count(
        db,
        select(func.count())
        .select_from(ranked)
        .where(ranked.c.rank == 1, ranked.c.currently_working.is_(True)),
    )
    duplicate_issues = count(
        db,
        select(func.count())
        .select_from(DataQualityIssue)
        .where(
            DataQualityIssue.issue_type.icontains("DUPLICATE", autoescape=True),
            DataQualityIssue.status.in_(["OPEN", "IN_PROGRESS"]),
        ),
    )
    return [
        metric(db, period, "KPI-PLC-001", confirmed),
        metric(db, period, "KPI-PLC-002", unique_placed),
        metric(db, period, "KPI-VAC-001", positions, basis="CURRENT"),
        metric(db, period, "KPI-VAC-002", started_current, basis="CURRENT"),
        metric(db, period, "KPI-VAC-003", outstanding, basis="CURRENT"),
        metric(db, period, "KPI-VAC-004", confirmed),
        metric(
            db,
            period,
            "KPI-MATCH-001",
            rate(submitted, qualified),
            numerator=submitted,
            denominator=qualified,
        ),
        metric(
            db,
            period,
            "KPI-MATCH-002",
            rate(interviewed, submitted),
            numerator=interviewed,
            denominator=submitted,
        ),
        metric(
            db,
            period,
            "KPI-MATCH-003",
            rate(started_period, selected),
            numerator=started_period,
            denominator=selected,
        ),
        metric(
            db,
            period,
            "KPI-MATCH-004",
            rate(confirmed, started_period),
            numerator=confirmed,
            denominator=started_period,
        ),
        metric(
            db,
            period,
            "KPI-EMP-001",
            round(median(turnaround), 2) if turnaround else 0,
            numerator=len(turnaround),
        ),
        metric(
            db,
            period,
            "KPI-SUP-001",
            rate(completed, registered),
            numerator=completed,
            denominator=registered,
        ),
        metric(db, period, "KPI-SUP-002", job_ready, basis="CURRENT"),
        metric(db, period, "KPI-MERL-001", still_working, basis="AS_OF_END"),
        metric(
            db,
            period,
            "KPI-MERL-002",
            None,
            unavailable_reason="Official retention cadence and denominator are not approved.",
        ),
        metric(
            db,
            period,
            "KPI-DQ-001",
            None,
            unavailable_reason="A versioned completeness rule is not approved.",
        ),
        metric(db, period, "KPI-DQ-002", duplicate_issues, basis="CURRENT"),
        metric(
            db,
            period,
            "KPI-MKT-001",
            None,
            unavailable_reason="Campaign source attribution is not configured.",
        ),
        metric(
            db,
            period,
            "KPI-MKT-002",
            None,
            unavailable_reason="Campaign source attribution is not configured.",
        ),
        metric(
            db,
            period,
            "KPI-MKT-003",
            None,
            unavailable_reason="Multi-touch placement attribution is not approved.",
        ),
    ]


def limited(query: Any, limit: int | None) -> Any:
    return query.limit(limit) if limit is not None else query


def drilldown(
    db: Session, code: str, period: data.Period, limit: int | None = 5000
) -> list[dict[str, Any]]:
    if code not in KPI_LABELS:
        raise ApiError(404, "KPI_NOT_FOUND", "KPI not found.")
    current = next(item for item in kpis(db, period) if item["code"] == code)
    if not current["available"]:
        raise ApiError(422, "KPI_UNAVAILABLE", current["unavailable_reason"])
    start, end = bounds(period)
    if code.startswith("KPI-PLC") or code == "KPI-VAC-004":
        placement_rows = db.execute(
            limited(
                select(Placement, Participant, Person, Vacancy, Organization)
                .join(Participant, Participant.id == Placement.participant_id)
                .join(Person, Person.id == Participant.person_id)
                .join(Vacancy, Vacancy.id == Placement.vacancy_id)
                .join(Organization, Organization.id == Placement.organization_id)
                .where(Placement.confirmed_at >= start, Placement.confirmed_at < end)
                .order_by(Placement.confirmed_at.desc()),
                limit,
            )
        )
        return [
            {
                "id": str(p.id),
                "code": p.placement_code,
                "participant": full_name(person),
                "vacancy": vacancy.title,
                "employer": org.name,
                "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
            }
            for p, _participant, person, vacancy, org in placement_rows
        ]
    if code.startswith("KPI-VAC"):
        started = dict(
            db.execute(
                select(Placement.vacancy_id, func.count(Placement.id))
                .where(
                    Placement.actual_start_date.is_not(None),
                    Placement.status.not_in(["FAILED_TO_START", "CANCELLED"]),
                )
                .group_by(Placement.vacancy_id)
            ).all()
        )
        vacancy_rows = db.execute(
            limited(
                select(Vacancy, Organization)
                .join(Organization)
                .where(Vacancy.status.in_(OPEN_VACANCY), Vacancy.archived_at.is_(None)),
                limit,
            )
        )
        return [
            {
                "id": str(v.id),
                "code": v.vacancy_code,
                "vacancy": v.title,
                "employer": org.name,
                "required": v.required_headcount,
                "started": started.get(v.id, 0),
                "outstanding": max(v.required_headcount - started.get(v.id, 0), 0),
            }
            for v, org in vacancy_rows
        ]
    if code in {"KPI-MATCH-001", "KPI-MATCH-002"}:
        target_stage = "SUBMITTED" if code == "KPI-MATCH-001" else "INTERVIEW"
        matching_rows = db.execute(
            limited(
                select(CandidateHistory, CandidateVacancy)
                .join(CandidateVacancy)
                .where(
                    CandidateHistory.to_status == target_stage,
                    CandidateHistory.occurred_at >= start,
                    CandidateHistory.occurred_at < end,
                )
                .order_by(CandidateHistory.occurred_at.desc()),
                limit,
            )
        )
        return [
            {
                "id": str(candidate.id),
                "stage": history.to_status,
                "occurred_at": history.occurred_at.isoformat(),
                "vacancy_id": str(candidate.vacancy_id),
            }
            for history, candidate in matching_rows
        ]
    if code == "KPI-MATCH-003":
        started_rows = db.execute(
            limited(
                select(Placement, Participant, Person)
                .join(Participant, Participant.id == Placement.participant_id)
                .join(Person, Person.id == Participant.person_id)
                .where(
                    Placement.actual_start_date >= period.date_from,
                    Placement.actual_start_date <= period.date_to,
                    Placement.status.not_in(["FAILED_TO_START", "CANCELLED"]),
                ),
                limit,
            )
        )
        return [
            {
                "id": str(placement.id),
                "code": placement.placement_code,
                "participant": full_name(person),
                "actual_start_date": placement.actual_start_date.isoformat()
                if placement.actual_start_date
                else None,
            }
            for placement, _participant, person in started_rows
        ]
    if code == "KPI-MATCH-004":
        confirmed_rows = db.execute(
            limited(
                select(Placement, Participant, Person)
                .join(Participant, Participant.id == Placement.participant_id)
                .join(Person, Person.id == Participant.person_id)
                .where(Placement.confirmed_at >= start, Placement.confirmed_at < end),
                limit,
            )
        )
        return [
            {
                "id": str(placement.id),
                "code": placement.placement_code,
                "participant": full_name(person),
                "confirmed_at": placement.confirmed_at.isoformat()
                if placement.confirmed_at
                else None,
            }
            for placement, _participant, person in confirmed_rows
        ]
    if code == "KPI-EMP-001":
        turnaround_rows = db.execute(
            limited(
                select(EmployerDecision, CandidateVacancy)
                .join(CandidateVacancy)
                .where(
                    EmployerDecision.created_at >= start,
                    EmployerDecision.created_at < end,
                    CandidateVacancy.submitted_at.is_not(None),
                ),
                limit,
            )
        )
        return [
            {
                "id": str(decision.id),
                "decision": decision.decision,
                "submitted_at": candidate.submitted_at.isoformat()
                if candidate.submitted_at
                else None,
                "decision_at": decision.created_at.isoformat(),
                "days": round(
                    (decision.created_at - candidate.submitted_at).total_seconds() / 86400, 2
                )
                if candidate.submitted_at
                else None,
            }
            for decision, candidate in turnaround_rows
        ]
    if code.startswith("KPI-SUP"):
        participant_query = (
            select(Participant, Person).join(Person).where(Participant.archived_at.is_(None))
        )
        if code == "KPI-SUP-001":
            participant_query = participant_query.where(
                Participant.created_at >= start,
                Participant.created_at < end,
                Participant.completed_at.is_not(None),
                Participant.completed_at < end,
            )
        else:
            participant_query = participant_query.where(
                Participant.onboarding_status == "COMPLETE",
                Participant.readiness_status == "JOB_READY",
                Participant.availability_status == "AVAILABLE",
            )
        participant_rows = db.execute(limited(participant_query, limit))
        return [
            {
                "id": str(participant.id),
                "code": participant.participant_code,
                "participant": full_name(person),
                "onboarding": participant.onboarding_status,
                "readiness": participant.readiness_status,
                "availability": participant.availability_status,
            }
            for participant, person in participant_rows
        ]
    if code == "KPI-MERL-001":
        latest = (
            select(
                Outcome.id,
                func.row_number()
                .over(
                    partition_by=Outcome.placement_id,
                    order_by=(
                        Outcome.as_of_date.desc(),
                        Outcome.created_at.desc(),
                        Outcome.id.desc(),
                    ),
                )
                .label("rank"),
            )
            .where(
                Outcome.as_of_date <= period.date_to,
                Outcome.archived_at.is_(None),
            )
            .subquery()
        )
        outcome_rows = db.execute(
            limited(
                select(Outcome, Participant, Person)
                .join(latest, latest.c.id == Outcome.id)
                .join(Participant, Participant.id == Outcome.participant_id)
                .join(Person, Person.id == Participant.person_id)
                .where(latest.c.rank == 1, Outcome.currently_working.is_(True))
                .order_by(Outcome.as_of_date.desc()),
                limit,
            )
        )
        return [
            {
                "id": str(outcome.id),
                "participant": full_name(person),
                "as_of_date": outcome.as_of_date.isoformat(),
                "role": outcome.current_role,
            }
            for outcome, _participant, person in outcome_rows
        ]
    issue_rows = db.scalars(
        limited(
            select(DataQualityIssue).where(
                DataQualityIssue.issue_type.icontains("DUPLICATE", autoescape=True),
                DataQualityIssue.status.in_(["OPEN", "IN_PROGRESS"]),
            ),
            limit,
        )
    )
    return [
        {
            "id": str(row.id),
            "code": row.issue_code,
            "severity": row.severity,
            "status": row.status,
            "description": row.description,
        }
        for row in issue_rows
    ]


def export_fields(code: str) -> list[str]:
    if code.startswith("KPI-PLC") or code in {"KPI-VAC-004", "KPI-MATCH-004"}:
        return EXPORT_FIELDS["PLACEMENT"]
    if code.startswith("KPI-VAC"):
        return EXPORT_FIELDS["VACANCY"]
    if code in {"KPI-MATCH-001", "KPI-MATCH-002"}:
        return EXPORT_FIELDS["MATCH_STAGE"]
    if code == "KPI-MATCH-003":
        return EXPORT_FIELDS["MATCH_START"]
    if code == "KPI-EMP-001":
        return EXPORT_FIELDS["TURNAROUND"]
    if code.startswith("KPI-SUP"):
        return EXPORT_FIELDS["SUPPLY"]
    if code == "KPI-MERL-001":
        return EXPORT_FIELDS["MERL"]
    return EXPORT_FIELDS["DATA_QUALITY"]


def csv_cell(value: Any) -> Any:
    if isinstance(value, str):
        # Prefix only textual input. Trusted numbers/Decimal/date values retain
        # their type and representation; source records are never rewritten.
        if value.startswith(("\t", "\r", "\n", "\ufeff")) or FORMULA_PREFIX.match(value):
            return "'" + value
    return value


def csv_export(code: str, rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    fields = export_fields(code)
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({key: csv_cell(value) for key, value in row.items()} for row in rows)
    return output.getvalue()


def export_job_view(row: ReportExportJob) -> dict[str, Any]:
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "kpi_code",
            "period_start",
            "period_end",
            "format",
            "include_sensitive",
            "status",
            "row_count",
            "error_code",
            "error_message",
            "attempt_count",
            "next_attempt_at",
            "started_at",
            "completed_at",
            "created_at",
            "version",
        )
    }


def create_target(
    db: Session, values: data.TargetCreate, actor: Principal, request: Request
) -> ReportTarget:
    if values.kpi_code not in KPI_LABELS:
        raise ApiError(422, "KPI_NOT_FOUND", "Choose a registered KPI code.")
    if target_for(
        db, values.kpi_code, data.Period(date_from=values.period_start, date_to=values.period_end)
    ):
        raise ApiError(
            409, "REPORT_TARGET_EXISTS", "A global target already exists for this period."
        )
    row = ReportTarget(**values.model_dump(), created_by=actor.user.id, updated_by=actor.user.id)
    db.add(row)
    db.flush()
    audit(db, "report_target.created", actor.audit_actor, "report_target", row.id, request)
    db.commit()
    return row


def update_target(
    db: Session, row: ReportTarget, values: data.TargetUpdate, actor: Principal, request: Request
) -> ReportTarget:
    writable(row, values.version)
    if values.kpi_code not in KPI_LABELS:
        raise ApiError(422, "KPI_NOT_FOUND", "Choose a registered KPI code.")
    for key, value in values.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    changed(row, actor.user.id)
    audit(db, "report_target.updated", actor.audit_actor, "report_target", row.id, request)
    db.commit()
    return row

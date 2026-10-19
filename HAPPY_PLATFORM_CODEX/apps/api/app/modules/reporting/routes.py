from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from starlette.responses import Response, StreamingResponse

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.iam.dependencies import Database, Principal, require
from app.modules.iam.service import audit
from app.modules.marketing.models import Campaign
from app.modules.merl.models import DataQualityIssue, FollowUp
from app.modules.placement.models import FirstIncomeVerification, Placement
from app.modules.reporting import schemas as data
from app.modules.reporting import service as s
from app.modules.reporting.models import ReportExportJob, ReportTarget
from app.storage.s3 import get_storage_client

router = APIRouter(tags=["reporting"])
Read = Annotated[Principal, Depends(require("report:view"))]
Export = Annotated[Principal, Depends(require("report:view", "report:export"))]
TargetManage = Annotated[Principal, Depends(require("report_target:manage"))]


def period(date_from: date, date_to: date) -> data.Period:
    try:
        return data.Period(date_from=date_from, date_to=date_to)
    except ValidationError as exc:
        raise ApiError(422, "INVALID_REPORTING_PERIOD", "Check the reporting date range.") from exc


def validate_export(values: data.ExportRequest, actor: Principal) -> None:
    if values.include_sensitive:
        if "report:sensitive_export" not in actor.permissions:
            raise ApiError(403, "PERMISSION_DENIED", "Sensitive export is not permitted.")
        if not values.privacy_acknowledged:
            raise ApiError(
                422,
                "PRIVACY_ACKNOWLEDGEMENT_REQUIRED",
                "Acknowledge the privacy warning before sensitive export.",
            )


def owned_job(db: Database, identifier: UUID, actor: Principal) -> ReportExportJob:
    row = db.get(ReportExportJob, identifier)
    if not row or row.archived_at or row.requested_by != actor.user.id:
        raise ApiError(404, "REPORT_EXPORT_JOB_NOT_FOUND", "Export job not found.")
    return row


@router.get("/reports/dashboard")
def dashboard(date_from: date, date_to: date, db: Database, actor: Read) -> dict[str, Any]:
    selected = {
        "KPI-PLC-001",
        "KPI-PLC-002",
        "KPI-VAC-003",
        "KPI-MATCH-001",
        "KPI-EMP-001",
        "KPI-SUP-001",
        "KPI-MERL-001",
        "KPI-DQ-002",
    }
    report_period = period(date_from, date_to)
    metrics = [row for row in s.kpis(db, report_period) if row["code"] in selected]
    placement_trend = list(
        db.execute(
            select(
                func.to_char(Placement.confirmed_at, "YYYY-MM").label("month"),
                func.count(Placement.id),
            )
            .where(
                Placement.confirmed_at >= s.bounds(report_period)[0],
                Placement.confirmed_at < s.bounds(report_period)[1],
                Placement.archived_at.is_(None),
            )
            .group_by("month")
            .order_by("month")
        )
    )
    return {
        "period": {"date_from": date_from, "date_to": date_to},
        "metrics": metrics,
        "placement_trend": [
            {"month": month, "confirmed_placements": value} for month, value in placement_trend
        ],
        "attention": {
            "overdue_first_income": db.scalar(
                select(func.count())
                .select_from(FirstIncomeVerification)
                .where(FirstIncomeVerification.status.in_(["DUE", "OVERDUE"]))
            )
            or 0,
            "overdue_follow_ups": db.scalar(
                select(func.count())
                .select_from(FollowUp)
                .where(
                    FollowUp.status.in_(["SCHEDULED", "DUE", "OVERDUE"]),
                    FollowUp.scheduled_for < date.today(),
                )
            )
            or 0,
            "critical_data_quality": db.scalar(
                select(func.count())
                .select_from(DataQualityIssue)
                .where(
                    DataQualityIssue.severity.in_(["HIGH", "CRITICAL"]),
                    DataQualityIssue.status.in_(["OPEN", "IN_PROGRESS"]),
                )
            )
            or 0,
            "campaigns_awaiting_review": db.scalar(
                select(func.count())
                .select_from(Campaign)
                .where(Campaign.status == "AWAITING_REVIEW")
            )
            or 0,
        },
    }


@router.get("/reports/kpis")
def kpi_list(date_from: date, date_to: date, db: Database, actor: Read) -> dict[str, Any]:
    return {
        "period": {"date_from": date_from, "date_to": date_to},
        "items": s.kpis(db, period(date_from, date_to)),
    }


@router.get("/reports/kpis/{code}/drilldown")
def kpi_drilldown(
    code: str, date_from: date, date_to: date, db: Database, actor: Read
) -> dict[str, Any]:
    return {
        "code": code,
        "period": {"date_from": date_from, "date_to": date_to},
        "items": s.drilldown(db, code, period(date_from, date_to)),
    }


@router.post("/reports/export")
def export(values: data.ExportRequest, db: Database, actor: Export, request: Request) -> Response:
    validate_export(values, actor)
    rows = s.drilldown(db, values.kpi_code, values)
    content = s.csv_export(values.kpi_code, rows)
    audit(
        db,
        "report.exported",
        actor.audit_actor,
        "report",
        None,
        request,
        changes={
            "kpi_code": values.kpi_code,
            "date_from": values.date_from.isoformat(),
            "date_to": values.date_to.isoformat(),
            "row_count": len(rows),
            "include_sensitive": values.include_sensitive,
        },
    )
    db.commit()
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{values.kpi_code.lower()}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/reports/export-jobs", status_code=202)
def export_job_create(
    values: data.ExportRequest,
    db: Database,
    actor: Export,
    request: Request,
) -> dict[str, Any]:
    validate_export(values, actor)
    if values.kpi_code not in s.KPI_LABELS:
        raise ApiError(404, "KPI_NOT_FOUND", "KPI not found.")
    row = ReportExportJob(
        requested_by=actor.user.id,
        kpi_code=values.kpi_code,
        period_start=values.date_from,
        period_end=values.date_to,
        format=values.format,
        include_sensitive=values.include_sensitive,
        created_by=actor.user.id,
        updated_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        "report.export_requested",
        actor.audit_actor,
        "report_export_job",
        row.id,
        request,
        changes={
            "kpi_code": row.kpi_code,
            "date_from": row.period_start.isoformat(),
            "date_to": row.period_end.isoformat(),
            "include_sensitive": row.include_sensitive,
        },
    )
    db.commit()
    return s.export_job_view(row)


@router.get("/reports/export-jobs")
def export_jobs(db: Database, actor: Export) -> dict[str, Any]:
    rows = db.scalars(
        select(ReportExportJob)
        .where(
            ReportExportJob.requested_by == actor.user.id,
            ReportExportJob.archived_at.is_(None),
        )
        .order_by(ReportExportJob.created_at.desc())
        .limit(100)
    )
    return {"items": [s.export_job_view(row) for row in rows]}


@router.get("/reports/export-jobs/{identifier}")
def export_job(identifier: UUID, db: Database, actor: Export) -> dict[str, Any]:
    return s.export_job_view(owned_job(db, identifier, actor))


@router.get("/reports/export-jobs/{identifier}/download")
def export_job_download(
    identifier: UUID, db: Database, actor: Export, request: Request
) -> StreamingResponse:
    row = owned_job(db, identifier, actor)
    if row.status != "SUCCEEDED" or not row.storage_key:
        raise ApiError(409, "REPORT_EXPORT_NOT_READY", "The export is not ready for download.")
    body = get_storage_client().get_object(Bucket=settings.s3_bucket, Key=row.storage_key)["Body"]
    audit(
        db,
        "report.export_downloaded",
        actor.audit_actor,
        "report_export_job",
        row.id,
        request,
        changes={"kpi_code": row.kpi_code, "row_count": row.row_count},
    )
    db.commit()
    return StreamingResponse(
        body.iter_chunks(chunk_size=64 * 1024),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{row.kpi_code.lower()}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/reports/data-quality")
def data_quality(db: Database, actor: Read) -> dict[str, Any]:
    rows = db.execute(
        select(
            DataQualityIssue.status,
            DataQualityIssue.severity,
            func.count(DataQualityIssue.id),
        )
        .where(DataQualityIssue.archived_at.is_(None))
        .group_by(DataQualityIssue.status, DataQualityIssue.severity)
    )
    return {
        "items": [
            {"status": status, "severity": severity, "count": count}
            for status, severity, count in rows
        ]
    }


@router.get("/reports/targets")
def targets(db: Database, actor: Read) -> dict[str, Any]:
    rows = db.scalars(
        select(ReportTarget)
        .where(ReportTarget.archived_at.is_(None))
        .order_by(ReportTarget.period_start.desc(), ReportTarget.kpi_code)
    )
    return {"items": [s.target_view(row) for row in rows]}


@router.post("/reports/targets", status_code=201)
def target_create(
    values: data.TargetCreate, db: Database, actor: TargetManage, request: Request
) -> dict[str, Any]:
    return s.target_view(s.create_target(db, values, actor, request))


@router.patch("/reports/targets/{identifier}")
def target_update(
    identifier: UUID,
    values: data.TargetUpdate,
    db: Database,
    actor: TargetManage,
    request: Request,
) -> dict[str, Any]:
    row = db.get(ReportTarget, identifier)
    if not row or row.archived_at:
        raise ApiError(404, "REPORT_TARGET_NOT_FOUND", "Target not found.")
    return s.target_view(s.update_target(db, row, values, actor, request))

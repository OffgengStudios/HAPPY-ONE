from datetime import timedelta
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy import func, select

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.demand import files
from app.modules.demand import service as s
from app.modules.demand.models import (
    Contact,
    JobDescriptionVersion,
    Organization,
    Partnership,
    PartnershipDocument,
    ReferenceData,
    Requirement,
    Vacancy,
    VacancyChange,
)
from app.modules.demand.schemas import (
    Archive,
    ContactFields,
    ContactPatch,
    OrganizationCreate,
    OrganizationPatch,
    PartnershipFields,
    PartnershipPatch,
    RequirementWrite,
    Transition,
    VacancyCreate,
    VacancyPatch,
    VacancyTransition,
    Version,
    json_value,
    normalize_phone,
    normalized_name,
)
from app.modules.iam.dependencies import Current, Database, Principal, require
from app.modules.iam.models import User, now
from app.modules.iam.service import audit, page_query, permissions_for

router = APIRouter(tags=["demand"])
OrgRead = Annotated[Principal, Depends(require("organization:view"))]
OrgCreate = Annotated[Principal, Depends(require("organization:create", "organization:view"))]
OrgEdit = Annotated[Principal, Depends(require("organization:edit", "organization:view"))]
ContactRead = Annotated[Principal, Depends(require("organization_contact:view"))]
ContactEdit = Annotated[
    Principal, Depends(require("organization_contact:edit", "organization_contact:view"))
]
PartnerRead = Annotated[Principal, Depends(require("partnership:view"))]
PartnerEdit = Annotated[Principal, Depends(require("partnership:edit", "partnership:view"))]
PartnerDocumentRead = Annotated[Principal, Depends(require("partnership_document:view"))]
PartnerDocumentEdit = Annotated[
    Principal, Depends(require("partnership_document:view", "partnership_document:edit"))
]
PartnerDocumentDownload = Annotated[
    Principal,
    Depends(require("partnership_document:view", "partnership_document:download")),
]
VacRead = Annotated[Principal, Depends(require("vacancy:view"))]
VacCreate = Annotated[Principal, Depends(require("vacancy:create", "vacancy:view"))]
VacEdit = Annotated[Principal, Depends(require("vacancy:edit", "vacancy:view"))]
JobDescriptionRead = Annotated[Principal, Depends(require("job_description:view"))]
JobDescriptionEdit = Annotated[
    Principal, Depends(require("job_description:view", "job_description:edit"))
]
JobDescriptionDownload = Annotated[
    Principal, Depends(require("job_description:view", "job_description:download"))
]
Workspace = Annotated[Principal, Depends(require("workspace_demand:view"))]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=200)]


def _private_download(
    db: Database,
    document: PartnershipDocument | JobDescriptionVersion,
    actor: Principal,
    request: Request,
    event_code: str,
) -> Response:
    if document.archived_at or document.scan_status != "AVAILABLE":
        raise ApiError(409, "FILE_SCAN_PENDING", "This document is not available for download.")
    content = files.verified_bytes(document)
    audit(
        db,
        event_code,
        actor.user.id,
        document.__tablename__,
        document.id,
        request,
        changes={"version_number": document.version_number},
    )
    db.commit()
    return Response(
        content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _rescan_document(
    db: Database,
    document: PartnershipDocument | JobDescriptionVersion,
    version: int,
    actor: Principal,
    request: Request,
    event_code: str,
) -> dict[str, Any]:
    s.writable(document, version)
    if document.scan_status != "SCANNING":
        raise ApiError(
            409, "INVALID_STATUS_TRANSITION", "Only scan-pending documents can be rescanned."
        )
    document.scan_status = files.scan(files.verified_bytes(document))
    s.changed(document, actor.user.id)
    s.persist(
        db,
        actor,
        request,
        document,
        event_code,
        details={"scan_status": document.scan_status},
    )
    return files.public_view(document)


@router.get("/organizations")
def organizations(
    db: Database,
    actor: OrgRead,
    q: Search = "",
    status: str | None = None,
    owner_id: UUID | None = None,
    archived: bool = False,
    pipeline_only: bool = False,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(Organization).where(
        Organization.archived_at.is_not(None) if archived else Organization.archived_at.is_(None)
    )
    if q:
        query = query.where(
            Organization.name.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%")
        )
    if status:
        query = query.join(Partnership).where(Partnership.status == status)
    elif pipeline_only:
        query = query.join(Partnership).where(
            Partnership.status.in_(
                {"LEAD", "CONTACTED", "ENGAGED", "INTERESTED", "MOU_PENDING", "MOU_SIGNED"}
            )
        )
    if owner_id:
        query = query.where(Organization.relationship_owner_id == owner_id)
    page = page_query(query, Organization, db, limit, cursor)
    return {
        "items": [s.organization_view(db, row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/organizations", status_code=201)
def organization_create(
    data: OrganizationCreate, db: Database, actor: OrgCreate, request: Request
) -> dict[str, Any]:
    values = data.model_dump()
    values["website"] = str(data.website) if data.website else None
    return s.organization_view(db, s.create_organization(db, values, actor, request))


@router.get("/organizations/{identifier}")
def organization_detail(identifier: UUID, db: Database, actor: OrgRead) -> dict[str, Any]:
    return s.organization_view(db, s.get_record(db, Organization, identifier))


@router.patch("/organizations/{identifier}")
def organization_edit(
    identifier: UUID, data: OrganizationPatch, db: Database, actor: OrgEdit, request: Request
) -> dict[str, Any]:
    row = s.get_record(db, Organization, identifier, True)
    s.writable(row, data.version)
    s.duplicate_check(db, data.name, row.id, data.duplicate_acknowledged)
    s.assignable(db, data.relationship_owner_id, "workspace_demand:view")
    values = data.model_dump(exclude={"version", "duplicate_acknowledged"})
    values["website"] = str(data.website) if data.website else None
    for key, value in values.items():
        setattr(row, key, value)
    row.normalized_name = normalized_name(row.name)
    s.changed(row, actor.user.id)
    s.persist(db, actor, request, row, "organization.updated", list(values))
    return s.organization_view(db, row)


@router.post("/organizations/{identifier}/archive")
def organization_archive(
    identifier: UUID, data: Archive, db: Database, actor: OrgEdit, request: Request
) -> dict[str, Any]:
    row = s.get_record(db, Organization, identifier, True)
    s.writable(row, data.version)
    if db.scalar(
        select(Vacancy.id)
        .where(
            Vacancy.organization_id == identifier,
            Vacancy.status.not_in({"CLOSED", "CANCELLED", "FULLY_FILLED"}),
        )
        .limit(1)
    ):
        s.fail(
            "OPEN_VACANCIES_EXIST", "Close or cancel this employer's vacancies before archiving."
        )
    row.archived_at = now()
    s.changed(row, actor.user.id)
    s.persist(db, actor, request, row, "organization.archived", reason=data.reason)
    return s.organization_view(db, row)


@router.get("/organizations/{identifier}/activity")
def organization_activity(
    identifier: UUID, db: Database, actor: OrgRead, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    s.get_record(db, Organization, identifier)
    return s.activity(db, "organizations", identifier, limit, cursor, actor)


@router.get("/organizations/{identifier}/contacts")
def contacts(
    identifier: UUID, db: Database, actor: ContactRead, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    s.get_record(db, Organization, identifier)
    page = page_query(
        select(Contact).where(Contact.organization_id == identifier), Contact, db, limit, cursor
    )
    return {"items": [s.view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/organizations/{identifier}/contacts", status_code=201)
def contact_create(
    identifier: UUID, data: ContactFields, db: Database, actor: ContactEdit, request: Request
) -> dict[str, Any]:
    s.organization_exists(db, identifier, True)
    values = data.model_dump()
    values["email"] = str(data.email).lower() if data.email else None
    row = Contact(
        **values,
        organization_id=identifier,
        phone_normalized=normalize_phone(data.phone_raw),
        created_by=actor.user.id,
    )
    s.contact_primary(db, row)
    db.add(row)
    s.persist(db, actor, request, row, "organization_contact.created")
    return s.view(row)


@router.patch("/organization-contacts/{identifier}")
def contact_edit(
    identifier: UUID, data: ContactPatch, db: Database, actor: ContactEdit, request: Request
) -> dict[str, Any]:
    row = s.get_record(db, Contact, identifier)
    s.organization_exists(db, row.organization_id, True)
    row = s.get_record(db, Contact, identifier, True)
    db.refresh(row)
    s.writable(row, data.version)
    values = data.model_dump(exclude={"version"})
    values["email"] = str(data.email).lower() if data.email else None
    for key, value in values.items():
        setattr(row, key, value)
    row.phone_normalized = normalize_phone(row.phone_raw)
    with db.no_autoflush:
        s.contact_primary(db, row)
    s.changed(row, actor.user.id)
    s.persist(db, actor, request, row, "organization_contact.updated", list(values))
    return s.view(row)


@router.get("/organizations/{identifier}/partnership")
def partnership_detail(identifier: UUID, db: Database, actor: PartnerRead) -> dict[str, Any]:
    s.get_record(db, Organization, identifier)
    row = db.scalar(
        select(Partnership)
        .where(Partnership.organization_id == identifier, Partnership.archived_at.is_(None))
        .order_by(Partnership.start_date.desc(), Partnership.created_at.desc())
        .limit(1)
    )
    if not row:
        s.fail("RECORD_NOT_FOUND", "This employer has no partnership.", 404)
    assert row
    return s.partnership_view(row)


@router.get("/organizations/{identifier}/partnerships")
def partnerships(
    identifier: UUID,
    db: Database,
    actor: PartnerRead,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    s.get_record(db, Organization, identifier)
    page = page_query(
        select(Partnership).where(Partnership.organization_id == identifier),
        Partnership,
        db,
        limit,
        cursor,
    )
    return {
        "items": [s.partnership_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/organizations/{identifier}/partnership", status_code=201)
def partnership_create(
    identifier: UUID, data: PartnershipFields, db: Database, actor: PartnerEdit, request: Request
) -> dict[str, Any]:
    s.organization_exists(db, identifier, True)
    s.assignable(db, data.owner_id, "workspace_demand:view")
    row = Partnership(
        **data.model_dump(),
        partnership_code="PAR-" + uuid4().hex[:12].upper(),
        organization_id=identifier,
        created_by=actor.user.id,
        owner_assigned_at=now() if data.owner_id else None,
    )
    db.add(row)
    s.persist(db, actor, request, row, "partnership.created")
    return s.partnership_view(row)


@router.get("/partnerships/{identifier}/documents")
def partnership_documents(
    identifier: UUID,
    db: Database,
    actor: PartnerDocumentRead,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    s.get_record(db, Partnership, identifier)
    page = page_query(
        select(PartnershipDocument).where(PartnershipDocument.partnership_id == identifier),
        PartnershipDocument,
        db,
        limit,
        cursor,
    )
    return {
        "items": [files.public_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/partnerships/{identifier}/documents", status_code=201)
def partnership_document_upload(
    identifier: UUID,
    db: Database,
    actor: PartnerDocumentEdit,
    request: Request,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form(ge=1)],
) -> dict[str, Any]:
    row = s.get_record(db, Partnership, identifier, True)
    s.writable(row, version)
    content = file.file.read(settings.file_max_bytes + 1)
    document = files.upload(
        db,
        PartnershipDocument,
        "partnership_id",
        row.id,
        "partnerships/mou",
        content,
        file.filename or "",
        file.content_type or "",
        actor.user.id,
    )
    s.changed(row, actor.user.id)
    s.persist(
        db,
        actor,
        request,
        row,
        "partnership.document_uploaded",
        details={"document_id": str(document.id), "scan_status": document.scan_status},
    )
    return files.public_view(document)


@router.get("/partnership-documents/{identifier}/download")
def partnership_document_download(
    identifier: UUID,
    db: Database,
    actor: PartnerDocumentDownload,
    request: Request,
) -> Response:
    document = s.get_record(db, PartnershipDocument, identifier)
    s.get_record(db, Partnership, document.partnership_id)
    return _private_download(db, document, actor, request, "partnership.document_downloaded")


@router.post("/partnership-documents/{identifier}/rescan")
def partnership_document_rescan(
    identifier: UUID,
    values: Version,
    db: Database,
    actor: PartnerDocumentEdit,
    request: Request,
) -> dict[str, Any]:
    document = s.get_record(db, PartnershipDocument, identifier, True)
    return _rescan_document(
        db, document, values.version, actor, request, "partnership.document_scan_completed"
    )


@router.patch("/partnerships/{identifier}")
def partnership_edit(
    identifier: UUID, data: PartnershipPatch, db: Database, actor: PartnerEdit, request: Request
) -> dict[str, Any]:
    original = s.get_record(db, Partnership, identifier)
    s.organization_exists(db, original.organization_id, True)
    row = s.get_record(db, Partnership, identifier, True)
    db.refresh(row)
    s.writable(row, data.version)
    if row.mou_required != data.mou_required and not data.reason:
        s.fail("MOU_POLICY_REASON_REQUIRED", "Changing the MOU requirement needs a reason.", 422)
    if not data.mou_signed_at and (
        row.status == "MOU_SIGNED" or (row.status == "ACTIVE" and data.mou_required)
    ):
        s.fail("MOU_SIGNATURE_REQUIRED", "This relationship needs a signed MOU date.")
    s.assignable(db, data.owner_id, "workspace_demand:view")
    before = {
        key: json_value(getattr(row, key))
        for key in (
            "partnership_type",
            "start_date",
            "end_date",
            "mou_required",
            "mou_sent_at",
            "mou_signed_at",
            "owner_id",
            "priority",
        )
    }
    if row.owner_id != data.owner_id:
        row.owner_assigned_at = now() if data.owner_id else None
    values = data.model_dump(exclude={"version", "reason"})
    for key in ("partnership_type", "start_date", "end_date"):
        if key not in data.model_fields_set:
            values.pop(key)
    for key, value in values.items():
        setattr(row, key, value)
    s.changed(row, actor.user.id)
    s.persist(
        db,
        actor,
        request,
        row,
        "partnership.updated",
        list(values),
        data.reason,
        details={"before": before, "after": {key: json_value(getattr(row, key)) for key in before}},
    )
    return s.partnership_view(row)


@router.post("/partnerships/{identifier}/transition")
def partnership_move(
    identifier: UUID, data: Transition, db: Database, actor: PartnerEdit, request: Request
) -> dict[str, Any]:
    original = s.get_record(db, Partnership, identifier)
    s.organization_exists(db, original.organization_id, True)
    row = s.get_record(db, Partnership, identifier, True)
    db.refresh(row)
    s.writable(row, data.version)
    before = row.status
    s.partnership_transition(row, data.to_status, data.reason)
    s.changed(row, actor.user.id)
    s.persist(
        db,
        actor,
        request,
        row,
        "partnership.status_changed",
        ["status"],
        data.reason,
        details={"from_status": before, "to_status": row.status},
    )
    return s.partnership_view(row)


@router.get("/vacancies")
def vacancies(
    db: Database,
    actor: VacRead,
    q: Search = "",
    status: str | None = None,
    organization_id: UUID | None = None,
    priority: Literal["NORMAL", "HIGH", "URGENT"] | None = None,
    owner_id: UUID | None = None,
    open_only: bool = False,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = select(Vacancy).where(Vacancy.archived_at.is_(None))
    if q:
        query = query.where(
            Vacancy.title.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%")
        )
    if status:
        query = query.where(Vacancy.status == status)
    if organization_id:
        query = query.where(Vacancy.organization_id == organization_id)
    if priority:
        query = query.where(Vacancy.priority == priority)
    if owner_id:
        query = query.where(Vacancy.demand_owner_id == owner_id)
    if open_only:
        query = query.where(Vacancy.status.in_(s.OPEN_STATES))
    page = page_query(query, Vacancy, db, limit, cursor)
    return {
        "items": [s.vacancy_view(db, row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/vacancies", status_code=201)
def vacancy_create(
    data: VacancyCreate, db: Database, actor: VacCreate, request: Request
) -> dict[str, Any]:
    s.organization_exists(db, data.organization_id, True)
    s.assignable(db, data.demand_owner_id, "workspace_demand:view")
    s.assignable(db, data.owner_id, "vacancy:edit")
    row = Vacancy(
        **data.model_dump(),
        vacancy_code="VAC-" + uuid4().hex[:12].upper(),
        created_by=actor.user.id,
    )
    db.add(row)
    s.persist(db, actor, request, row, "vacancy.created")
    return s.vacancy_view(db, row)


@router.get("/vacancies/{identifier}")
def vacancy_detail(identifier: UUID, db: Database, actor: VacRead) -> dict[str, Any]:
    return s.vacancy_view(db, s.get_record(db, Vacancy, identifier))


@router.get("/vacancies/{identifier}/job-descriptions")
def job_descriptions(
    identifier: UUID,
    db: Database,
    actor: JobDescriptionRead,
    limit: Limit = 25,
    cursor: str | None = None,
) -> dict[str, Any]:
    s.get_record(db, Vacancy, identifier)
    page = page_query(
        select(JobDescriptionVersion).where(JobDescriptionVersion.vacancy_id == identifier),
        JobDescriptionVersion,
        db,
        limit,
        cursor,
    )
    return {
        "items": [files.public_view(row) for row in page["rows"]],
        "next_cursor": page["next_cursor"],
    }


@router.post("/vacancies/{identifier}/job-descriptions", status_code=201)
def job_description_upload(
    identifier: UUID,
    db: Database,
    actor: JobDescriptionEdit,
    request: Request,
    file: Annotated[UploadFile, File()],
    version: Annotated[int, Form(ge=1)],
) -> dict[str, Any]:
    row = s.get_record(db, Vacancy, identifier, True)
    s.writable(row, version)
    content = file.file.read(settings.file_max_bytes + 1)
    document = files.upload(
        db,
        JobDescriptionVersion,
        "vacancy_id",
        row.id,
        "vacancies/job-descriptions",
        content,
        file.filename or "",
        file.content_type or "",
        actor.user.id,
    )
    s.changed(row, actor.user.id)
    s.persist(
        db,
        actor,
        request,
        row,
        "vacancy.job_description_uploaded",
        details={"document_id": str(document.id), "scan_status": document.scan_status},
    )
    return files.public_view(document)


@router.get("/job-descriptions/{identifier}/download")
def job_description_download(
    identifier: UUID,
    db: Database,
    actor: JobDescriptionDownload,
    request: Request,
) -> Response:
    document = s.get_record(db, JobDescriptionVersion, identifier)
    s.get_record(db, Vacancy, document.vacancy_id)
    return _private_download(db, document, actor, request, "vacancy.job_description_downloaded")


@router.post("/job-descriptions/{identifier}/rescan")
def job_description_rescan(
    identifier: UUID,
    values: Version,
    db: Database,
    actor: JobDescriptionEdit,
    request: Request,
) -> dict[str, Any]:
    document = s.get_record(db, JobDescriptionVersion, identifier, True)
    return _rescan_document(
        db, document, values.version, actor, request, "vacancy.job_description_scan_completed"
    )


@router.patch("/vacancies/{identifier}")
def vacancy_edit(
    identifier: UUID, data: VacancyPatch, db: Database, actor: VacEdit, request: Request
) -> dict[str, Any]:
    row = s.get_record(db, Vacancy, identifier, True)
    s.writable(row, data.version)
    s.assignable(db, data.demand_owner_id, "workspace_demand:view")
    s.assignable(db, data.owner_id, "vacancy:edit")
    if data.required_headcount < s.headcount(row, db)["started"]:
        s.fail(
            "HEADCOUNT_BELOW_STARTS",
            "Required headcount cannot be reduced below recorded actual starts.",
        )
    values = data.model_dump(exclude={"version", "reason"})
    fields = []
    for key, value in values.items():
        old = getattr(row, key)
        if old != value:
            s.log_change(db, row, key, old, value, data.reason, actor.user.id)
            fields.append(key)
            setattr(row, key, value)
    s.changed(row, actor.user.id)
    s.persist(db, actor, request, row, "vacancy.updated_material", fields, data.reason)
    return s.vacancy_view(db, row)


@router.post("/vacancies/{identifier}/transition")
def vacancy_move(
    identifier: UUID, data: VacancyTransition, db: Database, actor: VacEdit, request: Request
) -> dict[str, Any]:
    row = s.get_record(db, Vacancy, identifier, True)
    s.writable(row, data.version)
    before = row.status
    s.vacancy_transition(
        row,
        data.to_status,
        settings.demand_vacancy_confirmation_required,
        data.closure_reason,
        data.closure_note,
        db,
    )
    s.log_change(
        db, row, "status", before, row.status, data.closure_reason or data.reason, actor.user.id
    )
    s.changed(row, actor.user.id)
    if row.status in {"CLOSED", "CANCELLED"}:
        audit(
            db,
            "vacancy.closed",
            actor.user.id,
            "vacancies",
            row.id,
            request,
            changes={"reason": data.closure_reason, "from_status": before, "to_status": row.status},
        )
    s.persist(
        db,
        actor,
        request,
        row,
        "vacancy.status_changed",
        ["status"],
        data.closure_reason or data.reason,
        details={"from_status": before, "to_status": row.status},
    )
    return s.vacancy_view(db, row)


@router.post("/vacancies/{identifier}/close")
def vacancy_close(
    identifier: UUID, data: VacancyTransition, db: Database, actor: VacEdit, request: Request
) -> dict[str, Any]:
    if data.to_status not in {"CLOSED", "CANCELLED"}:
        s.fail("INVALID_TRANSITION", "Use CLOSED or CANCELLED for this action.", 422)
    return vacancy_move(identifier, data, db, actor, request)


@router.get("/vacancies/{identifier}/headcount")
def vacancy_headcount(identifier: UUID, db: Database, actor: VacRead) -> dict[str, int]:
    return s.headcount(s.get_record(db, Vacancy, identifier), db)


@router.get("/vacancies/{identifier}/changes")
def vacancy_changes(
    identifier: UUID, db: Database, actor: VacRead, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    s.get_record(db, Vacancy, identifier)
    page = page_query(
        select(VacancyChange).where(VacancyChange.vacancy_id == identifier),
        VacancyChange,
        db,
        limit,
        cursor,
    )
    return {
        "items": [
            {key: json_value(getattr(row, key)) for key in row.__table__.columns.keys()}
            for row in page["rows"]
        ],
        "next_cursor": page["next_cursor"],
    }


@router.get("/vacancies/{identifier}/activity")
def vacancy_activity(
    identifier: UUID, db: Database, actor: VacRead, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    s.get_record(db, Vacancy, identifier)
    return s.activity(db, "vacancies", identifier, limit, cursor, actor)


@router.get("/vacancies/{identifier}/requirements")
def requirements(
    identifier: UUID, db: Database, actor: VacRead, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    s.get_record(db, Vacancy, identifier)
    page = page_query(
        select(Requirement).where(
            Requirement.vacancy_id == identifier, Requirement.archived_at.is_(None)
        ),
        Requirement,
        db,
        limit,
        cursor,
    )
    return {"items": [s.view(row) for row in page["rows"]], "next_cursor": page["next_cursor"]}


@router.post("/vacancies/{identifier}/requirements", status_code=201)
def requirement_create(
    identifier: UUID, data: RequirementWrite, db: Database, actor: VacEdit, request: Request
) -> dict[str, Any]:
    vacancy = s.get_record(db, Vacancy, identifier, True)
    s.writable(vacancy, data.version)
    row = Requirement(
        **data.model_dump(exclude={"version", "reason"}),
        vacancy_id=identifier,
        created_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    s.log_change(
        db, vacancy, "requirement:" + str(row.id), None, s.view(row), data.reason, actor.user.id
    )
    s.changed(vacancy, actor.user.id)
    s.persist(db, actor, request, vacancy, "vacancy.requirement_created", [data.criterion_key])
    return s.view(row)


@router.patch("/vacancy-requirements/{identifier}")
def requirement_edit(
    identifier: UUID, data: RequirementWrite, db: Database, actor: VacEdit, request: Request
) -> dict[str, Any]:
    original = s.get_record(db, Requirement, identifier)
    vacancy = s.get_record(db, Vacancy, original.vacancy_id, True)
    s.writable(vacancy, data.version)
    row = s.get_record(db, Requirement, identifier, True)
    if row.archived_at:
        s.fail("RECORD_ARCHIVED", "This requirement is archived.")
    before = s.view(row)
    for key, value in data.model_dump(exclude={"version", "reason"}).items():
        setattr(row, key, value)
    s.changed(row, actor.user.id)
    s.log_change(
        db, vacancy, "requirement:" + str(row.id), before, s.view(row), data.reason, actor.user.id
    )
    s.changed(vacancy, actor.user.id)
    s.persist(db, actor, request, vacancy, "vacancy.requirement_updated", [row.criterion_key])
    return s.view(row)


@router.post("/vacancy-requirements/{identifier}/archive")
def requirement_archive(
    identifier: UUID, data: Archive, db: Database, actor: VacEdit, request: Request
) -> dict[str, Any]:
    original = s.get_record(db, Requirement, identifier)
    vacancy = s.get_record(db, Vacancy, original.vacancy_id, True)
    s.writable(vacancy, data.version)
    row = s.get_record(db, Requirement, identifier, True)
    if row.archived_at:
        s.fail("RECORD_ARCHIVED", "This requirement is already archived.")
    before = s.view(row)
    row.archived_at = now()
    s.changed(row, actor.user.id)
    s.log_change(
        db, vacancy, "requirement:" + str(row.id), before, None, data.reason, actor.user.id
    )
    s.changed(vacancy, actor.user.id)
    s.persist(db, actor, request, vacancy, "vacancy.requirement_archived", [row.criterion_key])
    return s.view(row)


@router.get("/demand/owners")
def owners(db: Database, actor: Current) -> dict[str, Any]:
    if not {"workspace_demand:view", "vacancy:edit"} & actor.permissions:
        s.fail("PERMISSION_DENIED", "Staff directory access is not permitted.", 403)
    rows = db.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.full_name)
    ).unique()
    return {
        "items": [
            {
                "id": str(row.id),
                "full_name": row.full_name,
                "demand": "workspace_demand:view" in permissions_for(row),
                "recruiter": "vacancy:edit" in permissions_for(row),
            }
            for row in rows
            if {"workspace_demand:view", "vacancy:edit"} & permissions_for(row)
        ]
    }


@router.get("/demand/reference-data")
def reference_data(db: Database, actor: VacRead) -> dict[str, Any]:
    result: dict[str, list[dict[str, str]]] = {}
    for row in db.scalars(
        select(ReferenceData).order_by(ReferenceData.group_code, ReferenceData.code)
    ):
        result.setdefault(row.group_code, []).append({"value": row.code, "label": row.label})
    return result


def dashboard_access(actor: Principal) -> None:
    if not {"organization:view", "partnership:view", "vacancy:view"} <= actor.permissions:
        s.fail(
            "PERMISSION_DENIED",
            "This workspace needs employer, partnership, and vacancy access.",
            403,
        )


@router.get("/demand/dashboard")
def dashboard(db: Database, actor: Workspace) -> dict[str, Any]:
    dashboard_access(actor)
    active = db.scalar(
        select(func.count())
        .select_from(Partnership)
        .join(Organization)
        .where(Partnership.status == "ACTIVE", Organization.archived_at.is_(None))
    )
    pending = db.scalar(
        select(func.count())
        .select_from(Partnership)
        .join(Organization)
        .where(Partnership.status == "MOU_PENDING", Organization.archived_at.is_(None))
    )
    query = select(Vacancy).where(Vacancy.status.in_(s.OPEN_STATES), Vacancy.archived_at.is_(None))
    rows = list(db.scalars(query))
    return {
        "metrics": [
            {
                "code": "DEMAND-ACTIVE-EMPLOYERS",
                "label": "Active employers",
                "value": active,
                "resource": "employers",
                "filters": {"status": "ACTIVE"},
            },
            {
                "code": "DEMAND-MOU-PENDING",
                "label": "MOU pending",
                "value": pending,
                "resource": "employers",
                "filters": {"status": "MOU_PENDING"},
            },
            {
                "code": "KPI-VAC-001",
                "label": "Positions required",
                "value": sum(r.required_headcount for r in rows),
                "resource": "vacancies",
                "filters": {"open_only": "true"},
            },
            {
                "code": "KPI-VAC-003",
                "label": "Outstanding positions",
                "value": sum(s.headcount(r, db)["outstanding"] for r in rows),
                "resource": "vacancies",
                "filters": {"open_only": "true"},
            },
        ],
        "vacancy_confirmation_required": settings.demand_vacancy_confirmation_required,
    }


@router.get("/demand/my-work")
def my_work(
    db: Database, actor: Workspace, limit: Limit = 25, cursor: str | None = None
) -> dict[str, Any]:
    dashboard_access(actor)
    query = (
        select(Partnership)
        .join(Organization)
        .where(
            Partnership.owner_id == actor.user.id,
            Partnership.next_action.is_not(None),
            Organization.archived_at.is_(None),
            Partnership.status.not_in({"DECLINED", "INACTIVE"}),
        )
    )
    page = page_query(query, Partnership, db, limit, cursor)
    return {
        "items": [
            {
                "id": str(row.id),
                "organization_id": str(row.organization_id),
                "title": row.next_action,
                "organization_name": s.get_record(db, Organization, row.organization_id).name,
                "due_at": json_value(row.next_action_due_at),
                "bucket": s.work_bucket(row.next_action_due_at),
                "priority": row.priority,
                "owner_name": actor.user.full_name,
                "assigned_at": json_value(row.owner_assigned_at),
                "recently_assigned": bool(
                    row.owner_assigned_at and row.owner_assigned_at >= now() - timedelta(days=7)
                ),
            }
            for row in page["rows"]
        ],
        "next_cursor": page["next_cursor"],
    }

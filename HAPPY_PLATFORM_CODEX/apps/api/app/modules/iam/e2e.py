"""Synthetic browser-test infrastructure, isolated from application data."""

import hashlib
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, date, datetime
from uuid import uuid4

import psutil
from cryptography.fernet import Fernet
from pydantic import SecretStr
from pypdf import PdfWriter
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from app.core.config import API_ROOT, PROJECT_ROOT, settings
from app.core.process import creation_flags
from app.db.sandbox import create_test_schema, drop_test_schema, test_schema_url
from app.integrations.employer_portal.models import EmployerSubmission
from app.integrations.employer_portal.schemas import PortalSubmission
from app.integrations.employer_portal.service import encrypt as encrypt_portal_submission
from app.integrations.intake.models import IntakeDocument, PublicIntake
from app.modules.demand.models import Organization, Partnership, Vacancy
from app.modules.iam.actors import AuditActor
from app.modules.iam.models import Permission, PermissionOverride, Role, User
from app.modules.iam.security import hasher
from app.modules.iam.service import audit
from app.modules.matching.models import CandidateHistory, CandidateVacancy
from app.modules.placement.models import Placement
from app.modules.reporting.models import ReportExportJob
from app.modules.supply.models import Consent, Document, Participant, Person
from app.modules.training.models import Training
from app.storage.s3 import get_storage_client


def cleanup_documents(engine: Engine) -> None:
    with Session(engine) as db:
        for document in db.scalars(select(Document)):
            owns_cv = document.storage_key.startswith(f"participants/{document.participant_id}/cv/")
            if not owns_cv and document.storage_key.startswith("intakes/"):
                staged = db.scalar(
                    select(IntakeDocument)
                    .join(PublicIntake)
                    .where(
                        IntakeDocument.linked_document_id == document.id,
                        PublicIntake.participant_id == document.participant_id,
                        IntakeDocument.storage_key == document.storage_key,
                    )
                )
                owns_cv = staged is not None and document.storage_key.startswith(
                    f"intakes/{staged.intake_id}/"
                )
            if not owns_cv:
                raise ValueError("Refusing cleanup outside the synthetic participant's CV prefix.")
            get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=document.storage_key)


def cleanup_intake_documents(engine: Engine) -> None:
    with Session(engine) as db:
        for staged in db.scalars(select(IntakeDocument)):
            if not staged.storage_key.startswith(f"intakes/{staged.intake_id}/"):
                raise ValueError("Refusing cleanup outside the synthetic intake prefix.")
            get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=staged.storage_key)


def cleanup_report_exports(engine: Engine) -> None:
    with Session(engine) as db:
        for job in db.scalars(
            select(ReportExportJob).where(ReportExportJob.storage_key.is_not(None))
        ):
            expected = f"reports/exports/{job.requested_by}/"
            if not job.storage_key or not job.storage_key.startswith(expected):
                raise ValueError("Refusing cleanup outside the synthetic report export prefix.")
            get_storage_client().delete_object(Bucket=settings.s3_bucket, Key=job.storage_key)


def start() -> None:
    schema, url = create_test_schema()
    process = None
    worker = None
    engine = create_engine(url)
    try:
        encryption_key = Fernet.generate_key().decode()
        settings.identity_encryption_key = SecretStr(encryption_key)
        password = secrets.token_urlsafe(24)
        encoded = hasher.hash(password)
        with Session(engine) as db:
            for code in (
                "ADMIN",
                "MARKETING",
                "DEMAND",
                "SUPPLY",
                "MATCHING",
                "MERL",
                "MANAGEMENT",
            ):
                role = db.scalar(select(Role).where(Role.code == code))
                assert role
                db.add(
                    User(
                        email=code.lower() + "@example.org",
                        full_name=code.title() + " Test",
                        password_hash=encoded,
                        roles=[role],
                        primary_role_id=role.id,
                    )
                )
            db.commit()
            supply_role = db.scalar(select(Role).where(Role.code == "SUPPLY"))
            denied_permission = db.scalar(
                select(Permission).where(Permission.code == "participant:view")
            )
            assert supply_role and denied_permission
            db.add(
                User(
                    email="supply-denied@example.org",
                    full_name="Supply Denied Test",
                    password_hash=encoded,
                    roles=[supply_role],
                    primary_role_id=supply_role.id,
                    overrides=[
                        PermissionOverride(permission_id=denied_permission.id, effect="DENY")
                    ],
                )
            )
            db.commit()
            owner = db.scalar(select(User).where(User.email == "supply@example.org"))
            for email, role_code, grants in (
                (
                    "granted-creator@example.org",
                    "MARKETING",
                    {
                        "organization:view": "ALLOW",
                        "organization:create": "ALLOW",
                        "participant:view": "ALLOW",
                        "participant:create": "ALLOW",
                    },
                ),
                (
                    "demand-create-denied@example.org",
                    "DEMAND",
                    {"organization:create": "DENY"},
                ),
                (
                    "supply-edit-denied@example.org",
                    "SUPPLY",
                    {"participant:edit": "DENY"},
                ),
            ):
                role = db.scalar(select(Role).where(Role.code == role_code))
                assert role
                permissions = {
                    permission.code: permission.id
                    for permission in db.scalars(
                        select(Permission).where(Permission.code.in_(grants))
                    )
                }
                db.add(
                    User(
                        email=email,
                        full_name="Synthetic Creator Test",
                        password_hash=encoded,
                        roles=[role],
                        primary_role_id=role.id,
                        overrides=[
                            PermissionOverride(permission_id=permissions[code], effect=effect)
                            for code, effect in grants.items()
                        ],
                    )
                )
            db.commit()
            assert owner
            for projection, phone in (("desktop", "0245555555"), ("mobile", "0245555556")):
                person = Person(
                    first_name="Synthetic",
                    surname="CV Fixture " + projection,
                    normalized_name="synthetic cv fixture " + projection,
                    phone_raw=phone,
                    phone_normalized="+233" + phone[1:],
                    community="Synthetic fixture",
                )
                db.add(person)
                db.flush()
                participant = Participant(
                    person_id=person.id,
                    participant_code="HAPPY-BROWSER-CV-" + projection.upper(),
                    assigned_user_id=owner.id,
                )
                db.add(participant)
                db.flush()
                # AVAILABLE is a synthetic UI fixture, never a scanner replacement.
                output = io.BytesIO()
                writer = PdfWriter()
                writer.add_blank_page(width=100, height=100)
                writer.write(output)
                content = output.getvalue()
                document = Document(
                    participant_id=participant.id,
                    document_code="DOC-" + uuid4().hex.upper(),
                    storage_key=f"participants/{participant.id}/cv/{uuid4().hex}",
                    original_filename="synthetic-scanned-fixture.pdf",
                    mime_type="application/pdf",
                    size_bytes=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    version_number=1,
                    scan_status="AVAILABLE",
                )
                db.add(document)
                db.commit()
                get_storage_client().put_object(
                    Bucket=settings.s3_bucket,
                    Key=document.storage_key,
                    Body=content,
                    ContentType="application/pdf",
                )
            employer = Organization(
                organization_code="EMP-BROWSER-FIXTURE",
                name="Synthetic Browser Employer",
                normalized_name="synthetic browser employer",
                organization_type="EMPLOYER",
            )
            db.add(employer)
            db.flush()
            db.add(Partnership(organization_id=employer.id, mou_required=True))
            vacancy = Vacancy(
                vacancy_code="VAC-BROWSER-FIXTURE",
                organization_id=employer.id,
                title="Read-only Browser Vacancy",
                status="ACTIVE",
                required_headcount=10,
            )
            db.add(vacancy)
            for projection in ("desktop", "mobile"):
                db.add(
                    Training(
                        training_code="TRN-BROWSER-" + projection.upper(),
                        title="Browser Training " + projection,
                        training_type="EMPLOYABILITY",
                        trainer_type="INTERNAL",
                        mode="IN_PERSON",
                        start_date=date(2026, 10, 20),
                        location_region_code="GREATER_ACCRA",
                        location_district_code="ACCRA_METROPOLITAN",
                        location_community="Accra",
                        modules_json=["CV preparation"],
                        status="PLANNED",
                    )
                )
            matching_owner = db.scalar(select(User).where(User.email == "matching@example.org"))
            assert matching_owner
            confirm_permission = db.scalar(
                select(Permission).where(Permission.code == "placement:confirm")
            )
            assert confirm_permission
            matching_owner.overrides.append(
                PermissionOverride(permission_id=confirm_permission.id, effect="ALLOW")
            )
            for projection, phone in (("desktop", "0245555577"), ("mobile", "0245555588")):
                matching_person = Person(
                    first_name="Ama",
                    surname="Matching Fixture " + projection,
                    normalized_name="ama matching fixture " + projection,
                    phone_raw=phone,
                    phone_normalized="+233" + phone[1:],
                    community="Accra",
                )
                db.add(matching_person)
                db.flush()
                matching_participant = Participant(
                    person_id=matching_person.id,
                    participant_code="HAPPY-BROWSER-MATCHING-" + projection.upper(),
                    onboarding_status="COMPLETE",
                    completed_sections=["basic", "contact", "consent", "review"],
                    assigned_user_id=owner.id,
                )
                db.add(matching_participant)
                db.flush()
                db.add(
                    Consent(
                        participant_id=matching_participant.id,
                        consent_type="PROGRAMME",
                        status="ACTIVE",
                        consented_at=datetime.now(UTC),
                        method="STAFF_RECORDED",
                        privacy_notice_version="SYNTHETIC-E2E-NOTICE",
                    )
                )
                candidate = CandidateVacancy(
                    participant_id=matching_participant.id,
                    vacancy_id=vacancy.id,
                    owner_id=matching_owner.id,
                    owner_assigned_at=datetime.now(UTC),
                    status="POTENTIAL_MATCH",
                    source="STAFF",
                    priority="HIGH",
                    next_action="Review synthetic candidate",
                    next_action_due_at=datetime.now(UTC),
                    created_by=matching_owner.id,
                )
                db.add(candidate)
                db.flush()
                db.add(
                    CandidateHistory(
                        candidate_vacancy_id=candidate.id,
                        from_status=None,
                        to_status="POTENTIAL_MATCH",
                        actor_type="USER",
                        actor_id=str(matching_owner.id),
                    )
                )
                merl_person = Person(
                    first_name="Esi",
                    surname="MERL Fixture " + projection,
                    normalized_name="esi merl fixture " + projection,
                    phone_raw="02477777" + ("77" if projection == "desktop" else "88"),
                    phone_normalized="+2332477777" + ("77" if projection == "desktop" else "88"),
                    community="Accra",
                )
                db.add(merl_person)
                db.flush()
                merl_participant = Participant(
                    person_id=merl_person.id,
                    participant_code="HAPPY-BROWSER-MERL-" + projection.upper(),
                    onboarding_status="COMPLETE",
                    completed_sections=["basic", "contact", "consent", "review"],
                    assigned_user_id=owner.id,
                )
                db.add(merl_participant)
                db.flush()
                merl_candidate = CandidateVacancy(
                    participant_id=merl_participant.id,
                    vacancy_id=vacancy.id,
                    owner_id=matching_owner.id,
                    owner_assigned_at=datetime.now(UTC),
                    status="CONFIRMED_PLACEMENT",
                    source="STAFF",
                    priority="NORMAL",
                    submitted_at=datetime(2026, 9, 28, tzinfo=UTC),
                    selected_at=datetime(2026, 9, 30, tzinfo=UTC),
                    created_by=matching_owner.id,
                )
                db.add(merl_candidate)
                db.flush()
                db.add(
                    Placement(
                        placement_code="PLC-BROWSER-MERL-" + projection.upper(),
                        participant_id=merl_participant.id,
                        candidate_vacancy_id=merl_candidate.id,
                        organization_id=employer.id,
                        vacancy_id=vacancy.id,
                        status="CONFIRMED",
                        actual_start_date=date(2026, 10, 1),
                        confirmed_at=datetime(2026, 10, 5, tzinfo=UTC),
                        currently_working=True,
                        created_by=matching_owner.id,
                    )
                )
                placement_person = Person(
                    first_name="Kojo",
                    surname="Placement Fixture " + projection,
                    normalized_name="kojo placement fixture " + projection,
                    phone_raw="02466666" + ("77" if projection == "desktop" else "88"),
                    phone_normalized="+2332466666" + ("77" if projection == "desktop" else "88"),
                    community="Accra",
                )
                db.add(placement_person)
                db.flush()
                placement_participant = Participant(
                    person_id=placement_person.id,
                    participant_code="HAPPY-BROWSER-PLACEMENT-" + projection.upper(),
                    onboarding_status="COMPLETE",
                    completed_sections=["basic", "contact", "consent", "review"],
                    assigned_user_id=owner.id,
                )
                db.add(placement_participant)
                db.flush()
                selected = CandidateVacancy(
                    participant_id=placement_participant.id,
                    vacancy_id=vacancy.id,
                    owner_id=matching_owner.id,
                    owner_assigned_at=datetime.now(UTC),
                    status="SELECTED",
                    source="STAFF",
                    priority="NORMAL",
                    submitted_at=datetime.now(UTC),
                    selected_at=datetime.now(UTC),
                    created_by=matching_owner.id,
                )
                db.add(selected)
                db.flush()
                db.add(
                    CandidateHistory(
                        candidate_vacancy_id=selected.id,
                        from_status="EMPLOYER_DECISION",
                        to_status="SELECTED",
                        actor_type="USER",
                        actor_id=str(matching_owner.id),
                    )
                )
            db.commit()
            audit(db, "readiness.synthetic_actor", AuditActor("INTEGRATION", "HAMIS"))
            for projection in ("desktop", "mobile"):
                portal_data = PortalSubmission.model_validate(
                    {
                        "submissionId": "PS-BROWSER-" + projection.upper(),
                        "referenceNumber": "HP-EMP-2026-"
                        + ("90001" if projection == "desktop" else "90002"),
                        "companyName": "Portal Browser Employer " + projection,
                        "sector": "AGRICULTURE",
                        "companySize": "51-200",
                        "region": "GREATER_ACCRA",
                        "city": "Accra",
                        "contactName": "Portal Hiring Lead",
                        "contactRole": "HR Manager",
                        "contactPhone": "0247777701" if projection == "desktop" else "0247777702",
                        "contactEmail": f"portal-{projection}@example.org",
                        "consentAgreement": True,
                        "consentContact": True,
                        "signatureFileId": "synthetic-signature-" + projection,
                        "vacancies": [
                            {
                                "vacancyId": "PV-BROWSER-" + projection.upper(),
                                "jobTitle": "Portal Field Officer " + projection,
                                "location": "Accra",
                                "employmentType": "FULL_TIME",
                                "openings": 3,
                            }
                        ],
                    }
                )
                serialized = portal_data.model_dump(mode="json", by_alias=True)
                db.add(
                    EmployerSubmission(
                        external_submission_id=portal_data.submission_id,
                        reference_number=portal_data.reference_number,
                        payload_hash=hashlib.sha256(
                            json.dumps(
                                serialized,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode()
                        ).hexdigest(),
                        payload_ciphertext=encrypt_portal_submission(portal_data),
                        company_name=portal_data.company_name,
                        vacancy_count=len(portal_data.vacancies),
                    )
                )
            db.commit()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        api_url = f"http://127.0.0.1:{port}"
        environment = {
            **os.environ,
            "DATABASE_URL": url,
            "APP_ENV": "test",
            "API_CORS_ORIGINS": json.dumps(
                [
                    "http://127.0.0.1:3100",
                    f"http://127.0.0.1:{int(os.environ.get('HAPPY_INTAKE_TEST_PORT', '8765'))}",
                ]
            ),
            "AUTH_IP_LIMIT": "100",
            "SUPPLY_ONBOARDING_POLICY_APPROVED": "true",
            "SUPPLY_PRIVACY_NOTICE_VERSION": "SYNTHETIC-E2E-NOTICE",
            "SUPPLY_PRIVACY_NOTICE_TEXT": "Synthetic test privacy notice; not programme policy.",
            "EMPLOYER_INTAKE_NOTICE_TEXT": "Synthetic test employer notice; not programme policy.",
            "SUPPLY_REQUIRED_SECTIONS": '["basic","contact","consent","review"]',
            "SUPPLY_REQUIRED_FIELDS": "[]",
            "FILE_SCAN_HOST": "",
            "IDENTITY_ENCRYPTION_KEY": encryption_key,
        }
        directory = PROJECT_ROOT / ".local" / "e2e"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{schema}.log").open("ab") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=API_ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=creation_flags(detached=True),
                start_new_session=os.name != "nt",
            )
            worker = subprocess.Popen(
                [sys.executable, "-m", "app.workers.operations"],
                cwd=API_ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=creation_flags(detached=True),
                start_new_session=os.name != "nt",
            )
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(api_url + "/api/v1/health/live", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Synthetic browser API did not start.") from None
                time.sleep(0.2)
        print(
            json.dumps(
                {
                    "schema": schema,
                    "pid": process.pid,
                    "worker_pid": worker.pid,
                    "api_url": api_url,
                    "password": password,
                }
            )
        )
    except Exception:
        if worker:
            worker.terminate()
            worker.wait(timeout=10)
        if process:
            process.terminate()
            process.wait(timeout=10)
        cleanup_documents(engine)
        cleanup_intake_documents(engine)
        cleanup_report_exports(engine)
        drop_test_schema(schema)
        raise
    finally:
        engine.dispose()


def stop() -> None:
    state = json.loads(sys.stdin.read())
    try:
        worker = psutil.Process(state["worker_pid"])
        if "app.workers.operations" not in worker.cmdline() or worker.cwd() != str(API_ROOT):
            raise ValueError("Browser worker PID does not identify this project's process.")
        worker.terminate()
        worker.wait(timeout=15)
    except psutil.NoSuchProcess:
        pass
    try:
        process = psutil.Process(state["pid"])
        if "app.main:app" not in process.cmdline() or process.cwd() != str(API_ROOT):
            raise ValueError("Browser API PID does not identify this project's process.")
        process.terminate()
        process.wait(timeout=15)
    except psutil.NoSuchProcess:
        pass
    engine = create_engine(test_schema_url(state["schema"]))
    try:
        cleanup_documents(engine)
        cleanup_intake_documents(engine)
        cleanup_report_exports(engine)
    finally:
        engine.dispose()
    drop_test_schema(state["schema"])
    print("Synthetic browser API and test schema removed.")


if __name__ == "__main__":
    if sys.argv[1:] == ["start"]:
        start()
    elif sys.argv[1:] == ["stop"]:
        stop()
    else:
        raise SystemExit("Choose start or stop.")

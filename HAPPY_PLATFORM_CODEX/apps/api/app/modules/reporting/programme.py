"""Programme report projections over shared records, with explicit row grain."""

import io
import re
from datetime import date
from decimal import Decimal
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.demand.models import Organization
from app.modules.merl.models import Outcome
from app.modules.placement.models import EmploymentStatusHistory, Placement
from app.modules.supply.ages import event_age
from app.modules.supply.models import Education, Participant, Person, SensitiveProfile
from app.modules.training.models import Training, TrainingAttendance

ONBOARDING = [
    "Participant ID",
    "Onboarding Date",
    "Implementing Partner (or Sub-Partner)",
    "Region",
    "District",
    "Community",
    "Location Status",
    "Participant Type - Support",
    "Surname",
    "First Name",
    "Other Name(s)",
    "Sex",
    "Date of Birth",
    "Age",
    "Participant Type - Age",
    "Telephone (E.g. 0244111111)",
    "Ghana Card ID Number",
    "Voter's ID Number",
    "Refugee Status",
    'Nationality (If "Yes" to Refugee)',
    "Disability Status",
    "Specify Disability",
    "Education Level",
    "Employment Status",
    "Occupation",
    "Monthly Income",
]
CAPACITY = [
    "Participant ID",
    "Start Date",
    "End Date",
    "Training Location",
    "Participant Type - Support",
    "Surname",
    "First Name",
    "Other Name(s)",
    "Sex",
    "Date of Birth",
    "Age",
    "Participant Type - Age",
    "Telephone",
    "Agriculture Sector",
    "Good Agronomic and Production Practices",
    "Animal Husbundry & Health",
    "Post-Harvest Management and Value Addition",
    "Business/Marketing",
    "Financial Literacy",
    "Soft Skills",
    "Training/Skill Development Modules",
    "IT Skills",
    "Completion Status",
    "Certificate",
    "Training Partner",
    "Trainer Type",
]
EMPLOYMENT = [
    "Participant ID",
    "Start Date",
    "IP (Sub-Partner)",
    "Region",
    "District",
    "Community",
    "Location Status",
    "PT - Support",
    "Surname",
    "First Name",
    "Other Name(s)",
    "Sex",
    "Date of Birth",
    "Age",
    "Participant Type - Age",
    "Telephone",
    "Refugee Status",
    "Disability Status",
    "Specify Disability",
    "Baseline Employment Status",
    "Current Employment Status",
    "Agriculture Sector",
    "Job Type",
    "Farm Management Services",
    "Farm Size (Acres)",
    "Seed (Kg)",
    "Fertilizer (Kg)",
    "Crop Protection (Litre)",
    "Innoculant (g)",
    "Volumes Harvested",
    "Income (GHS)",
    "Employment Type",
    "Employment Category",
]
PLACEMENTS = [
    "PLACED BY PARTNER",
    "PLACEMENT START DATE",
    "PLACEMENT REGION",
    "PLACEMENT DISTRICT",
    "PLACEMENT COMMUNITY",
    "SECTOR",
    "INDUSTRY",
    "JOB TYPE",
    "JOB ROLE",
    "EMPLOYMENT TYPE",
    "EMPLOYMENT CATEGORY",
    "PLACEMENT INCOME",
    "PLACEMENT INCOME FREQ",
    "EMPLOYER NAME",
    "CONTRACT TYPE",
    "WORK HOURS",
]
HEADERS = {
    "1. Participant Onboarding": ONBOARDING,
    "2. Capacity Building": CAPACITY,
    "3. Employment": EMPLOYMENT,
    "Placements": PLACEMENTS,
}
AGRICULTURE_KEYS = [
    "sector",
    "farm_management_services",
    "farm_size_acres",
    "seed_kg",
    "fertilizer_kg",
    "crop_protection_litre",
    "inoculant_g",
    "volumes_harvested",
]
POLICY_NOTES = [
    "Age columns use onboarding, training-start and employment/placement-start dates respectively.",
    "Future onboarding or training reference dates produce projected ages.",
    "Module flags use received categories; the detail column lists the person's received topics.",
    "Current age is separate; programme age category and age-36 boundary await approval.",
    "Support-type Outreach and overlapping income bands await programme clarification.",
    "Onboarding: one participant; training: one enrolment; placements: one recruitment placement.",
    "Employment: confirmed placements with latest observations by period end; "
    "independent verified observations are separate rows.",
    "Independent observations are not confirmed placements and do not change placement KPIs.",
    "Blank means not recorded or restricted, never an inferred zero or No.",
    "GHS monthly income only; other currency/frequency conversions await approval.",
    "Identity numbers are blank unless explicitly included in an authorized sensitive export.",
    "WORK HOURS are hours per week. Placement rows link to participants in the Report Notes sheet.",
    "Exports are live revisions, not approved locked reporting periods.",
]


def bounded(db: Session, query: Any) -> list[Any]:
    rows = list(db.scalars(query.limit(5001)))
    if len(rows) > 5000:
        raise ApiError(
            422, "REPORT_TOO_LARGE", "Narrow the date range; maximum 5,000 records per section."
        )
    return rows


def monthly(
    amount: Any, frequency: str | None, currency: str = "GHS", status: str | None = None
) -> Any:
    if status == "UNKNOWN":
        return "Unknown"
    if status == "NOT_APPLICABLE":
        return "Not applicable"
    return amount if frequency == "MONTHLY" and currency == "GHS" else None


def build(
    db: Session, start: date, end: date, sensitive: bool = False, identity_numbers: bool = False
) -> dict[str, Any]:
    if identity_numbers and not sensitive:
        raise ApiError(422, "SENSITIVE_EXPORT_REQUIRED", "Identity export requires sensitive mode.")

    def identity(ciphertext: str | None) -> str | None:
        if not identity_numbers or not ciphertext:
            return None
        try:
            return (
                Fernet(settings.identity_encryption_key.get_secret_value().encode())
                .decrypt(ciphertext.encode())
                .decode()
            )
        except (ValueError, InvalidToken):
            raise ApiError(
                503,
                "IDENTITY_EXPORT_UNAVAILABLE",
                "Protected identity export could not be completed.",
            ) from None

    people: dict[Any, tuple[Participant, Person]] = {
        participant.id: (participant, person)
        for participant, person in db.execute(
            select(Participant, Person)
            .join(Person, Person.id == Participant.person_id)
            .where(Participant.archived_at.is_(None))
        )
    }
    profiles = (
        {p.participant_id: p for p in db.scalars(select(SensitiveProfile))} if sensitive else {}
    )
    education = {
        p.participant_id: p.education_level
        for p in db.scalars(
            select(Education)
            .where(Education.archived_at.is_(None))
            .order_by(Education.is_highest, Education.created_at)
        )
    }
    partners = {p.id: p.name for p in db.scalars(select(Organization))}
    sheets: dict[str, list[list[Any]]] = {name: [] for name in HEADERS}
    participants: set[Any] = set()
    dqa = []

    def quality(participant: Participant, issue: str) -> None:
        dqa.append(
            {
                "participant_id": str(participant.id),
                "participant_code": participant.participant_code,
                "issue": issue,
            }
        )

    def common(participant: Participant, person: Person, reference: date | None) -> list[Any]:
        return [
            person.surname,
            person.first_name,
            person.other_names,
            person.sex if sensitive else None,
            person.date_of_birth if sensitive else None,
            event_age(person.date_of_birth, reference) if sensitive else None,
            None,
            person.phone_raw,
        ]

    for participant, person in people.values():
        # Missing dates cannot be placed in a period; expose actionable DQA instead.
        if participant.onboarding_date is None:
            quality(participant, "Missing Onboarding Date; excluded from dated onboarding export")
        if not (person.government_id_type == "GHANA_CARD" and person.government_id_ciphertext):
            quality(participant, "Ghana Card required before onboarding completion")
        if (
            participant.onboarding_date
            and person.date_of_birth
            and participant.onboarding_date < person.date_of_birth
        ):
            quality(participant, "Onboarding Date is before Date of Birth")
        if not participant.onboarding_date or not start <= participant.onboarding_date <= end:
            continue
        participants.add(participant.id)
        profile = profiles.get(participant.id)
        sheets["1. Participant Onboarding"].append(
            [
                participant.participant_code,
                participant.onboarding_date,
                participant.implementing_partner,
                person.region_code,
                person.district_code,
                person.community,
                person.location_status,
                participant.support_type,
                *common(participant, person, participant.onboarding_date),
                identity(person.government_id_ciphertext)
                if person.government_id_type == "GHANA_CARD"
                else None,
                identity(person.voter_id_ciphertext),
                profile.refugee_status if profile else None,
                person.nationality if sensitive else None,
                profile.disability_status if profile else None,
                profile.disability_specify if profile else None,
                education.get(participant.id),
                participant.baseline_employment_status,
                participant.baseline_occupation,
                monthly(
                    profile.baseline_income_amount,
                    profile.baseline_income_frequency,
                    status=profile.baseline_income_status,
                )
                if profile
                else None,
            ]
        )
    enrolments = bounded(
        db,
        select(TrainingAttendance)
        .join(Training)
        .where(
            TrainingAttendance.archived_at.is_(None),
            Training.archived_at.is_(None),
            Training.start_date >= start,
            Training.start_date <= end,
        )
        .order_by(Training.start_date, TrainingAttendance.id),
    )
    for enrolment in enrolments:
        if enrolment.participant_id not in people:
            continue
        participant, person = people[enrolment.participant_id]
        training = db.get(Training, enrolment.training_id)
        assert training
        participants.add(participant.id)
        received = {module.strip().casefold() for module in enrolment.received_modules}
        module_values = [
            "Yes" if label.replace("Husbundry", "Husbandry").casefold() in received else None
            for label in CAPACITY[14:22]
        ]
        module_values[6] = "; ".join(enrolment.received_modules) or None
        sheets["2. Capacity Building"].append(
            [
                participant.participant_code,
                training.start_date,
                training.end_date,
                training.location_text or training.location_community,
                participant.support_type,
                *common(participant, person, training.start_date),
                training.agriculture_sector,
                *module_values,
                "Yes"
                if enrolment.completion_status == "COMPLETED"
                else "No"
                if enrolment.completion_status == "NOT_COMPLETED"
                else None,
                "Yes" if enrolment.certificate_issued else "No",
                partners.get(training.partner_organization_id)
                if training.partner_organization_id
                else None,
                "Internal" if training.trainer_type == "INTERNAL" else "External",
            ]
        )
    placements = bounded(
        db,
        select(Placement)
        .where(
            Placement.archived_at.is_(None),
            Placement.actual_start_date >= start,
            Placement.actual_start_date <= end,
        )
        .order_by(Placement.actual_start_date, Placement.id),
    )
    links = []
    for placement in placements:
        if placement.participant_id not in people:
            continue
        participant, person = people[placement.participant_id]
        participants.add(participant.id)
        sheets["Placements"].append(
            [
                placement.placed_by_partner,
                placement.actual_start_date,
                placement.placement_region,
                placement.placement_district,
                placement.placement_community,
                placement.sector,
                placement.industry,
                placement.job_type,
                placement.job_role,
                placement.employment_type,
                placement.employment_category,
                placement.salary_amount if sensitive else None,
                placement.salary_frequency,
                placement.employer_name or partners.get(placement.organization_id),
                placement.contract_type,
                placement.work_hours,
            ]
        )
        links.append(
            [
                len(sheets["Placements"]) + 1,
                participant.participant_code,
                placement.placement_code,
                placement.salary_currency,
                placement.work_hours_period,
            ]
        )
        if placement.confirmed_at is None or placement.confirmed_at.date() > end:
            quality(participant, "Placement start recorded; first income is not yet verified")
            continue
        observation = db.scalar(
            select(Outcome)
            .where(
                Outcome.placement_id == placement.id,
                Outcome.archived_at.is_(None),
                Outcome.as_of_date <= end,
            )
            .order_by(Outcome.as_of_date.desc(), Outcome.created_at.desc(), Outcome.id.desc())
            .limit(1)
        )
        working_event = db.scalar(
            select(EmploymentStatusHistory)
            .where(
                EmploymentStatusHistory.placement_id == placement.id,
                EmploymentStatusHistory.effective_date <= end,
            )
            .order_by(
                EmploymentStatusHistory.effective_date.desc(),
                EmploymentStatusHistory.created_at.desc(),
                EmploymentStatusHistory.id.desc(),
            )
            .limit(1)
        )
        append_employment(
            sheets,
            participant,
            person,
            profiles.get(participant.id),
            placement.actual_start_date,
            observation,
            placement,
            sensitive,
            common,
            working_event.status == "WORKING" if working_event else None,
        )
    observations = bounded(
        db,
        select(Outcome)
        .where(
            Outcome.placement_id.is_(None),
            Outcome.archived_at.is_(None),
            Outcome.as_of_date >= start,
            Outcome.as_of_date <= end,
        )
        .order_by(Outcome.as_of_date, Outcome.id),
    )
    for observation in observations:
        if observation.participant_id not in people:
            continue
        participant, person = people[observation.participant_id]
        participants.add(participant.id)
        append_employment(
            sheets,
            participant,
            person,
            profiles.get(participant.id),
            observation.employment_start_date,
            observation,
            None,
            sensitive,
            common,
        )
    if any(len(rows) > 5000 for rows in sheets.values()):
        raise ApiError(
            422, "REPORT_TOO_LARGE", "Narrow the date range; maximum 5,000 rows per sheet."
        )
    return {
        "sheets": sheets,
        "placement_links": links,
        "issues": dqa,
        "counts": {
            "distinct_participants": len(participants),
            "onboarding_records": len(sheets["1. Participant Onboarding"]),
            "training_enrolments": len(enrolments),
            "placement_records": len(placements),
            "employment_rows": len(sheets["3. Employment"]),
        },
        "notes": POLICY_NOTES,
    }


def append_employment(
    sheets: dict[str, list[list[Any]]],
    participant: Participant,
    person: Person,
    profile: SensitiveProfile | None,
    reference: date | None,
    observation: Outcome | None,
    placement: Placement | None,
    sensitive: bool,
    common: Any,
    placement_working: bool | None = None,
) -> None:
    agriculture = observation.agriculture if observation else {}
    sheets["3. Employment"].append(
        [
            participant.participant_code,
            reference,
            participant.implementing_partner,
            person.region_code,
            person.district_code,
            person.community,
            person.location_status,
            participant.support_type,
            *common(participant, person, reference),
            profile.refugee_status if profile else None,
            profile.disability_status if profile else None,
            profile.disability_specify if profile else None,
            participant.baseline_employment_status,
            "Yes"
            if observation and observation.currently_working
            else "No"
            if observation
            else "Yes"
            if placement_working is True
            else "No"
            if placement_working is False
            else None,
            agriculture.get("sector"),
            observation.job_type if observation else placement.job_type if placement else None,
            *[agriculture.get(key) for key in AGRICULTURE_KEYS[1:]],
            monthly(
                observation.current_income_amount,
                observation.income_frequency,
                status=observation.income_status,
            )
            if observation and sensitive
            else monthly(
                placement.salary_amount, placement.salary_frequency, placement.salary_currency
            )
            if placement and sensitive
            else None,
            observation.employment_type
            if observation
            else placement.employment_type
            if placement
            else None,
            observation.employment_category
            if observation
            else placement.employment_category
            if placement
            else None,
        ]
    )


def workbook(result: dict[str, Any]) -> bytes:
    """Inline-string OOXML: entered text cannot execute spreadsheet formulas."""
    output = io.BytesIO()
    sheets = {name: [HEADERS[name], *rows] for name, rows in result["sheets"].items()}
    sheets["Report Notes"] = [
        ["Report notes"],
        *[[note] for note in result["notes"]],
        [
            "Placement sheet row",
            "Participant ID",
            "Placement ID",
            "Income currency",
            "Hours period",
        ],
        *result["placement_links"],
        ["Participant ID", "Data quality issue"],
        *[[issue["participant_code"], issue["issue"]] for issue in result["issues"]],
    ]
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    office = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    types = Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    SubElement(
        types,
        "Default",
        Extension="rels",
        ContentType="application/vnd.openxmlformats-package.relationships+xml",
    )
    SubElement(types, "Default", Extension="xml", ContentType="application/xml")
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml."
    SubElement(types, "Override", PartName="/xl/workbook.xml", ContentType=mime + "sheet.main+xml")
    relationships = Element("Relationships", xmlns=rel)
    SubElement(
        relationships,
        "Relationship",
        Id="rId1",
        Type=office + "/officeDocument",
        Target="xl/workbook.xml",
    )
    book = Element("workbook", {"xmlns": main, "xmlns:r": office})
    sheet_list = SubElement(book, "sheets")
    book_rel = Element("Relationships", xmlns=rel)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for index, (name, rows) in enumerate(sheets.items(), 1):
            part = f"worksheets/sheet{index}.xml"
            SubElement(
                types, "Override", PartName="/xl/" + part, ContentType=mime + "worksheet+xml"
            )
            SubElement(
                sheet_list, "sheet", name=name, sheetId=str(index), attrib={"r:id": f"rId{index}"}
            )
            SubElement(
                book_rel, "Relationship", Id=f"rId{index}", Type=office + "/worksheet", Target=part
            )
            sheet = Element("worksheet", xmlns=main)
            views = SubElement(sheet, "sheetViews")
            view = SubElement(views, "sheetView", workbookViewId="0")
            SubElement(view, "pane", ySplit="1", topLeftCell="A2", state="frozen")
            cols = SubElement(sheet, "cols")
            SubElement(cols, "col", min="1", max=str(len(rows[0])), width="24", customWidth="1")
            data = SubElement(sheet, "sheetData")
            for number, row in enumerate(rows, 1):
                xml_row = SubElement(data, "row", r=str(number))
                if number == 1:
                    xml_row.set("ht", "60")
                    xml_row.set("customHeight", "1")
                for value in row:
                    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                        numeric = SubElement(xml_row, "c", t="n")
                        SubElement(numeric, "v").text = str(value)
                        continue
                    cell = SubElement(xml_row, "c", t="inlineStr")
                    if number == 1:
                        cell.set("s", "1")
                    text = SubElement(SubElement(cell, "is"), "t")
                    text.text = re.sub(
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value) if value is not None else ""
                    )
            archive.writestr("xl/" + part, tostring(sheet, encoding="utf-8", xml_declaration=True))
        styles = Element("styleSheet", xmlns=main)
        fonts = SubElement(styles, "fonts", count="2")
        for bold in (False, True):
            font = SubElement(fonts, "font")
            SubElement(font, "sz", val="11")
            SubElement(font, "name", val="Arial")
            if bold:
                SubElement(font, "b")
                SubElement(font, "color", rgb="FFFFFFFF")
        fills = SubElement(styles, "fills", count="3")
        for pattern in ("none", "gray125", "solid"):
            fill = SubElement(SubElement(fills, "fill"), "patternFill", patternType=pattern)
            if pattern == "solid":
                SubElement(fill, "fgColor", rgb="FF004AB9")
        SubElement(SubElement(styles, "borders", count="1"), "border")
        SubElement(
            SubElement(styles, "cellStyleXfs", count="1"),
            "xf",
            numFmtId="0",
            fontId="0",
            fillId="0",
            borderId="0",
        )
        formats = SubElement(styles, "cellXfs", count="2")
        SubElement(formats, "xf", numFmtId="0", fontId="0", fillId="0", borderId="0", xfId="0")
        header = SubElement(
            formats,
            "xf",
            numFmtId="0",
            fontId="1",
            fillId="2",
            borderId="0",
            xfId="0",
            applyAlignment="1",
        )
        SubElement(header, "alignment", wrapText="1", vertical="center")
        SubElement(
            SubElement(styles, "cellStyles", count="1"),
            "cellStyle",
            name="Normal",
            xfId="0",
            builtinId="0",
        )
        SubElement(types, "Override", PartName="/xl/styles.xml", ContentType=mime + "styles+xml")
        SubElement(
            book_rel, "Relationship", Id="styles", Type=office + "/styles", Target="styles.xml"
        )
        archive.writestr("xl/styles.xml", tostring(styles, encoding="utf-8", xml_declaration=True))
        for path, element in (
            ("[Content_Types].xml", types),
            ("_rels/.rels", relationships),
            ("xl/workbook.xml", book),
            ("xl/_rels/workbook.xml.rels", book_rel),
        ):
            archive.writestr(path, tostring(element, encoding="utf-8", xml_declaration=True))
    return output.getvalue()

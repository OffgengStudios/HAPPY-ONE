import io
import struct
import zipfile
from datetime import date

import pytest
from pydantic import ValidationError
from pypdf import PdfWriter

from app.core.config import settings
from app.core.errors import ApiError
from app.modules.supply import files, schemas
from app.modules.supply.service import age


def pdf_bytes():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    return output.getvalue()


def test_age_is_derived_and_accounts_for_birthday():
    assert age(None) is None
    assert age(date(2000, 10, 8), date(2026, 10, 7)) == 25
    assert age(date(2000, 10, 7), date(2026, 10, 7)) == 26


@pytest.mark.parametrize(
    "extra",
    [
        {"phone_raw": "123"},
        {"first_name": ""},
        {"community": ""},
        {"source_system": "HAMIS"},
        {"onboarding_status": "COMPLETE"},
        {"hamis_id": "external"},
    ],
)
def test_intake_validation_and_mass_assignment(extra):
    with pytest.raises(ValidationError):
        schemas.Intake.model_validate(
            {
                "first_name": "Synthetic",
                "surname": "Person",
                "phone_raw": "0241234567",
                "community": "Accra",
                **extra,
            }
        )


@pytest.mark.parametrize(
    "schema,values",
    [
        (
            schemas.SensitiveWrite,
            {"version": 1, "current_income_amount": -1, "income_frequency": "MONTHLY"},
        ),
        (schemas.SensitiveWrite, {"version": 1, "current_income_amount": 100}),
        (
            schemas.EducationFields,
            {"education_level": "Secondary", "start_year": 2020, "end_year": 2019},
        ),
        (
            schemas.ExperienceFields,
            {
                "employer_name": "Test",
                "role_title": "Test",
                "start_date": "2020-01-01",
                "end_date": "2019-01-01",
            },
        ),
        (
            schemas.Assignment,
            {"version": 1, "reason": "Test", "next_action_due_at": "2026-01-01T00:00:00Z"},
        ),
        (
            schemas.ConsentWrite,
            {
                "version": 1,
                "consent_type": "PROGRAMME",
                "consented_at": "2099-01-01T00:00:00Z",
                "method": "VERBAL",
                "privacy_notice_version": "test",
                "participant_agreed": True,
            },
        ),
    ],
)
def test_section_validation(schema, values):
    with pytest.raises(ValidationError):
        schema.model_validate(values)


def test_pdf_filename_validation_and_size_limit(monkeypatch):
    data = pdf_bytes()
    assert files.validate_file(data, r"C:\fakepath\cv.pdf", files.PDF) == ("cv.pdf", files.PDF)
    for filename, mime, content in [
        ("cv.exe", files.PDF, data),
        ("cv.pdf", files.DOCX, data),
        ("cv.pdf", files.PDF, b"%PDF-invalid"),
        ("bad\n.pdf", files.PDF, data),
    ]:
        with pytest.raises(ApiError) as error:
            files.validate_file(content, filename, mime)
        assert error.value.code == "FILE_TYPE_NOT_ALLOWED"
    monkeypatch.setattr(settings, "file_max_bytes", 5)
    with pytest.raises(ApiError) as error:
        files.validate_file(data, "cv.pdf", files.PDF)
    assert error.value.status == 413


def test_docx_rejects_macros_and_path_traversal():
    for forbidden in ["word/vbaProject.bin", "../payload", "/payload"]:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr("word/document.xml", "<document />")
            archive.writestr(forbidden, "synthetic")
        with pytest.raises(ApiError):
            files.validate_file(output.getvalue(), "cv.docx", files.DOCX)


def test_docx_requires_real_xml_and_rejects_entity_declarations():
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body /></w:document>"
    )
    types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Override PartName="/word/document.xml" ContentType="' + files.DOCX_MAIN + '" /></Types>'
    )
    for xml, valid in [
        (document, True),
        ("<not-a-document />", False),
        ("<!DOCTYPE document [<!ENTITY secret 'hidden'>]>" + document, False),
        ("not XML", False),
    ]:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("[Content_Types].xml", types)
            archive.writestr("word/document.xml", xml)
        if valid:
            assert files.validate_file(output.getvalue(), "cv.docx", files.DOCX) == (
                "cv.docx",
                files.DOCX,
            )
        else:
            with pytest.raises(ApiError):
                files.validate_file(output.getvalue(), "cv.docx", files.DOCX)


@pytest.mark.parametrize(
    "response,expected",
    [
        (b"stream: OK\0", "AVAILABLE"),
        (b"stream: Eicar-Test-Signature FOUND\0", "REJECTED"),
        (b"stream: error\0", "SCANNING"),
        (b"", "SCANNING"),
    ],
)
def test_scanner_protocol_and_fail_closed(monkeypatch, response, expected):
    class Connection:
        def __init__(self):
            self.sent = bytearray()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def sendall(self, content):
            self.sent.extend(content)

        def recv(self, size):
            return response

    connection = Connection()
    monkeypatch.setattr(settings, "file_scan_host", "scanner.invalid")
    monkeypatch.setattr(files.socket, "create_connection", lambda *args, **kwargs: connection)
    assert files.scan(b"test") == expected
    assert connection.sent == b"zINSTREAM\0" + struct.pack("!I", 4) + b"test" + struct.pack("!I", 0)


def test_unconfigured_and_unreachable_scanner_never_marks_available(monkeypatch):
    monkeypatch.setattr(settings, "file_scan_host", "")
    assert files.scan(b"synthetic") == "SCANNING"
    monkeypatch.setattr(settings, "file_scan_host", "scanner.invalid")

    def unavailable(*args, **kwargs):
        raise OSError("Synthetic failure")

    monkeypatch.setattr(files.socket, "create_connection", unavailable)
    assert files.scan(b"synthetic") == "SCANNING"

import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.integrations.cv_parser import adapter
from app.integrations.cv_parser.adapter import HttpCvParser, ParserUnavailable

PARSER_URL = "https://parser.example.test/api/v1/integrations/happy/parse"
PARSER_TOKEN = "test-parser-token-with-at-least-thirty-two-characters"


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


@pytest.fixture
def configure_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cv_parser_url", PARSER_URL)
    monkeypatch.setattr(settings, "cv_parser_token", SecretStr(PARSER_TOKEN))


def test_http_adapter_uses_and_accepts_the_happy_parser_contract(
    configure_parser: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_body = json.dumps(
        {
            "schema_version": "1",
            "provider": "happy-cv-parser",
            "model": "extraction-classifier-v1",
            "suggestions": [
                {"field": "email", "value": "candidate@example.org"},
                {
                    "field": "skills",
                    "value": ["Customer service", "Excel"],
                    "confidence": 0.91,
                },
            ],
        }
    ).encode()
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(response_body)

    monkeypatch.setattr(adapter, "urlopen", fake_urlopen)
    result = HttpCvParser().parse(b"synthetic cv", "application/pdf", "candidate.pdf")

    request = captured["request"]
    assert isinstance(request, Request)
    body = json.loads(request.data or b"{}")
    assert request.full_url == PARSER_URL
    assert request.get_header("Authorization") == f"Bearer {PARSER_TOKEN}"
    assert body["filename"] == "candidate.pdf"
    assert body["mime_type"] == "application/pdf"
    assert captured["timeout"] == settings.cv_parser_timeout_seconds
    assert result.provider == "happy-cv-parser"
    assert [(item.field, item.value) for item in result.suggestions] == [
        ("email", "candidate@example.org"),
        ("skills", ["Customer service", "Excel"]),
    ]


def test_http_adapter_rejects_malformed_parser_responses(
    configure_parser: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapter,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b'{"suggestions": []}'),
    )

    with pytest.raises(ValueError, match="invalid response contract"):
        HttpCvParser().parse(b"synthetic cv", "application/pdf", "candidate.pdf")


def test_http_adapter_rejects_oversized_parser_responses(
    configure_parser: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adapter, "urlopen", lambda *args, **kwargs: FakeResponse(b" " * 524289))

    with pytest.raises(ValueError, match="exceeds the allowed size"):
        HttpCvParser().parse(b"synthetic cv", "application/pdf", "candidate.pdf")


def test_http_adapter_treats_transport_errors_as_retryable(
    configure_parser: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = HTTPError(PARSER_URL, 503, "Unavailable", {}, BytesIO(b""))

    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(adapter, "urlopen", fail_urlopen)

    with pytest.raises(ParserUnavailable):
        HttpCvParser().parse(b"synthetic cv", "application/pdf", "candidate.pdf")

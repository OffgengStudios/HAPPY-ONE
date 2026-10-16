import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


@dataclass(frozen=True)
class ParserSuggestion:
    field: str
    value: Any
    confidence: float | None = None


@dataclass(frozen=True)
class ParserOutput:
    suggestions: tuple[ParserSuggestion, ...]
    provider: str
    model: str | None = None


class CvParser(Protocol):
    def parse(self, content: bytes, mime_type: str, filename: str) -> ParserOutput: ...


class ParserUnavailable(RuntimeError):
    """Raised when no real parser transport has been configured."""


class UnavailableCvParser:
    def parse(self, content: bytes, mime_type: str, filename: str) -> ParserOutput:
        del content, mime_type, filename
        raise ParserUnavailable("The CV parser provider is not configured.")


class HttpCvParser:
    def parse(self, content: bytes, mime_type: str, filename: str) -> ParserOutput:
        payload = json.dumps(
            {
                "filename": filename,
                "mime_type": mime_type,
                "content_base64": base64.b64encode(content).decode(),
            }
        ).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        token = settings.cv_parser_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with urlopen(
                Request(settings.cv_parser_url, data=payload, headers=headers, method="POST"),
                timeout=settings.cv_parser_timeout_seconds,
            ) as response:
                result = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ParserUnavailable("The CV parser service is unavailable.") from error
        suggestions = result.get("suggestions")
        if not isinstance(suggestions, list):
            raise ValueError("Parser response does not contain suggestions.")
        return ParserOutput(
            suggestions=tuple(
                ParserSuggestion(
                    field=item["field"],
                    value=item.get("value"),
                    confidence=item.get("confidence"),
                )
                for item in suggestions
                if isinstance(item, dict) and isinstance(item.get("field"), str)
            ),
            provider=str(result.get("provider") or settings.cv_parser_provider or "HTTP"),
            model=str(result.get("model") or settings.cv_parser_model) or None,
        )


def get_cv_parser() -> CvParser:
    return HttpCvParser() if settings.cv_parser_url else UnavailableCvParser()

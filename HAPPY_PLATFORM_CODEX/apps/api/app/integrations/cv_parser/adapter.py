import base64
import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import settings


class SuggestionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal[
        "first_name",
        "surname",
        "other_names",
        "phone_raw",
        "email",
        "job_role",
        "sector_code",
        "industry_code",
        "skills",
    ]
    value: str | list[str]
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def bounded_value(self) -> "SuggestionContract":
        if self.field == "skills":
            if (
                not isinstance(self.value, list)
                or not 1 <= len(self.value) <= 100
                or any(not value.strip() or len(value) > 150 for value in self.value)
            ):
                raise ValueError("Invalid skills suggestion.")
        elif not isinstance(self.value, str) or not self.value.strip() or len(self.value) > 254:
            raise ValueError("Invalid scalar suggestion.")
        return self


class ParserResponseContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"
    provider: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    suggestions: list[SuggestionContract] = Field(min_length=1, max_length=9)


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
                Request(
                    settings.cv_parser_url
                    or f"http://{settings.cv_parser_hostport}/api/v1/integrations/happy/parse",
                    data=payload,
                    headers=headers,
                    method="POST",
                ),
                timeout=settings.cv_parser_timeout_seconds,
            ) as response:
                raw = response.read(524289)
                if len(raw) > 524288:
                    raise ValueError("Parser response exceeds the allowed size.")
                result = ParserResponseContract.model_validate_json(raw)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ParserUnavailable("The CV parser service is unavailable.") from error
        except ValidationError:
            raise ValueError("The parser returned an invalid response contract.") from None
        if len({item.field for item in result.suggestions}) != len(result.suggestions):
            raise ValueError("The parser returned duplicate fields.")
        return ParserOutput(
            suggestions=tuple(
                ParserSuggestion(
                    field=item.field,
                    value=item.value,
                    confidence=item.confidence,
                )
                for item in result.suggestions
            ),
            provider=result.provider,
            model=result.model,
        )


def get_cv_parser() -> CvParser:
    return (
        HttpCvParser()
        if settings.cv_parser_url or settings.cv_parser_hostport
        else UnavailableCvParser()
    )

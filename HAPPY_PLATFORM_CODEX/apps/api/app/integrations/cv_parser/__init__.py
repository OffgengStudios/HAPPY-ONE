"""CV parser adapter boundary; parser output is advisory until staff review."""

from app.integrations.cv_parser.adapter import (
    CvParser,
    ParserOutput,
    ParserSuggestion,
    UnavailableCvParser,
    get_cv_parser,
)

__all__ = [
    "CvParser",
    "ParserOutput",
    "ParserSuggestion",
    "UnavailableCvParser",
    "get_cv_parser",
]

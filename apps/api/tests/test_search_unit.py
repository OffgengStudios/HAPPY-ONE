import pytest
from pydantic import ValidationError

from app.core.errors import ApiError
from app.modules.iam.actors import AuditActor
from app.modules.search.schemas import SearchRequest
from app.modules.search.service import search


@pytest.mark.parametrize(
    "fields",
    [
        {"q": ""},
        {"q": "x"},
        {"q": "x" * 201},
        {"q": "ab\x00cd"},
        {"q": "ab\ncd"},
        {"q": "ab\x7fcd"},
        {"q": "ab", "limit": 0},
        {"q": "ab", "limit": 101},
        {"q": "ab", "entities": []},
        {"q": "ab", "entities": ["HAMIS"]},
        {"q": "ab", "entities": ["PARTICIPANT", "PARTICIPANT"]},
        {"q": "ab", "entities": ["VACANCY"], "cursors": {"PARTICIPANT": "cursor"}},
        {"q": "ab", "permissions": ["participant:view"]},
    ],
)
def test_search_input_is_bounded_and_cannot_supply_authority(fields):
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(fields)


def test_search_strips_outer_whitespace_and_accepts_literal_pattern_characters():
    request = SearchRequest(q="  100%_Example\\  ")
    assert request.q == "100%_Example\\"
    assert request.limit == 25


def test_search_denies_before_accessing_database_when_no_resource_is_permitted():
    class Context:
        permissions: set[str] = set()
        audit_actor = AuditActor("SYSTEM")

    with pytest.raises(ApiError) as error:
        search(None, Context(), SearchRequest(q="example"))
    assert error.value.status == 403

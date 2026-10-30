import asyncio

import pytest

from app.core.config import settings
from app.core.middleware import RequestSizeMiddleware


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/participants/00000000-0000-4000-8000-000000000001/cv",
        "/api/v1/partnerships/00000000-0000-4000-8000-000000000001/documents",
        "/api/v1/vacancies/00000000-0000-4000-8000-000000000001/job-descriptions",
        "/api/v1/participant-intake",
        "/api/v1/employer-intake",
    ],
)
def test_chunked_upload_is_bounded_before_the_application(
    path: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "file_max_bytes", 1024)
    consumed = 0
    sent = []

    async def receive():
        nonlocal consumed
        consumed += 1
        assert consumed <= 6, "Upload body exceeded the documented multipart budget"
        return {"type": "http.request", "body": b"x" * 65536, "more_body": True}

    async def send(message):
        sent.append(message)

    async def downstream(scope, receive, send):
        raise AssertionError("Oversized streamed upload reached application code")

    asyncio.run(
        RequestSizeMiddleware(downstream)(
            {"type": "http", "method": "POST", "path": path, "headers": []}, receive, send
        )
    )
    assert sent[0]["status"] == 413
    assert b"FILE_TOO_LARGE" in sent[1]["body"]


def test_regular_json_write_retains_512_kib_limit(monkeypatch: pytest.MonkeyPatch):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"x" * (524288 + 1), "more_body": False}

    async def send(message):
        sent.append(message)

    async def downstream(scope, receive, send):
        raise AssertionError("Oversized JSON write reached the application")

    asyncio.run(
        RequestSizeMiddleware(downstream)(
            {"type": "http", "method": "POST", "path": "/api/v1/participants", "headers": []},
            receive,
            send,
        )
    )
    assert sent[0]["status"] == 413 and b"REQUEST_TOO_LARGE" in sent[1]["body"]

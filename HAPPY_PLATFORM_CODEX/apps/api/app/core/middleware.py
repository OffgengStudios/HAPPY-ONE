import json
import logging
import re
import time
from datetime import UTC, datetime
from uuid import uuid4

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.private_telemetry import METHODS
from app.core.version import RELEASE_VERSION

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
logger = logging.getLogger("happy.access")
SINGLE_FILE_UPLOAD = re.compile(
    r"/api/v1/(?:participants/[^/]+/cv|partnerships/[^/]+/documents|vacancies/[^/]+/job-descriptions)"
)
MULTIPART_FIELDS_BYTES = 262144
MULTIPART_OVERHEAD_BYTES = 65536


def record_request(request: Request, request_id: str, status: int, started: float) -> None:
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": "INFO",
                "service": "happy-api",
                "release_version": RELEASE_VERSION,
                "environment": settings.app_env,
                "request_id": request_id,
                "method": request.method if request.method in METHODS else "_OTHER",
                "route": getattr(request.scope.get("route"), "path", "<unmatched>"),
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            separators=(",", ":"),
        )
    )


class RequestSizeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        slots = 0
        if scope["method"] == "POST":
            if path == "/api/v1/employer-intake":
                slots = 5
            elif path == "/api/v1/participant-intake" or SINGLE_FILE_UPLOAD.fullmatch(path):
                slots = 1
        is_upload = slots > 0
        limit = (
            slots * settings.file_max_bytes + MULTIPART_FIELDS_BYTES + MULTIPART_OVERHEAD_BYTES
            if is_upload
            else 524288
        )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "FILE_TOO_LARGE" if is_upload else "REQUEST_TOO_LARGE",
                            "message": "The request exceeds the allowed size.",
                            "details": {},
                            "request_id": scope.get("state", {}).get("request_id"),
                        }
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        trace.get_current_span().set_attribute("happy.request_id", request_id)
        try:
            response = await call_next(request)
        except Exception:
            record_request(request, request_id, 500, started)
            raise
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/v1/participant-intake") or request.url.path.startswith(
            "/api/v1/employer-intake"
        ):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        record_request(request, request_id, response.status_code, started)
        return response

"""Keep request values out of secondary logs and the telemetry export boundary."""

import logging
from collections.abc import Sequence

from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import SpanContext, Status, TraceState

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE"}
METRIC_ATTRIBUTES = {
    "http.method",
    "http.request.method",
    "http.status_code",
    "http.response.status_code",
    "http.route",
    "http.scheme",
    "url.scheme",
    "network.protocol.version",
    "job_type",
    "status",
    "error_code",
    "operation",
}


class NoRawAccess(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return False


class SafeServerErrors(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info or record.exc_text or record.stack_info:
            record.msg = "Unhandled server failure; correlate the structured request log."
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


def configure_private_logging() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, NoRawAccess) for item in access.filters):
        access.addFilter(NoRawAccess())
    errors = logging.getLogger("uvicorn.error")
    if not any(isinstance(item, SafeServerErrors) for item in errors.filters):
        errors.addFilter(SafeServerErrors())
    structured = logging.getLogger("happy.access")
    if not structured.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        structured.addHandler(handler)
    structured.setLevel(logging.INFO)
    structured.propagate = False


def private_metric_views() -> list[View]:
    return [View(instrument_name="*", attribute_keys=METRIC_ATTRIBUTES)]


def private_context(context: SpanContext | None) -> SpanContext | None:
    if context is None:
        return None
    return SpanContext(
        trace_id=context.trace_id,
        span_id=context.span_id,
        is_remote=context.is_remote,
        trace_flags=context.trace_flags,
        trace_state=TraceState(),
    )


class PrivateSpanExporter(SpanExporter):
    def __init__(self, delegate: SpanExporter) -> None:
        self.delegate = delegate

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        safe = []
        for span in spans:
            original = span.attributes or {}
            attributes: dict[str, str | int] = {}
            for key in ("http.status_code", "http.response.status_code"):
                value = original.get(key)
                if isinstance(value, int) and 100 <= value <= 599:
                    attributes[key] = value
            method = original.get("http.request.method", original.get("http.method"))
            if isinstance(method, str):
                attributes["http.request.method"] = method if method in METHODS else "_OTHER"
            route = original.get("http.route")
            if isinstance(route, str):
                attributes["http.route"] = route
            correlation = original.get("happy.request_id")
            if isinstance(correlation, str):
                attributes["happy.request_id"] = correlation
            if original.get("db.system", original.get("db.system.name")) == "postgresql":
                attributes["db.system.name"] = "postgresql"
            # Names, events, links, exception descriptions, URLs, query strings,
            # SQL statements/parameters and request headers are not exported.
            name = "HTTP request" if method else "application operation"
            if isinstance(route, str):
                name = f"{attributes.get('http.request.method', 'HTTP')} {route}"
            elif "db.system.name" in attributes:
                name = "PostgreSQL operation"
            resource = Resource(
                {
                    key: value
                    for key, value in span.resource.attributes.items()
                    if key in {"service.name", "service.version", "deployment.environment.name"}
                }
            )
            safe.append(
                ReadableSpan(
                    name=name,
                    context=private_context(span.context),
                    parent=private_context(span.parent),
                    resource=resource,
                    attributes=attributes,
                    kind=span.kind,
                    status=Status(span.status.status_code),
                    start_time=span.start_time,
                    end_time=span.end_time,
                    instrumentation_scope=span.instrumentation_scope,
                )
            )
        return self.delegate.export(safe)

    def shutdown(self) -> None:
        self.delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.delegate.force_flush(timeout_millis)

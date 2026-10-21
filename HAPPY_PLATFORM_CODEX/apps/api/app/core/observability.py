from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings
from app.core.private_telemetry import PrivateSpanExporter, private_metric_views
from app.core.version import RELEASE_VERSION


def configure_observability(app: FastAPI) -> None:
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
    if not endpoint:
        return
    resource = Resource(
        {
            "service.name": "happy-api",
            "service.version": RELEASE_VERSION,
            "deployment.environment.name": settings.app_env,
        }
    )
    tracer = TracerProvider(resource=resource)
    tracer.add_span_processor(
        BatchSpanProcessor(
            PrivateSpanExporter(
                OTLPSpanExporter(
                    endpoint=endpoint + "/v1/traces",
                    headers=settings.otel_exporter_otlp_headers,
                )
            )
        )
    )
    trace.set_tracer_provider(tracer)
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=endpoint + "/v1/metrics",
            headers=settings.otel_exporter_otlp_headers,
        )
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[reader], views=private_metric_views())
    )
    SQLAlchemyInstrumentor().instrument()
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/api/v1/health/live",
        tracer_provider=tracer,
        meter_provider=metrics.get_meter_provider(),
    )

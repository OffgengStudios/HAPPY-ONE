from unittest.mock import Mock

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.core import operational_metrics
from app.core.operational_health import persist_state
from app.core.private_telemetry import private_metric_views


def test_metrics_export_only_bounded_aggregate_attributes(monkeypatch):
    monkeypatch.setattr(
        operational_metrics,
        "collected",
        lambda: {
            "database_available": 1,
            "scan_backlog": 2,
            "components": {
                "WORKER": {
                    "heartbeat_timestamp": 100,
                    "last_attempt_timestamp": 101,
                    "last_success_timestamp": 99,
                    "last_failure_timestamp": 0,
                    "consecutive_failures": 0,
                }
            },
            "queues": {
                "PARSER": {
                    "queued": 3,
                    "running": 1,
                    "failed": 2,
                    "succeeded": 4,
                    "oldest_queued_age_seconds": 20,
                    "stale_leases": 1,
                    "last_success_timestamp": 50,
                }
            },
        },
    )
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader], views=private_metric_views())
    operational_metrics.register(provider.get_meter("synthetic-operations"))
    data = reader.get_metrics_data()
    assert data is not None
    points = [
        point
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        for point in metric.data.data_points
    ]
    assert points
    assert all(set(point.attributes) <= {"job_type", "operation"} for point in points)
    assert all(
        value in {"WORKER", "PARSER"} for point in points for value in point.attributes.values()
    )
    provider.shutdown()


def test_checkpoint_failure_never_leaks_private_exception(monkeypatch, caplog):
    from app.core import operational_health

    monkeypatch.setattr(
        operational_health,
        "get_session_factory",
        Mock(side_effect=RuntimeError("SENTINEL-private-database-url")),
    )
    persist_state("WORKER", succeeded=False)
    assert "operational_checkpoint_unavailable" in caplog.text
    assert "SENTINEL" not in caplog.text

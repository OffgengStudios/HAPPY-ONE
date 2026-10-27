"""OTLP gauges with bounded attributes and one aggregate DB refresh per interval."""

import threading
import time
from collections.abc import Callable, Iterable
from typing import Any

from opentelemetry.metrics import CallbackOptions, Meter, Observation

from app.core.operational_health import snapshot
from app.db.session import get_session_factory

_lock = threading.Lock()
_cached: dict[str, Any] = {}
_expires = 0.0


def collected() -> dict[str, Any]:
    global _cached, _expires
    with _lock:
        if time.monotonic() < _expires:
            return _cached
        try:
            with get_session_factory()() as db:
                _cached = {**snapshot(db), "database_available": 1}
        except Exception:
            _cached = {"database_available": 0}
        _expires = time.monotonic() + 10
        return _cached


def register(meter: Meter) -> None:
    def scalar(key: str) -> Callable[[CallbackOptions], Iterable[Observation]]:
        def callback(options: CallbackOptions) -> Iterable[Observation]:
            data = collected()
            if key in data:
                yield Observation(data[key])

        return callback

    for key in (
        "database_available",
        "scan_backlog",
        "rejected_documents",
        "duplicate_reviews",
        "auth_failures_15m",
    ):
        meter.create_observable_gauge("happy.operations." + key, callbacks=[scalar(key)])

    def intake(options: CallbackOptions) -> Iterable[Observation]:
        for status, count in collected().get("intake_submissions", {}).items():
            if status in {"RECEIVED", "NEEDS_REVIEW", "APPLIED", "REJECTED"}:
                yield Observation(count, {"status": status})

    meter.create_observable_gauge("happy.intake.submissions", callbacks=[intake])

    def queue(field: str) -> Callable[[CallbackOptions], Iterable[Observation]]:
        def callback(options: CallbackOptions) -> Iterable[Observation]:
            for kind, values in collected().get("queues", {}).items():
                yield Observation(values[field], {"job_type": kind})

        return callback

    for field in (
        "queued",
        "running",
        "failed",
        "succeeded",
        "oldest_queued_age_seconds",
        "stale_leases",
        "last_success_timestamp",
    ):
        meter.create_observable_gauge("happy.jobs." + field, callbacks=[queue(field)])

    def checkpoint(field: str) -> Callable[[CallbackOptions], Iterable[Observation]]:
        def callback(options: CallbackOptions) -> Iterable[Observation]:
            for component, values in collected().get("components", {}).items():
                yield Observation(values[field], {"operation": component})

        return callback

    for field in (
        "heartbeat_timestamp",
        "last_attempt_timestamp",
        "last_success_timestamp",
        "last_failure_timestamp",
        "consecutive_failures",
    ):
        meter.create_observable_gauge("happy.checkpoint." + field, callbacks=[checkpoint(field)])

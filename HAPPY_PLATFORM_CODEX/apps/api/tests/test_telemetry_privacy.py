import gzip
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import psutil
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import SpanContext, Status, StatusCode

from app.core.config import API_ROOT
from app.core.private_telemetry import PrivateSpanExporter, private_metric_views


def test_real_otlp_wire_payload_drops_query_tokens_sql_and_exception_text() -> None:
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            message = ExportTraceServiceRequest.FromString(body)
            received.append(message)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    delegate = OTLPSpanExporter(endpoint=f"http://127.0.0.1:{server.server_port}/v1/traces")
    exporter = PrivateSpanExporter(delegate)
    sentinel = "SENTINEL-private-code-email-password"
    span = ReadableSpan(
        name=f"GET /callback?code={sentinel}",
        context=SpanContext(1, 2, False),
        resource=Resource({"service.name": "happy-api", "process.command_args": sentinel}),
        attributes={
            "url.full": f"https://example.org/callback?code={sentinel}",
            "http.target": f"/participants?q={sentinel}",
            "db.statement": sentinel,
            "exception.message": sentinel,
            "http.request.header.authorization": sentinel,
            "http.route": "/api/v1/participants/{identifier}",
            "http.method": "GET",
            "http.status_code": 500,
            "happy.request_id": "privacy-correlation-123",
        },
        events=[Event("exception", {"exception.message": sentinel})],
        status=Status(StatusCode.ERROR, sentinel),
        start_time=1,
        end_time=2,
    )
    try:
        assert exporter.export([span]) == SpanExportResult.SUCCESS
        assert len(received) == 1
        encoded = str(received[0])
        assert sentinel not in encoded
        assert "privacy-correlation-123" in encoded
        assert "/api/v1/participants/{identifier}" in encoded
        assert "ERROR" in encoded
    finally:
        exporter.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_metric_views_drop_identifiers_queries_and_other_unapproved_labels() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader], views=private_metric_views())
    try:
        counter = provider.get_meter("privacy-test").create_counter("http.requests")
        counter.add(
            1,
            {
                "http.method": "GET",
                "http.route": "/api/v1/participants",
                "url.full": "SENTINEL-query",
                "participant_id": "SENTINEL-person",
            },
        )
        data = reader.get_metrics_data()
        assert data is not None
        point = data.resource_metrics[0].scope_metrics[0].metrics[0].data.data_points[0]
        assert dict(point.attributes) == {
            "http.method": "GET",
            "http.route": "/api/v1/participants",
        }
        assert point.value == 1
    finally:
        provider.shutdown()


def test_actual_uvicorn_default_access_and_error_logs_never_echo_request_values(
    tmp_path: Path,
) -> None:
    wire = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            if self.path == "/v1/traces":
                wire.append(ExportTraceServiceRequest.FromString(body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    collector = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    collector_thread = threading.Thread(target=collector.serve_forever, daemon=True)
    collector_thread.start()
    module = tmp_path / "privacy_app.py"
    module.write_text(
        "from app.main import create_app\napp=create_app()\n"
        "@app.get('/privacy-error')\n"
        "def fail(): raise RuntimeError('SENTINEL-exception-message')\n",
        encoding="utf-8",
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(tmp_path), str(API_ROOT)]),
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{collector.server_port}",
        "OTEL_BSP_SCHEDULE_DELAY": "100",
    }
    log_path = tmp_path / "server.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "privacy_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=API_ROOT,
            env=environment,
            stdout=log,
            stderr=log,
        )
    try:
        url = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=url, timeout=5) as client:
            deadline = time.monotonic() + 30
            while True:
                try:
                    if client.get("/api/v1/health/live").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.1)
            for path, params in [
                ("/api/v1/participants", {"q": "SENTINEL-private-search"}),
                ("/api/v1/auth/sso/callback", {"code": "SENTINEL-auth-code", "state": "invalid"}),
                ("/api/v1/SENTINEL-unknown-path", {}),
                ("/privacy-error", {"token": "SENTINEL-secret-token"}),
            ]:
                client.get(path, params=params, headers={"X-Request-ID": "privacy-correlation-123"})
        output = log_path.read_text(encoding="utf-8")
        assert "SENTINEL" not in output
        records = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
        assert any(r["status"] == 500 for r in records)
        assert any(r["route"] == "<unmatched>" for r in records)
        assert any(r["route"].endswith("/participants") for r in records)
        for row in records:
            assert row["method"] == "GET" and row["duration_ms"] >= 0
            assert row["request_id"]
        assert any(r["request_id"] == "privacy-correlation-123" for r in records)
        deadline = time.monotonic() + 10
        while not any("privacy-correlation-123" in str(payload) for payload in wire):
            assert time.monotonic() < deadline, "Application OTLP spans did not arrive"
            time.sleep(0.1)
        assert "SENTINEL" not in "".join(str(payload) for payload in wire)
    finally:
        # The Windows venv launcher can have a distinct actual interpreter PID.
        try:
            children = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        for child in children:
            if child.cwd() == str(API_ROOT) and "privacy_app:app" in child.cmdline():
                child.terminate()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=15)
        collector.shutdown()
        collector.server_close()
        collector_thread.join(timeout=5)

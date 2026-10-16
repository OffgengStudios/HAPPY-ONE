from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app


def test_liveness_returns_request_id() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json()["request_id"] == "test-request"
    assert response.json()["status"] == "ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_unsafe_request_id_is_replaced() -> None:
    response = TestClient(app).get(
        "/api/v1/health/live", headers={"X-Request-ID": "unsafe\nlog-entry"}
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe\nlog-entry"
    UUID(response.headers["X-Request-ID"])


def test_readiness_checks_database(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(app)
    called = False

    def fake_check_database() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.modules.health.routes.check_database", fake_check_database)
    monkeypatch.setattr("app.modules.health.routes.check_object_storage", lambda: None)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert called is True


def test_storage_failure_returns_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.modules.health.routes.check_database", lambda: None)

    def failed_storage() -> None:
        raise RuntimeError("private credentials and internal details")

    monkeypatch.setattr("app.modules.health.routes.check_object_storage", failed_storage)
    response = TestClient(app).get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Object storage readiness check failed"
    assert "private credentials" not in response.text


def test_database_failure_returns_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def failed_database() -> None:
        raise RuntimeError("private database details")

    monkeypatch.setattr("app.modules.health.routes.check_database", failed_database)
    response = TestClient(app).get("/api/v1/health/ready")
    assert response.status_code == 503
    assert "private database" not in response.text

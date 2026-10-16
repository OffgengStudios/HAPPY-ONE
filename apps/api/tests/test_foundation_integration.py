import os
from urllib.parse import quote
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_engine
from app.main import app
from app.storage.s3 import get_storage_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("HAPPY_RUN_INTEGRATION") != "1",
        reason="Run pnpm verify with live infrastructure.",
    ),
]


def test_database_transactions_roll_back() -> None:
    with get_engine().connect() as connection:
        transaction = connection.begin()
        connection.execute(text("CREATE TEMP TABLE phase0_rollback (id integer)"))
        connection.execute(text("INSERT INTO phase0_rollback VALUES (1)"))
        transaction.rollback()
        assert (
            connection.execute(text("SELECT to_regclass('pg_temp.phase0_rollback')")).scalar()
            is None
        )


def test_private_storage_round_trip_and_anonymous_access_denied() -> None:
    client = get_storage_client()
    key = f"foundation-check/{uuid4()}.txt"
    payload = b"synthetic foundation verification"
    try:
        client.put_object(Bucket=settings.s3_bucket, Key=key, Body=payload, ACL="private")
        response = client.get_object(Bucket=settings.s3_bucket, Key=key)
        with response["Body"] as body:
            assert body.read() == payload
        url = f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket}/{quote(key)}"
        assert httpx.get(url, timeout=5).status_code == 403
        signed = client.generate_presigned_url(
            "get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=60
        )
        assert httpx.get(signed, timeout=15).content == payload
    finally:
        client.delete_object(Bucket=settings.s3_bucket, Key=key)


def test_live_dependencies_pass_readiness() -> None:
    response = TestClient(app).get(
        "/api/v1/health/ready", headers={"X-Request-ID": "foundation-integration"}
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "foundation-integration"

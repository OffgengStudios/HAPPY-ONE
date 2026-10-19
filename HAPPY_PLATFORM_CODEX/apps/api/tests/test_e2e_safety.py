from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.sandbox import test_schema_url as schema_url
from app.modules.iam import e2e


@pytest.mark.parametrize(
    "schema",
    [
        "public",
        "happy_test_",
        "happy_test_" + "g" * 32,
        "happy_test_" + "a" * 32 + ";drop schema public",
    ],
)
def test_sandbox_url_rejects_untrusted_schemas(schema):
    with pytest.raises(ValueError):
        schema_url(schema)


def test_sandbox_url_preserves_connection_and_scopes_only_search_path(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+psycopg://test:test@127.0.0.1:5433/test?application_name=synthetic",
    )
    schema = "happy_test_" + uuid4().hex
    url = make_url(schema_url(schema))
    assert url.host == "127.0.0.1"
    assert url.database == "test"
    assert url.query["application_name"] == "synthetic"
    assert url.query["options"] == "-csearch_path=" + schema


@pytest.mark.parametrize(
    "field,value",
    [
        ("app_env", "production"),
        ("database_url", "postgresql://test:test@external.example.org/test"),
    ],
)
def test_sandbox_url_refuses_production_and_remote_database(monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    with pytest.raises(ValueError):
        schema_url("happy_test_" + uuid4().hex)


@pytest.mark.parametrize("allowed", [True, False])
def test_browser_cleanup_never_deletes_outside_its_participant_prefix(monkeypatch, allowed):
    identifier = uuid4()
    key = (
        f"participants/{identifier}/cv/{uuid4().hex}" if allowed else "unrelated/production-object"
    )
    db = MagicMock()
    db.scalars.return_value = [SimpleNamespace(participant_id=identifier, storage_key=key)]
    context = MagicMock()
    context.__enter__.return_value = db
    storage = MagicMock()
    monkeypatch.setattr(e2e, "Session", lambda engine: context)
    monkeypatch.setattr(e2e, "get_storage_client", lambda: storage)
    if allowed:
        e2e.cleanup_documents(MagicMock())
        storage.delete_object.assert_called_once_with(Bucket=settings.s3_bucket, Key=key)
    else:
        with pytest.raises(ValueError):
            e2e.cleanup_documents(MagicMock())
        storage.delete_object.assert_not_called()


@pytest.mark.parametrize("allowed", [True, False])
def test_browser_cleanup_never_deletes_outside_its_report_export_prefix(monkeypatch, allowed):
    requester = uuid4()
    key = (
        f"reports/exports/{requester}/{uuid4()}.csv"
        if allowed
        else "reports/exports/another-user/production.csv"
    )
    db = MagicMock()
    db.scalars.return_value = [SimpleNamespace(requested_by=requester, storage_key=key)]
    context = MagicMock()
    context.__enter__.return_value = db
    storage = MagicMock()
    monkeypatch.setattr(e2e, "Session", lambda engine: context)
    monkeypatch.setattr(e2e, "get_storage_client", lambda: storage)
    if allowed:
        e2e.cleanup_report_exports(MagicMock())
        storage.delete_object.assert_called_once_with(Bucket=settings.s3_bucket, Key=key)
    else:
        with pytest.raises(ValueError):
            e2e.cleanup_report_exports(MagicMock())
        storage.delete_object.assert_not_called()

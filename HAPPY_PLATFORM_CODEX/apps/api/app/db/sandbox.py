import os
import re
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import API_ROOT, settings


def test_schema_url(schema: str) -> str:
    if settings.app_env not in {"development", "test"} or not re.fullmatch(
        r"happy_test_[0-9a-f]{32}", schema
    ):
        raise ValueError("Only an isolated synthetic schema may be accessed.")
    base = make_url(settings.database_url)
    if base.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Test schemas require a loopback PostgreSQL endpoint.")
    query = dict(base.query)
    query["options"] = f"-csearch_path={schema}"
    return base.set(query=query).render_as_string(hide_password=False)


def create_test_schema() -> tuple[str, str]:
    if settings.app_env not in {"development", "test"}:
        raise ValueError("Synthetic test schemas are only available in development/test.")
    base = make_url(settings.database_url)
    if base.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Test schemas require a loopback PostgreSQL endpoint.")
    schema = "happy_test_" + uuid4().hex
    engine = create_engine(base)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine.dispose()
    url = test_schema_url(schema)
    environment = {**os.environ, "DATABASE_URL": url, "APP_ENV": "test"}
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=API_ROOT,
            env=environment,
            capture_output=True,
            check=True,
        )
    except Exception:
        drop_test_schema(schema)
        raise
    return schema, url


def drop_test_schema(schema: str) -> None:
    if settings.app_env not in {"development", "test"} or not re.fullmatch(
        r"happy_test_[0-9a-f]{32}", schema
    ):
        raise ValueError("Refusing to remove a non-test schema.")
    engine = create_engine(settings.database_url)
    try:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
    finally:
        engine.dispose()

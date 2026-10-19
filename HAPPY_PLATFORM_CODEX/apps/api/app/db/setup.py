"""Provision the application database on an existing local PostgreSQL server."""

import sys

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.core.config import Settings


class SetupSettings(Settings):
    postgres_admin_user: str = "postgres"
    postgres_admin_password: SecretStr | None = None


def setup_database(settings: SetupSettings | None = None) -> None:
    settings = settings or SetupSettings()
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL.")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("db:setup only provisions a local PostgreSQL server.")
    if not url.username or not url.password or not url.database:
        raise ValueError("DATABASE_URL must specify the app user, password, and database.")

    app_connection = make_conninfo(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
        connect_timeout=5,
    )
    try:
        with psycopg.connect(app_connection) as connection:
            connection.execute("SELECT 1")
        print("Application database connection OK; no setup needed.")
        return
    except psycopg.OperationalError:
        pass

    if (
        not settings.postgres_admin_password
        or not settings.postgres_admin_password.get_secret_value()
    ):
        raise ValueError(
            "Set POSTGRES_ADMIN_PASSWORD in the project root .env, "
            "or configure DATABASE_URL with a working app account."
        )

    with psycopg.connect(
        host=url.host,
        port=url.port or 5432,
        user=settings.postgres_admin_user,
        password=settings.postgres_admin_password.get_secret_value(),
        dbname="postgres",
        connect_timeout=5,
        autocommit=True,
    ) as admin:
        role_exists = admin.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (url.username,)
        ).fetchone()
        if not role_exists:
            admin.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(sql.Identifier(url.username), sql.Literal(url.password))
            )
            print("Created application role.")

        database_exists = admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not database_exists:
            admin.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(url.database), sql.Identifier(url.username)
                )
            )
            print("Created application database.")

    with psycopg.connect(app_connection) as connection:
        connection.execute("SELECT 1")
    print("Application database connection OK. Run pnpm api:migrate next.")


def main() -> int:
    try:
        setup_database()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except psycopg.Error:
        print(
            "PostgreSQL setup failed. Check the server and credentials in .env. "
            "Existing role passwords and database ownership are preserved.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

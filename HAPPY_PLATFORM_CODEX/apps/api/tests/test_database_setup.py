from unittest.mock import MagicMock

import psycopg
import pytest
from pydantic import SecretStr

from app.db.setup import SetupSettings, setup_database


def test_working_app_account_does_not_need_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    monkeypatch.setattr("app.db.setup.psycopg.connect", connect)

    setup_database(SetupSettings(postgres_admin_password=None))

    connect.assert_called_once()


def test_existing_role_and_database_are_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = MagicMock()
    admin.__enter__.return_value = admin
    admin.execute.return_value.fetchone.return_value = (1,)
    connect = MagicMock(side_effect=[psycopg.OperationalError(), admin, MagicMock()])
    monkeypatch.setattr("app.db.setup.psycopg.connect", connect)

    setup_database(SetupSettings(postgres_admin_password=SecretStr("test-admin-password")))

    assert connect.call_count == 3
    assert admin.execute.call_count == 2
    assert all(call.args[0].startswith("SELECT ") for call in admin.execute.call_args_list)


def test_remote_database_is_not_provisioned(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = MagicMock()
    monkeypatch.setattr("app.db.setup.psycopg.connect", connect)

    with pytest.raises(ValueError, match="local PostgreSQL"):
        setup_database(
            SetupSettings(database_url="postgresql+psycopg://happy:password@remote.example/happy")
        )

    connect.assert_not_called()

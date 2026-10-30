import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import PROJECT_ROOT


@pytest.fixture
def local_launcher(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    return importlib.import_module("local_production")


def test_stop_validates_every_process_before_terminating_any(
    local_launcher, monkeypatch, tmp_path: Path
) -> None:
    valid = SimpleNamespace(
        create_time=lambda: 1,
        cwd=lambda: "expected",
        cmdline=lambda: ["start.mjs"],
        terminate=Mock(),
        children=Mock(return_value=[]),
    )
    unrelated = SimpleNamespace(
        create_time=lambda: 1,
        cwd=lambda: "unrelated-project",
        cmdline=lambda: ["start.mjs"],
        terminate=Mock(),
    )
    state = tmp_path / "state.json"
    # Stop checks in reverse order. It must validate the second parent before
    # touching the first valid process or its children.
    state.write_text(
        json.dumps(
            {
                "processes": [
                    {"pid": 2, "created": 1, "cwd": "expected", "marker": "start.mjs"},
                    {"pid": 1, "created": 1, "cwd": "expected", "marker": "start.mjs"},
                ]
            }
        )
    )
    monkeypatch.setattr(local_launcher, "STATE", state)
    monkeypatch.setattr(local_launcher.psutil, "Process", lambda pid: {1: valid, 2: unrelated}[pid])
    with pytest.raises(ValueError, match="identity changed"):
        local_launcher.stop()
    valid.terminate.assert_not_called()
    valid.children.assert_not_called()
    unrelated.terminate.assert_not_called()
    assert state.exists()


def test_reused_pid_is_never_treated_as_a_managed_process(local_launcher, monkeypatch) -> None:
    monkeypatch.setattr(
        local_launcher.psutil, "Process", lambda _: SimpleNamespace(create_time=lambda: 2)
    )
    with pytest.raises(ValueError, match="PID was reused"):
        local_launcher.owned_process({"pid": 1, "created": 1})


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        "/unijay/../../.env",
        "/unijay/%2e%2e/%2e%2e/.env",
        "/HAPPY_PLATFORM_CODEX/.env",
        "/hamis/../../.env",
        "/employer/%2e%2e/%2e%2e/.env",
        "/hamis/C:%5cWindows%5cwin.ini",
        "/employer/%5c%5cserver%5cshare%5csecret",
    ],
)
def test_public_server_cannot_expose_repository_configuration(local_launcher, path: str) -> None:
    handler = object.__new__(local_launcher.PublicHandler)
    translated = Path(handler.translate_path(path))
    assert translated.is_relative_to(local_launcher.DIRECTORY / "unavailable")

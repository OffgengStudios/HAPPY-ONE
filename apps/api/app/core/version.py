import os
from pathlib import Path

API_VERSION = "v1"
DEFAULT_RELEASE_VERSION = "1.0.0-rc.1"


def release_version() -> str:
    configured = os.environ.get("HAPPY_RELEASE_VERSION", "").strip()
    if configured:
        return configured
    version_file = Path(__file__).resolve().parents[4] / "VERSION"
    return (
        version_file.read_text(encoding="ascii").strip()
        if version_file.is_file()
        else DEFAULT_RELEASE_VERSION
    )


RELEASE_VERSION = release_version()

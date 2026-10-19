import os
import subprocess

CREATE_NO_WINDOW: int = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
DETACHED_PROCESS: int = int(getattr(subprocess, "DETACHED_PROCESS", 0))


def creation_flags(*, detached: bool = False, platform: str | None = None) -> int:
    if (platform or os.name) != "nt":
        return 0
    return CREATE_NO_WINDOW | (DETACHED_PROCESS if detached else 0)

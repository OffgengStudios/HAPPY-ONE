import argparse
import json
import os
import subprocess
import time
from urllib.parse import urlsplit

import psutil
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import PROJECT_ROOT, settings
from app.storage.setup import setup_bucket

DIRECTORY = PROJECT_ROOT / ".local" / "storage"
BINARY = PROJECT_ROOT / ".local" / "bin" / ("weed.exe" if os.name == "nt" else "weed")
PID_FILE = DIRECTORY / "server.pid"


def owned_process() -> psutil.Process | None:
    if not PID_FILE.exists():
        return None
    try:
        process = psutil.Process(int(PID_FILE.read_text().strip()))
        if (
            process.is_running()
            and process.exe().lower() == str(BINARY.resolve()).lower()
            and f"-dir={DIRECTORY / 'data'}" in process.cmdline()
        ):
            return process
    except (psutil.NoSuchProcess, ValueError):
        return None
    raise RuntimeError("Storage PID does not identify this project's server.")


def run(action: str) -> None:
    process = owned_process()
    if action == "stop":
        if process:
            process.terminate()
            process.wait(timeout=30)
            PID_FILE.unlink(missing_ok=True)
        print("Project-local object storage stopped.")
        return

    endpoint = urlsplit(settings.s3_endpoint_url)
    if endpoint.hostname not in {"127.0.0.1", "localhost"} or settings.app_env != "development":
        raise ValueError("storage:local is for loopback development endpoints only.")
    if not BINARY.is_file():
        raise ValueError("Run pnpm storage:install first.")

    if not process:
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        credentials = DIRECTORY / "credentials.json"
        credentials.write_text(
            json.dumps(
                {
                    "identities": [
                        {
                            "name": "happy-local",
                            "credentials": [
                                {
                                    "accessKey": settings.s3_access_key_id.get_secret_value(),
                                    "secretKey": settings.s3_secret_access_key.get_secret_value(),
                                }
                            ],
                            "actions": ["Admin", "Read", "Write", "List", "Tagging"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        credentials.chmod(0o600)
        environment = os.environ.copy()
        environment["DEBUG"] = "false"
        with (DIRECTORY / "server.log").open("ab") as log:
            child = subprocess.Popen(
                [
                    str(BINARY),
                    "mini",
                    f"-dir={DIRECTORY / 'data'}",
                    "-ip=127.0.0.1",
                    "-ip.bind=127.0.0.1",
                    f"-s3.port={endpoint.port or 9000}",
                    f"-s3.config={credentials}",
                    "-admin.ui=false",
                    "-webdav=false",
                    "-master.telemetry=false",
                    "-s3.port.iceberg=0",
                    "-s3.port.lance=0",
                ],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
                if os.name == "nt"
                else 0,
                start_new_session=os.name != "nt",
                env=environment,
            )
        PID_FILE.write_text(str(child.pid), encoding="ascii")

    deadline = time.monotonic() + 30
    while True:
        try:
            setup_bucket()
            break
        except (BotoCoreError, ClientError):
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Storage startup failed; inspect .local/storage/server.log."
                ) from None
            time.sleep(0.25)
    print("Project-local private S3 storage is ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Control project-local private S3 storage.")
    parser.add_argument("action", choices=("start", "stop"))
    run(parser.parse_args().action)


if __name__ == "__main__":
    main()

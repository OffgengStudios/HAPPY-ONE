"""Build and serve the optimized local suite with managed, loopback-only processes."""

import argparse
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import psutil
from api import API, PYTHON, ROOT

sys.path.insert(0, str(API))
from app.core.config import Settings  # noqa: E402
from app.core.process import creation_flags  # noqa: E402

REPOSITORY = ROOT.parent
COLLECTOR = Path(
    os.environ.get("UNIJAY_REPOSITORY", REPOSITORY.parent / "UNIJAY-FASHION-DATA-COLLECTION")
).resolve()
WEB = ROOT / "apps" / "web"
DIRECTORY = ROOT / ".local" / "local-production"
STATE = DIRECTORY / "state.json"
BUILD = WEB / ".next-local-production" / "local-runtime.json"
API_PORT = 8100
WEB_PORT = 3300
PUBLIC_PORT = 8865
API_ORIGIN = f"http://127.0.0.1:{API_PORT}"
ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (WEB_PORT, PUBLIC_PORT)
]


def environment(selected: Path) -> dict[str, str]:
    if not selected.is_file():
        raise ValueError("Choose an existing private environment file with --env-file.")
    configured = Settings(_env_file=selected)
    from sqlalchemy.engine import make_url

    if configured.app_env not in {"development", "test"}:
        raise ValueError("This localhost HTTP launcher requires development/test API settings.")
    if make_url(configured.database_url).host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("The local launcher requires a loopback PostgreSQL database.")
    return {
        **os.environ,
        "HAPPY_ENV_FILE": str(selected),
        "HAPPY_LOCAL_PRODUCTION": "1",
        "API_INTERNAL_URL": API_ORIGIN,
        "API_CORS_ORIGINS": json.dumps(sorted(set(configured.api_cors_origins + ORIGINS))),
        "NEXT_PUBLIC_APP_ENV": configured.app_env,
        "HAPPY_API_BASE_URL": API_ORIGIN,
        "ENABLE_LEGACY_INTEGRATIONS": "false",
        "HOSTNAME": "127.0.0.1",
        "PORT": str(WEB_PORT),
    }


def owned_process(entry: dict) -> psutil.Process | None:
    try:
        process = psutil.Process(entry["pid"])
        if abs(process.create_time() - entry["created"]) > 0.01:
            raise ValueError("Local process PID was reused; refusing to stop it.")
        if process.cwd() != entry["cwd"] or not any(
            entry["marker"] in arg for arg in process.cmdline()
        ):
            raise ValueError("Local process identity changed; refusing to stop it.")
        return process
    except psutil.NoSuchProcess:
        return None


def stop() -> None:
    if not STATE.exists():
        print("Local optimized services are stopped.")
        return
    state = json.loads(STATE.read_text())
    # Validate every tracked parent before terminating any process.
    processes = [owned_process(entry) for entry in reversed(state["processes"])]
    for process in processes:
        if process is None:
            continue
        children = process.children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
        _, remaining = psutil.wait_procs([*children, process], timeout=10)
        for child in remaining:
            child.kill()
    STATE.unlink()
    print("Local optimized API, worker, staff and public services stopped.")


def available_port(port: int) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))


def wait_ready(url: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Local service readiness failed; inspect the private local-production logs.")


def start(selected: Path, configured: dict[str, str]) -> None:
    if STATE.exists():
        raise ValueError("Local state already exists. Run status or stop before starting again.")
    if not BUILD.is_file() or json.loads(BUILD.read_text())["env_file"] != str(selected):
        raise ValueError("Build the local suite with this environment file before starting.")
    for port in (API_PORT, WEB_PORT, PUBLIC_PORT):
        available_port(port)
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    state: dict = {"processes": [], "env_file": str(selected)}

    def launch(name: str, command: list[str], cwd: Path, marker: str) -> None:
        with (DIRECTORY / f"{name}.log").open("ab") as log:
            child = subprocess.Popen(
                command,
                cwd=cwd,
                env=configured,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=creation_flags(detached=True),
                start_new_session=os.name != "nt",
            )
        state["processes"].append(
            {
                "pid": child.pid,
                "created": psutil.Process(child.pid).create_time(),
                "cwd": str(cwd),
                "marker": marker,
                "name": name,
            }
        )
        STATE.write_text(json.dumps(state, indent=2))

    try:
        launch(
            "api",
            [
                PYTHON,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(API_PORT),
                "--no-access-log",
            ],
            API,
            "app.main:app",
        )
        wait_ready(API_ORIGIN + "/api/v1/health/ready")
        launch("worker", [PYTHON, "-m", "app.workers.operations"], API, "app.workers.operations")
        launch("staff", [shutil.which("node") or "node", "start.mjs"], WEB, "start.mjs")
        launch(
            "public",
            [PYTHON, str(Path(__file__).resolve()), "serve-public"],
            ROOT,
            "local_production.py",
        )
        wait_ready(f"http://127.0.0.1:{WEB_PORT}")
        wait_ready(f"http://127.0.0.1:{PUBLIC_PORT}")
        if not all(owned_process(entry) for entry in state["processes"]):
            raise RuntimeError("A local service exited during startup.")
    except Exception:
        stop()
        raise
    status()


def status() -> None:
    entries = json.loads(STATE.read_text())["processes"] if STATE.exists() else []
    print(
        json.dumps(
            {
                "running": bool(entries) and all(owned_process(entry) for entry in entries),
                "staff": f"http://localhost:{WEB_PORT}",
                "participant": f"http://localhost:{PUBLIC_PORT}/unijay/",
            },
            indent=2,
        )
    )


class PublicHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass

    def list_directory(self, path: str) -> None:
        self.send_error(404)

    def translate_path(self, path: str) -> str:
        parts = unquote(urlsplit(path).path).strip("/").split("/", 1)
        directories = {
            "unijay": COLLECTOR / "dist",
        }
        root = directories.get(parts[0])
        relative = parts[1] if len(parts) > 1 else ""
        if (
            root is None
            or "\\" in relative
            or ":" in relative
            or ".." in PurePosixPath(relative).parts
        ):
            return str(DIRECTORY / "unavailable")
        target = (root / relative).resolve()
        return str(target if target.is_relative_to(root.resolve()) else DIRECTORY / "unavailable")

    def proxy(self) -> None:
        if not self.path.startswith("/api/v1/"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if self.headers.get("Transfer-Encoding") or not 0 <= length <= 132 * 1024 * 1024:
            self.send_error(413)
            return
        omitted = {"host", "connection", "content-length", "transfer-encoding"}
        headers = {key: value for key, value in self.headers.items() if key.lower() not in omitted}
        connection = http.client.HTTPConnection("127.0.0.1", API_PORT, timeout=60)
        try:
            connection.request(self.command, self.path, self.rfile.read(length), headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in omitted:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (OSError, http.client.HTTPException):
            self.send_error(502, "Local API unavailable")
        finally:
            connection.close()

    def do_GET(self) -> None:
        if self.path.startswith("/api/v1/"):
            self.proxy()
        elif self.path == "/":
            body = (
                f'<a href="http://localhost:{WEB_PORT}">Staff workspace</a><br>'
                '<a href="/unijay/">Participant registration</a>'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    do_POST = proxy
    do_PUT = proxy
    do_PATCH = proxy
    do_DELETE = proxy
    do_OPTIONS = proxy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "start", "stop", "status", "serve-public"])
    parser.add_argument("--env-file", type=Path, default=Path(".local/runtime/working.env"))
    arguments = parser.parse_args()
    if arguments.action == "serve-public":
        ThreadingHTTPServer(("127.0.0.1", PUBLIC_PORT), PublicHandler).serve_forever()
        return 0
    if arguments.action in {"stop", "status"}:
        {"stop": stop, "status": status}[arguments.action]()
        return 0
    selected = (ROOT / arguments.env_file).resolve()
    configured = environment(selected)
    if STATE.exists():
        print(
            "Run local:production status or stop before rebuilding or starting again.",
            file=sys.stderr,
        )
        return 1
    if arguments.action == "start":
        start(selected, configured)
        return 0
    commands = [
        ([shutil.which("pnpm") or "pnpm", "--filter", "web", "build"], ROOT),
        ([shutil.which("node") or "node", "build.mjs"], COLLECTOR),
    ]
    for command, cwd in commands:
        result = subprocess.run(command, cwd=cwd, env=configured, check=False)
        if result.returncode:
            return result.returncode
    BUILD.write_text(json.dumps({"env_file": str(selected), "api_origin": API_ORIGIN}))
    print("Local optimized suite built. Run local:production start with the same environment file.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError):
        print(
            "Local command failed. Check the environment file, build, ports and private logs.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

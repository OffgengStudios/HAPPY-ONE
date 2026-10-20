"""Run public browser journeys against an isolated synthetic HAPPY API."""

import json
import os
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "HAPPY_PLATFORM_CODEX"
API = PLATFORM / "apps/api"
PYTHON = PLATFORM / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    environment = os.environ.copy()
    result = subprocess.run(
        [str(PYTHON), "-m", "app.modules.iam.e2e", "start"],
        cwd=API,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    state = json.loads(result.stdout)
    server = None
    fixture = None
    try:

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ROOT), **kwargs)

            def do_GET(self):
                if self.path in {"/frontend/js/config.js", "/portal/src/config.js"}:
                    content = (
                        "window.HAPPY_API_BASE_URL=" + json.dumps(state["api_url"]) + ";"
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/javascript")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    super().do_GET()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        # A genuine synthetic PDF exercises multipart upload and private storage.
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as document:
            fixture = Path(document.name)
            generated = subprocess.run(
                [
                    str(PYTHON),
                    "-c",
                    "from pypdf import PdfWriter; import io, sys; w=PdfWriter(); "
                    "w.add_blank_page(width=100,height=100); target=io.BytesIO(); "
                    "w.write(target); sys.stdout.buffer.write(target.getvalue())",
                ],
                capture_output=True,
                check=True,
            )
            document.write(generated.stdout)
        environment["HAPPY_BROWSER_CV"] = str(fixture)
        completed = subprocess.run(["node", "integration/browser.cjs"], cwd=ROOT, env=environment)
        return completed.returncode
    finally:
        if fixture:
            fixture.unlink(missing_ok=True)
        if server:
            server.shutdown()
            server.server_close()
        # Keep generated staff credentials inside subprocess memory, never output.
        subprocess.run(
            [str(PYTHON), "-m", "app.modules.iam.e2e", "stop"],
            cwd=API,
            env=environment,
            input=json.dumps(state),
            text=True,
            check=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())

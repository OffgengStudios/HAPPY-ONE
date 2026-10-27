import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from api import PYTHON, ROOT


def main() -> int:
    package_manager = shutil.which("pnpm")
    if not package_manager:
        print("Install pnpm before running CI.", file=sys.stderr)
        return 1
    environment = os.environ.copy()
    environment["HAPPY_RUN_INTEGRATION"] = "1"
    environment.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".local" / "browsers"))
    if os.name == "nt":
        edge = (
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
            / "Microsoft/Edge/Application/msedge.exe"
        )
        if edge.is_file():
            environment.setdefault("PLAYWRIGHT_CHANNEL", "msedge")
    steps = [
        (
            "Python formatting",
            [
                PYTHON,
                "-m",
                "ruff",
                "format",
                "--check",
                "--config",
                "apps/api/pyproject.toml",
                "apps/api",
                "database/migrations",
                "scripts",
            ],
        ),
        ("Backend lint", [sys.executable, "scripts/api.py", "lint"]),
        ("Backend types", [sys.executable, "scripts/api.py", "type-check"]),
        ("Database migration", [sys.executable, "scripts/api.py", "migrate"]),
        (
            "Migration model drift",
            [sys.executable, "scripts/api.py", "migration-check"],
        ),
        (
            "Backend unit and live integration tests",
            [sys.executable, "scripts/api.py", "test"],
        ),
        ("JavaScript formatting", [package_manager, "format:check"]),
        ("Frontend lint", [package_manager, "lint"]),
        ("Workspace types", [package_manager, "type-check"]),
        ("Environment tests", [package_manager, "--filter", "@happy/config", "test"]),
        ("Web production build", [package_manager, "--filter", "web", "build"]),
        (
            "Desktop and mobile browser tests",
            [package_manager, "--filter", "web", "test"],
        ),
        ("Python dependency consistency", [PYTHON, "-m", "pip", "check"]),
        (
            "Python dependency audit",
            [
                PYTHON,
                "-m",
                "pip_audit",
                "--skip-editable",
                "--cache-dir",
                ".local/audit-cache",
                "--progress-spinner",
                "off",
            ],
        ),
        (
            "JavaScript production dependency audit",
            [package_manager, "audit", "--prod", "--audit-level", "high"],
        ),
    ]
    fixture = None
    try:
        for label, command in steps:
            if label == "Web production build":
                setup = subprocess.run(
                    [PYTHON, "-m", "app.modules.iam.e2e", "start"],
                    cwd=ROOT / "apps" / "api",
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if setup.returncode:
                    print(
                        "FAILED: Synthetic browser API setup. Check local test logs.",
                        file=sys.stderr,
                    )
                    return setup.returncode
                fixture = json.loads(setup.stdout)
                environment["API_INTERNAL_URL"] = fixture["api_url"]
                environment["HAPPY_E2E_PASSWORD"] = fixture["password"]
            print(f"\n{label}", flush=True)
            step_environment = environment.copy()
            # Retain adapter regressions without enabling legacy routes in the
            # default application or deployed environments.
            step_environment["ENABLE_LEGACY_INTEGRATIONS"] = (
                "true" if label == "Backend unit and live integration tests" else "false"
            )
            result = subprocess.run(command, cwd=ROOT, env=step_environment, check=False)
            if result.returncode:
                print(f"FAILED: {label}", file=sys.stderr)
                return result.returncode
        print("\nLocal CI passed.", flush=True)
        return 0
    finally:
        if fixture:
            subprocess.run(
                [PYTHON, "-m", "app.modules.iam.e2e", "stop"],
                cwd=ROOT / "apps" / "api",
                env=environment,
                input=json.dumps(fixture),
                text=True,
                check=True,
            )


if __name__ == "__main__":
    sys.exit(main())

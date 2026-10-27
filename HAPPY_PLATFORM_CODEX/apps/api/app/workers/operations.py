import time

from app.core.config import settings
from app.integrations.hamis.worker import run_once as run_hamis_once
from app.modules.cv_parser.worker import run_once as run_parser_once
from app.modules.reporting.worker import run_once as run_report_once


def run_once() -> bool:
    return (
        run_report_once()
        or run_parser_once()
        or (settings.enable_legacy_integrations and run_hamis_once())
    )


def main() -> None:
    while True:
        if not run_once():
            time.sleep(settings.background_worker_poll_seconds)


if __name__ == "__main__":
    main()

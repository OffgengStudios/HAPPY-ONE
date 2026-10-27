import logging
import threading
import time

from app.core.config import settings
from app.core.observability import configure_observability
from app.core.operational_health import persist_state
from app.integrations.hamis.worker import run_once as run_hamis_once
from app.modules.cv_parser.worker import run_once as run_parser_once
from app.modules.reporting.worker import run_once as run_report_once

logger = logging.getLogger("happy.worker")
_last_poll_checkpoint = 0.0


def run_once() -> bool:
    global _last_poll_checkpoint
    try:
        worked = (
            run_report_once()
            or run_parser_once()
            or (settings.enable_legacy_integrations and run_hamis_once())
        )
    except Exception:
        persist_state("WORKER", succeeded=False)
        raise
    # Idle polls are frequent; record a successful poll at most every ten
    # seconds. Job completion is measured separately from terminal queue rows.
    if worked or time.monotonic() - _last_poll_checkpoint >= 10:
        persist_state("WORKER", succeeded=True)
        _last_poll_checkpoint = time.monotonic()
    return worked


def heartbeat(stop: threading.Event) -> None:
    while not stop.is_set():
        persist_state("WORKER", heartbeat=True)
        stop.wait(10)


def main() -> None:
    configure_observability(service_name="happy-worker")
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat, args=(stop,), daemon=True)
    thread.start()
    try:
        while True:
            try:
                worked = run_once()
            except Exception:
                logger.error("worker_poll_failed")
                worked = False
            if not worked:
                time.sleep(settings.background_worker_poll_seconds)
    finally:
        stop.set()
        thread.join(timeout=7)


if __name__ == "__main__":
    main()

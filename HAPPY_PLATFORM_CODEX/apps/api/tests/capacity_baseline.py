"""Opt-in synthetic local capacity evidence; only disposable loopback schemas.

Run from apps/api with PYTHONPATH=. and HAPPY_ENV_FILE pointing at a private
local environment: python tests/capacity_baseline.py --output <private-json>.
This measures in-process HTTP/DB capacity, not a deployed network or cloud SLO.
"""

import argparse
import json
import math
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from uuid import uuid4

import psutil
from sqlalchemy import create_engine, event, func, insert, select, text, update
from sqlalchemy.orm import Session
from test_matching_integration import login

from app.core.config import settings
from app.db.sandbox import create_test_schema, drop_test_schema
from app.db.session import get_db
from app.main import app
from app.modules.demand.models import Organization, Vacancy
from app.modules.iam.models import now
from app.modules.matching.models import CandidateVacancy
from app.modules.placement.models import FirstIncomeVerification, Placement, PlacementHistory
from app.modules.supply.models import Consent, Document, Participant, Person


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 16 or not 5 <= args.requests <= 200:
        parser.error("Use 1–16 concurrent requests and 5–200 samples per route.")
    schema, url = create_test_schema()
    engine = create_engine(url, pool_size=10, max_overflow=10, pool_timeout=5)
    old_origins = settings.api_cors_origins
    settings.api_cors_origins = ["http://localhost:3000"]
    revision = subprocess.run(
        ["git", "-c", "safe.directory=*", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[4],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = {
        "happy_sha": revision,
        "environment": "local synthetic in-process HTTP with live PostgreSQL",
        "dataset": {
            "participants": 10000,
            "employers": 1000,
            "vacancies": 2000,
            "candidate_vacancies": 20000,
            "confirmed_placements": 100,
            "document_metadata": 500,
            "placement_history": 100,
        },
        "concurrency": args.concurrency,
        "samples_per_route": args.requests,
        "measurements": {},
        "status": "INCOMPLETE",
        "seed_counts_verified": False,
        "cleanup": "NOT VERIFIED",
    }
    counters = {"queries": 0, "peak_connections": 0, "peak_rss_bytes": 0}
    lock = threading.Lock()
    stop = threading.Event()

    def database():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    def query(*unused):
        with lock:
            counters["queries"] += 1

    def connection(*unused):
        with lock:
            counters["peak_connections"] = max(
                counters["peak_connections"], engine.pool.checkedout()
            )

    def memory():
        process = psutil.Process()
        while not stop.wait(0.05):
            counters["peak_rss_bytes"] = max(counters["peak_rss_bytes"], process.memory_info().rss)

    app.dependency_overrides[get_db] = database
    monitor = threading.Thread(target=memory, daemon=True)
    try:
        with Session(engine, expire_on_commit=False) as seed:
            client, user = login(seed, "ADMIN")
            people = [uuid4() for _ in range(10000)]
            participants = [uuid4() for _ in people]
            employers = [uuid4() for _ in range(1000)]
            vacancies = [uuid4() for _ in range(2000)]
            candidates = [uuid4() for _ in range(20000)]
            placements = [uuid4() for _ in range(100)]
            actor = {"created_by": user.id, "updated_by": user.id}
            seed.execute(
                insert(Person),
                [
                    dict(
                        actor,
                        id=identifier,
                        first_name="Synthetic",
                        surname=f"Capacity {i:05d}",
                        normalized_name=f"synthetic capacity {i:05d}",
                        phone_raw=f"024{i:07d}",
                        phone_normalized=f"+23324{i:07d}",
                        community="Synthetic Community",
                    )
                    for i, identifier in enumerate(people)
                ],
            )
            seed.execute(
                insert(Participant),
                [
                    dict(
                        actor,
                        id=identifier,
                        person_id=people[i],
                        participant_code=f"CAP-P-{i:05d}",
                        onboarding_status="COMPLETE",
                        completed_sections=["basic", "contact", "consent", "review"],
                        completed_at=now(),
                    )
                    for i, identifier in enumerate(participants)
                ],
            )
            seed.execute(
                insert(Consent),
                [
                    dict(
                        actor,
                        participant_id=identifier,
                        consent_type="PROGRAMME",
                        status="ACTIVE",
                        consented_at=now(),
                        method="STAFF_RECORDED",
                        privacy_notice_version=settings.supply_privacy_notice_version
                        or "SYNTHETIC-CAPACITY",
                    )
                    for identifier in participants
                ],
            )
            seed.execute(
                insert(Organization),
                [
                    dict(
                        actor,
                        id=identifier,
                        organization_code=f"CAP-O-{i:05d}",
                        name=f"Synthetic Employer {i:05d}",
                        normalized_name=f"synthetic employer {i:05d}",
                        organization_type="EMPLOYER",
                    )
                    for i, identifier in enumerate(employers)
                ],
            )
            seed.execute(
                insert(Vacancy),
                [
                    dict(
                        actor,
                        id=identifier,
                        organization_id=employers[i % 1000],
                        vacancy_code=f"CAP-V-{i:05d}",
                        title=f"Synthetic Vacancy {i:05d}",
                        status="ACTIVE",
                        required_headcount=10,
                    )
                    for i, identifier in enumerate(vacancies)
                ],
            )
            seed.execute(
                insert(CandidateVacancy),
                [
                    dict(
                        actor,
                        id=identifier,
                        participant_id=participants[i % 10000],
                        vacancy_id=vacancies[(i % 2000 + i // 10000) % 2000],
                        status="SELECTED" if i < 100 else "POTENTIAL_MATCH",
                        selected_at=now() if i < 100 else None,
                        submitted_at=now() if i < 100 else None,
                        source="STAFF",
                        priority="NORMAL",
                    )
                    for i, identifier in enumerate(candidates)
                ],
            )
            seed.execute(
                insert(Placement),
                [
                    dict(
                        actor,
                        id=identifier,
                        placement_code=f"CAP-L-{i:05d}",
                        participant_id=participants[i],
                        candidate_vacancy_id=candidates[i],
                        organization_id=employers[i],
                        vacancy_id=vacancies[i],
                        status="START_PENDING",
                    )
                    for i, identifier in enumerate(placements)
                ],
            )
            seed.execute(
                insert(FirstIncomeVerification),
                [
                    dict(
                        actor,
                        placement_id=identifier,
                        status="CONFIRMED",
                        actual_income_received_date=date(2026, 10, 25),
                        verified_at=now(),
                        verified_by=user.id,
                        amount_received=2400,
                    )
                    for identifier in placements
                ],
            )
            seed.execute(
                update(Placement)
                .where(Placement.id.in_(placements))
                .values(
                    status="CONFIRMED", actual_start_date=date(2026, 10, 10), confirmed_at=now()
                )
            )
            seed.execute(
                update(CandidateVacancy)
                .where(CandidateVacancy.id.in_(candidates[:100]))
                .values(status="CONFIRMED_PLACEMENT")
            )
            seed.execute(
                insert(PlacementHistory),
                [
                    dict(
                        placement_id=identifier,
                        to_status="CONFIRMED",
                        actor_type="USER",
                        actor_id=str(user.id),
                        reason="Synthetic capacity fixture",
                    )
                    for identifier in placements
                ],
            )
            seed.execute(
                insert(Document),
                [
                    dict(
                        actor,
                        participant_id=participants[i],
                        document_code=f"CAP-D-{i:05d}",
                        storage_key=f"synthetic-capacity-metadata/{i}",
                        original_filename="synthetic.pdf",
                        mime_type="application/pdf",
                        size_bytes=1,
                        sha256="0" * 64,
                        version_number=1,
                        scan_status="SCANNING",
                    )
                    for i in range(500)
                ],
            )
            seed.commit()
            for model in (
                Person,
                Participant,
                Consent,
                Organization,
                Vacancy,
                CandidateVacancy,
                Placement,
                FirstIncomeVerification,
                PlacementHistory,
                Document,
            ):
                seed.execute(text(f'ANALYZE "{schema}"."{model.__tablename__}"'))
            seed.commit()
        with Session(engine) as check:
            for model, expected in (
                (Participant, 10000),
                (Organization, 1000),
                (Vacancy, 2000),
                (CandidateVacancy, 20000),
                (Placement, 100),
                (Document, 500),
                (PlacementHistory, 100),
                (Consent, 10000),
            ):
                assert check.scalar(select(func.count()).select_from(model)) == expected
        with Session(engine) as check:
            result["migration_head"] = check.scalar(text("SELECT version_num FROM alembic_version"))
        result["seed_counts_verified"] = True
        result["query_plans"] = {}
        with Session(engine) as check:
            plans = {
                "participant_page": "SELECT id FROM participants WHERE archived_at IS NULL "
                "ORDER BY created_at DESC, id DESC LIMIT 26",
                "selective_participant_search": "SELECT p.id FROM participants p "
                "JOIN people n ON n.id=p.person_id WHERE p.archived_at IS NULL AND "
                "(n.normalized_name ILIKE '%capacity 09999%' OR "
                "p.participant_code ILIKE '%capacity 09999%' OR "
                "n.phone_normalized ILIKE '%capacity 09999%') "
                "ORDER BY p.created_at DESC,p.id DESC LIMIT 26",
                "vacancy_page": "SELECT id FROM vacancies WHERE archived_at IS NULL "
                "ORDER BY created_at DESC,id DESC LIMIT 26",
            }
            for label, statement in plans.items():
                result["query_plans"][label] = check.scalar(
                    text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement)
                )
        event.listen(engine, "before_cursor_execute", query)
        event.listen(engine, "checkout", connection)
        monitor.start()
        period = "date_from=2026-01-01&date_to=2026-12-31"
        routes = {
            "participant_list": ("GET", "/api/v1/participants?limit=25", None),
            "participant_search": ("GET", "/api/v1/participants?q=Capacity&limit=25", None),
            "vacancy_list": ("GET", "/api/v1/vacancies?limit=25", None),
            "matching_suggestions": (
                "POST",
                f"/api/v1/vacancies/{vacancies[-1]}/match-suggestions",
                {},
            ),
            "dashboard": ("GET", "/api/v1/reports/dashboard?" + period, None),
            "management_kpis": ("GET", "/api/v1/reports/kpis?" + period, None),
            "report_export": (
                "POST",
                "/api/v1/reports/export",
                {"kpi_code": "KPI-SUP-001", "date_from": "2026-01-01", "date_to": "2026-12-31"},
            ),
        }
        for name, (method, path, body) in routes.items():

            def request(_, method=method, path=path, body=body):
                started = time.perf_counter()
                response = client.request(method, path, json=body)
                return (
                    (time.perf_counter() - started) * 1000,
                    response.status_code,
                    len(response.content),
                )

            # Sequential probe isolates SQL query count from the concurrent sample.
            counters["queries"] = 0
            probe = request(0)
            sql_queries = counters["queries"]
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                samples = list(pool.map(request, range(args.requests)))
            durations = sorted(sample[0] for sample in samples)
            result["measurements"][name] = {
                "p50_ms": round(statistics.median(durations), 2),
                "p95_ms": round(durations[math.ceil(len(durations) * 0.95) - 1], 2),
                "error_rate": sum(status >= 400 for _, status, _ in samples) / len(samples),
                "status_codes": sorted({status for _, status, _ in samples}),
                "sequential_sql_queries": sql_queries,
                "max_response_bytes": max(size for _, _, size in samples),
                "probe_status": probe[1],
            }
        # Compare query growth across page sizes to expose N+1 behavior.
        result["query_growth"] = {}
        for resource in ("participants", "vacancies"):
            sizes = {}
            for size in (5, 25):
                counters["queries"] = 0
                response = client.get(f"/api/v1/{resource}?limit={size}")
                assert response.status_code == 200
                sizes[str(size)] = counters["queries"]
                if size == 5:
                    for row in response.json()["items"]:
                        detail = client.get(f"/api/v1/{resource}/{row['id']}")
                        assert detail.status_code == 200
                        assert row == detail.json(), "Batched list projection changed record fields"
            result["query_growth"][resource] = sizes
            assert sizes["25"] <= sizes["5"] + 2, "List queries grow with row count"
        result["peak_app_rss_bytes"] = counters["peak_rss_bytes"]
        result["peak_app_database_connections"] = counters["peak_connections"]
        result["status"] = "COMPLETED"
        assert all(value["error_rate"] == 0 for value in result["measurements"].values())
        assert result["measurements"]["report_export"]["max_response_bytes"] > 1000
        result["pool"] = {"size": 10, "max_overflow": 10, "timeout_seconds": 5}
        result["limitations"] = [
            "No deployed network/TLS, cloud sizing or real-user traffic",
            "Small sample count; not a soak test or production SLO acceptance",
            "Documents are metadata-only SCANNING fixtures; no object upload throughput claim",
            "Synthetic bulk setup is not golden business-workflow evidence",
            "Application RSS includes fixture setup and retained synthetic ID lists",
            "Synchronous report export uses its existing 5000-row bound",
        ]
    except Exception:
        result["status"] = "FAILED"
        raise
    finally:
        stop.set()
        if monitor.ident is not None:
            monitor.join(timeout=2)
        app.dependency_overrides.clear()
        settings.api_cors_origins = old_origins
        engine.dispose()
        drop_test_schema(schema)
        result["cleanup"] = "VERIFIED disposable schema removed; no objects created"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

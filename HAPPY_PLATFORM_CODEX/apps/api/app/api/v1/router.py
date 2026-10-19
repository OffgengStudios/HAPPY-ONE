from fastapi import APIRouter

from app.integrations.employer_portal.routes import router as employer_portal_router
from app.integrations.hamis.routes import router as hamis_router
from app.modules.cv_parser.routes import router as cv_parser_router
from app.modules.demand.routes import router as demand_router
from app.modules.external_references.routes import router as reference_router
from app.modules.health.routes import router as health_router
from app.modules.iam.routes import router as iam_router
from app.modules.marketing.routes import router as marketing_router
from app.modules.matching.routes import router as matching_router
from app.modules.merl.routes import router as merl_router
from app.modules.placement.routes import router as placement_router
from app.modules.reporting.routes import router as reporting_router
from app.modules.search.routes import router as search_router
from app.modules.supply.routes import router as supply_router
from app.modules.training.routes import router as training_router
from app.modules.work.routes import router as work_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(iam_router)
api_router.include_router(demand_router)
api_router.include_router(supply_router)
api_router.include_router(cv_parser_router)
api_router.include_router(reference_router)
api_router.include_router(search_router)
api_router.include_router(matching_router)
api_router.include_router(merl_router)
api_router.include_router(marketing_router)
api_router.include_router(placement_router)
api_router.include_router(reporting_router)
api_router.include_router(training_router)
api_router.include_router(work_router)
api_router.include_router(hamis_router)
api_router.include_router(employer_portal_router)

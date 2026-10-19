from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_errors
from app.core.middleware import RequestIdMiddleware, RequestSizeMiddleware
from app.core.observability import configure_observability
from app.core.version import RELEASE_VERSION


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=RELEASE_VERSION,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )

    app.add_middleware(RequestSizeMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
    )
    app.include_router(api_router, prefix="/api/v1")
    register_errors(app)
    configure_observability(app)
    return app


app = create_app()

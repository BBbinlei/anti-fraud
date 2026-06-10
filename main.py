"""
FastAPI entrypoint.

This module creates the app, initializes observability, and mounts routers.
Business logic belongs in services/.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import (
    APP_NAME,
    APP_VERSION,
    FRONTEND_ASSETS_DIR,
    FRONTEND_ASSETS_ROUTE,
    FRONTEND_INDEX_FILE,
    FRONTEND_INDEX_ROUTE,
    FRONTEND_PROFILE_FILE,
    FRONTEND_PROFILE_ROUTE,
    FRONTEND_REVIEW_FILE,
    FRONTEND_REVIEW_ROUTE,
    FRONTEND_REPORT_FILE,
    FRONTEND_REPORT_ROUTE,
    FRONTEND_THEATER_FILE,
    FRONTEND_THEATER_ROUTE,
    PHOENIX_PROJECT_NAME,
    RISK_RULES_FILE,
)
from routers import report, theater, user

logger = logging.getLogger(__name__)


def init_observability() -> bool:
    """Start Phoenix tracing if optional observability dependencies exist."""
    try:
        import phoenix as px
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register

        px.launch_app()
        tracer_provider = register(
            project_name=PHOENIX_PROJECT_NAME,
            auto_instrument=True,
        )
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        return True
    except Exception:
        logger.warning("Observability initialization skipped", exc_info=True)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.db_service import init_db
    init_db()
    with open(RISK_RULES_FILE, encoding="utf-8") as f:
        app.state.risk_rules = json.load(f)["rules"]
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
    try:
        app.state.observability_enabled = init_observability()
    except Exception:
        logger.warning("Observability initialization failed", exc_info=True)
        app.state.observability_enabled = False
    app.mount(
        FRONTEND_ASSETS_ROUTE,
        StaticFiles(directory=FRONTEND_ASSETS_DIR),
        name="assets",
    )

    @app.get(FRONTEND_INDEX_ROUTE, include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(FRONTEND_INDEX_FILE)

    @app.get(FRONTEND_THEATER_ROUTE, include_in_schema=False)
    async def frontend_theater() -> FileResponse:
        return FileResponse(FRONTEND_THEATER_FILE)

    @app.get(FRONTEND_REVIEW_ROUTE, include_in_schema=False)
    async def frontend_review() -> FileResponse:
        return FileResponse(FRONTEND_REVIEW_FILE)

    @app.get(FRONTEND_REPORT_ROUTE, include_in_schema=False)
    async def frontend_report() -> FileResponse:
        return FileResponse(FRONTEND_REPORT_FILE)

    @app.get(FRONTEND_PROFILE_ROUTE, include_in_schema=False)
    async def frontend_profile() -> FileResponse:
        return FileResponse(FRONTEND_PROFILE_FILE)

    app.include_router(theater.router)
    app.include_router(report.router)
    app.include_router(user.router)
    return app


app = create_app()

"""FastAPI application factory.

Run locally:   uvicorn app.main:app --reload        (from the backend/ directory)
API docs:      http://localhost:8000/api/docs
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router
from .config import Settings
from .policies import DEFAULT_GATE, DayAheadGate
from .repository import DataUnavailableError, WindDataRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("wind_desk")


def create_app(settings: Settings | None = None, repository: WindDataRepository | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = repository or WindDataRepository(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load data and pre-compute the default views in the background so the first
        # visitor does not wait. Failures are logged, not fatal: requests retry lazily.
        async def warm() -> None:
            try:
                analytics = await repository.analytics()
                first, last = settings.delivery_days
                analytics.evaluate(DayAheadGate(DEFAULT_GATE), first, last)
                analytics.lead_curve(first, last)
                analytics.gate_sweep(first, last)
                log.info("Data warm-up complete (source=%s)", analytics.dataset.source)
            except Exception as exc:  # noqa: BLE001
                log.warning("Background warm-up failed: %s", exc)

        task = asyncio.create_task(warm())
        yield
        task.cancel()

    app = FastAPI(
        title="Wind Desk API",
        version=__version__,
        description="Day-ahead wind forecast intelligence for GB power procurement "
        "(Elexon BMRS FUELHH outturn vs WINDFOR forecasts).",
        lifespan=lifespan,
        # Docs live under /api so they reach the backend in every deployment shape:
        # Vite and nginx proxy only /api, and Vercel routes only /api/* to the function.
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.repository = repository

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(DataUnavailableError)
    async def data_unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    app.include_router(router)

    # Single-container deployments (Docker/Heroku) serve the built React app too.
    # Mounted last so /api/* routes always win.
    if settings.static_dir and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="spa")
        log.info("Serving frontend from %s", settings.static_dir)

    return app


app = create_app()

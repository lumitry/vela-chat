from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from watchfiles import awatch

from .config import get_settings
from .engine import MiniMediatorEngine
from .fixtures import FixturesStore
from .logging_middleware import RequestLoggingMiddleware
from .providers.openai import build_router as build_openai_router
from .providers.ollama import build_router as build_ollama_router

logger = logging.getLogger(__name__)


def create_app(
    *,
    log_requests: bool | None = None,
    log_file: str | None = None,
    log_pretty: bool | None = None,
) -> FastAPI:
    settings = get_settings()
    fixtures_store = FixturesStore()
    engine = MiniMediatorEngine(fixtures_store=fixtures_store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine
        watch_task = None

        if settings.watch_fixtures:
            async def _watch_fixtures():
                async for changes in awatch(engine.fixtures_root):
                    try:
                        engine.reload_fixtures()
                        logger.info("Reloaded fixtures after changes: %s", changes)
                    except Exception as exc:  # pragma: no cover - dev aid
                        logger.exception("Failed to reload fixtures: %s", exc)

            watch_task = asyncio.create_task(_watch_fixtures())

        try:
            yield
        finally:
            if watch_task:
                watch_task.cancel()
                with suppress(asyncio.CancelledError):
                    await watch_task

    app = FastAPI(title="Mini-Mediator Mock Server", lifespan=lifespan)

    # Determine logging configuration (CLI args override settings)
    final_log_requests = log_requests if log_requests is not None else settings.log_requests
    final_log_file = log_file if log_file is not None else settings.log_file
    final_log_pretty = log_pretty if log_pretty is not None else settings.log_pretty
    
    # Store in app.state for potential runtime access
    app.state.log_requests = final_log_requests
    app.state.log_file = final_log_file
    app.state.log_pretty = final_log_pretty
    
    # Add request logging middleware if enabled
    if final_log_requests:
        app.add_middleware(
            RequestLoggingMiddleware,
            enabled=True,
            log_file=final_log_file,
            pretty=final_log_pretty,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(build_openai_router(engine))
    app.include_router(build_ollama_router(engine))

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


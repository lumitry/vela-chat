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
from .providers.openai import build_router as build_openai_router
from .providers.ollama import build_router as build_ollama_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
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


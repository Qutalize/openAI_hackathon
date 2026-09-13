import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import load_settings
from app.inference.worker import InferenceService
from app.repositories.rooms import RoomRepository
from app.services.rooms import RoomService
from app.ws.routes import router as ws_router
from app.web import FrontendFiles


def create_app(settings=None, inference=None):
    cfg = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=cfg.observability.log_level)
        engine = inference or InferenceService(cfg)
        app.state.inference = engine
        app.state.rooms = RoomService(cfg, RoomRepository(cfg.path(cfg.storage.room_database)), engine)
        await engine.start()

        async def reap():
            while True:
                await asyncio.sleep(1)
                await app.state.rooms.cleanup()

        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            for session in list(app.state.rooms.sessions.values()):
                await app.state.rooms.remove(session)
            await engine.close()

    app = FastAPI(
        title=cfg.app.name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if cfg.server.serve_frontend else "/docs",
        redoc_url=None if cfg.server.serve_frontend else "/redoc",
        openapi_url=None if cfg.server.serve_frontend else "/openapi.json",
    )
    app.state.settings = cfg
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list({*cfg.server.allowed_origins, cfg.public_origin}),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    app.include_router(api_router)
    app.include_router(ws_router)
    if cfg.server.serve_frontend:
        app.mount("/", FrontendFiles(cfg.path(cfg.server.frontend_dist)), name="frontend")
    return app


app = create_app()

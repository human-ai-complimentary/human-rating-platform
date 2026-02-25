from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import build_database
from routers import admin, raters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    if request.url.path.startswith(("/admin", "/raters")):
        logger.info(
            "%s %s - %s - %.3fs",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )

    return response


async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


async def health():
    return {"status": "healthy"}


def create_app() -> FastAPI:
    settings = get_settings()
    database = build_database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await database.connect()
        app.state.database = database
        try:
            yield
        finally:
            await database.disconnect()

    app = FastAPI(
        title="Human Rating Platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(log_requests)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(admin.router)
    app.include_router(raters.router)
    app.add_api_route("/health", health, methods=["GET"])

    return app


app = create_app()

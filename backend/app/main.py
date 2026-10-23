"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.core.request_id import RequestIdMiddleware
from app.db.session import engine

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bookleaf")

DESCRIPTION = """
REST API for the **BookLeaf Author Support & Communication Portal**.

* **Auth**: `POST /api/v1/auth/login` → bearer JWT. Send `Authorization: Bearer <token>` on every call.
* **Roles**: `AUTHOR` endpoints are scoped to the caller's own data by the token; `ADMIN` endpoints see everything.
* **Errors**: every non-2xx response is `{"error": {"code", "message", "request_id", "details"?}}`.
* **Realtime**: SSE endpoints accept `?token=<jwt>` because `EventSource` cannot set headers.
"""

TAGS = [
    {"name": "auth", "description": "Login / session."},
    {"name": "author", "description": "Author portal: my books, my tickets."},
    {"name": "admin", "description": "Ops portal: queue, ticket management, AI assistance, usage."},
    {"name": "system", "description": "Health."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("BookLeaf API starting (env=%s, ai=%s)", settings.app_env, "on" if settings.ai_available else "OFF")
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="BookLeaf Support API",
        version="1.0.0",
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    register_error_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok", "ai": "enabled" if settings.ai_available else "disabled"}

    return app


app = create_app()

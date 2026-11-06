import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.v1 import auth, listings, misc
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.db.session import get_engine
from app.storage import MediaNotFound, get_storage

log = logging.getLogger("ajar")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("startup", extra={"extra_fields": {"env": settings.env, "demo_mode": settings.demo_mode}})
        yield
        await get_engine().dispose()

    app = FastAPI(
        title="2ajar API",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs" if settings.env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", "X-Request-ID"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/healthz", tags=["health"])
    @app.head("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    @app.head("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness check failed")
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth.router)
    v1.include_router(auth.me_router)
    v1.include_router(misc.router)
    v1.include_router(listings.router)
    app.include_router(v1)

    @app.get("/media/{key:path}", include_in_schema=False)
    async def media(key: str) -> Response:
        try:
            data, content_type = await get_storage().get(key)
        except (MediaNotFound, ValueError):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found"}}, status_code=404)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    return app


app = create_app()

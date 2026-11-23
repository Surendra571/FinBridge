"""
FinBridge Application Entrypoint.
Initializes FastAPI, mounts middleware, registers API routes, and configures lifecycle events.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.v1.api_router import api_v1_router
from app.api.v1.endpoints.health import router as root_health_router

# Initialize structured logging
setup_logging()
logger = get_logger("finbridge.app")


class CorrelationIdMiddleware:
    """Pure ASGI middleware for high-performance correlation ID injection and timing."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())
        for k, v in scope.get("headers", []):
            if k.lower() == b"x-correlation-id":
                correlation_id = v.decode("latin1", errors="ignore")
                break

        start_time = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-correlation-id", correlation_id.encode("latin1")))
                resp_headers.append((b"x-response-time-ms", str(duration_ms).encode("latin1")))
                message["headers"] = resp_headers

                status_code = message.get("status", 200)
                logger.info(
                    "HTTP Request",
                    method=scope.get("method"),
                    path=scope.get("path"),
                    status_code=status_code,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    logger.info(
        "Application starting up",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    # Ensure database tables exist (e.g. SQLite local development)
    try:
        import app.models  # noqa: F401
        from app.db.base import Base
        from app.db.session import get_engine
        from sqlalchemy import text
        engine = get_engine()
        async with engine.begin() as conn:
            if "sqlite" in settings.DATABASE_URL:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA busy_timeout=5000;"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema verified and active")
    except Exception as exc:
        logger.error("Database schema initialization warning", error=str(exc))

    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description="Enterprise AI-assisted Financial Operations & Reconciliation Platform",
        docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^https://.*\.vercel\.app$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Pure ASGI Correlation ID & Timing Middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 3. Mount Versioned Routers
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # 4. Mount top-level /health probes
    app.include_router(root_health_router)

    # 5. Root status endpoint
    @app.get("/", tags=["Root"])
    async def root_index():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "tagline": "Finance. Connected. Verified.",
            "docs_url": "/docs",
            "api_v1_url": settings.API_V1_PREFIX,
        }

    # 6. Global exception handler with CORS guarantee
    from fastapi import Request
    from fastapi.responses import JSONResponse
    import traceback

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled server exception",
            path=request.url.path,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        origin = request.headers.get("origin")
        headers = {}
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "*"
            headers["Access-Control-Allow-Headers"] = "*"
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred.", "error": str(exc)},
            headers=headers,
        )

    return app


app = create_app()

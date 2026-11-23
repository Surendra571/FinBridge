"""
Health check endpoints for liveness, readiness, and observability.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health & Status"])


@router.get("/live", summary="Liveness probe")
async def liveness_probe() -> Dict[str, Any]:
    """
    Checks if the web process is running.
    Returns 200 OK immediately if the application server is responsive.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready", summary="Readiness probe")
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Checks if the application and all core dependencies (Database) are ready to serve traffic.
    """
    health_status: Dict[str, Any] = {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "dependencies": {},
    }

    is_healthy = True

    # 1. Check Database connectivity
    try:
        result = await db.execute(text("SELECT 1"))
        scalar = result.scalar()
        if scalar == 1:
            health_status["dependencies"]["database"] = {"status": "connected"}
        else:
            health_status["dependencies"]["database"] = {"status": "degraded"}
            is_healthy = False
    except Exception as exc:
        health_status["dependencies"]["database"] = {
            "status": "unreachable",
            "error": str(exc),
        }
        is_healthy = False

    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    health_status["status"] = "ok" if is_healthy else "degraded"

    return JSONResponse(status_code=status_code, content=health_status)


@router.api_route("/setup-db", methods=["GET", "POST"], summary="Initialize schema and seed demo data")
async def setup_db(db: AsyncSession = Depends(get_db)):
    """Creates all database tables and seeds initial demo users and organizations."""
    try:
        from app.db.base import Base
        from app.db.session import get_engine
        import app.models  # noqa
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from scripts.seed_demo_data import seed
        await seed()
        user_count = (await db.execute(text("SELECT count(*) FROM users"))).scalar()
        return {
            "status": "ok",
            "message": "Database tables created and seeded successfully",
            "users_count": user_count,
        }
    except Exception as exc:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )

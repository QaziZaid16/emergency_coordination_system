import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.api import router
from app.config import get_settings
from app.database import Base, engine
from app import models  # noqa: F401 - registers SQLAlchemy models
from app.intelligence import run_analysis_recovery_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Local SQLite and automated tests may create tables directly. Deployments use Alembic.
    if settings.environment in ("development", "test"):
        Base.metadata.create_all(bind=engine)
    worker = (
        asyncio.create_task(run_analysis_recovery_worker())
        if settings.environment != "test"
        else None
    )
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        engine.dispose()


settings = get_settings()
app = FastAPI(
    title="Emergency Coordination API",
    version="0.1.0",
    description="Shared role based API for the development coordination platform.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Do not log the exception text: driver diagnostics may include the
        # configured host or connection details. The exception class is enough
        # for an operator to distinguish the failure family.
        logger.warning("Database readiness check failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ready"}

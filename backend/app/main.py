from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import router
from app.config import get_settings
from app.database import Base, engine
from app import models  # noqa: F401 - registers SQLAlchemy models


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Local SQLite and automated tests may create tables directly. Deployments use Alembic.
    if settings.environment in ("development", "test"):
        Base.metadata.create_all(bind=engine)
    yield


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
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from config import get_settings
from db.health import check_all
from db.migrations import ensure_schema
from db.pool import db_pool


settings = get_settings()
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared infrastructure resources."""
    pool = await db_pool.create()

    await ensure_schema(pool)

    yield

    await db_pool.close()


app = FastAPI(
    title=settings.app_name,
    description="Production multi-modal LLM orchestration platform.",
    version="1.0.0",
    lifespan=lifespan,
)


FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health() -> dict:
    """Check PostgreSQL, Redis, and MLflow connectivity."""
    pool = db_pool.get_pool()

    checks = await check_all(pool)

    status = "ok" if all(checks.values()) else "degraded"

    return {
        "status": status,
        "checks": checks,
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/")
async def root() -> dict:
    """Return basic API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
    }
from api.ingest import router as ingest_router

app.include_router(ingest_router)

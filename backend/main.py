from contextlib import asynccontextmanager

from monitoring.metrics import *
from fastapi import FastAPI
from fastapi.responses import Response, Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

def _initialize_metrics():
    queries_total.labels(pipeline_id="default", status="success")
    queries_total.labels(pipeline_id="default", status="error")
    ingestion_docs_total.labels(source_type="unknown")
    llm_calls_total.labels(provider="unknown", model="unknown", task_type="unknown")
    circuit_breaker_trips_total.labels(provider="unknown")
    retrieval_latency.labels(strategy="hybrid")
    generation_latency.labels(model="unknown")
    llm_cost.labels(model="unknown")
    eval_faithfulness.labels(pipeline_id="default")
    eval_overall.labels(pipeline_id="default")


from config import get_settings
from api.query import router as query_router, configure_provider
from api.evaluations import router as evaluations_router
from api.rating import router as rating_router
from api.finetune import router as finetune_router
from api.pipelines import router as pipelines_router
from api.compare import router as compare_router
from db.health import check_all
from db.migrations import ensure_schema
from db.pool import db_pool
from providers.openai_provider import OpenAIProvider
from providers.openai_provider import OpenAIProvider


settings = get_settings()
tracer = trace.get_tracer(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared infrastructure resources."""
    pool = await db_pool.create()

    await ensure_schema(pool)
    configure_provider(
        OpenAIProvider(
            model="gpt-4o-mini",
            api_key=settings.llm_api_key,
        )
    )

    yield

    await db_pool.close()


_initialize_metrics()

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

app.include_router(query_router)
app.include_router(evaluations_router)

app.include_router(rating_router)

app.include_router(finetune_router)
app.include_router(pipelines_router)
app.include_router(compare_router)

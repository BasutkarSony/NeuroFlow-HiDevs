import asyncpg
from arq.connections import RedisSettings
from opentelemetry import trace

from config import get_settings
from pipelines.ingestion.pipeline import process_document
from pipelines.ingestion.repository import DocumentRepository
from providers.openai_provider import OpenAIProvider


async def ingest_job(ctx, document_id: str, file_path: str, source_type: str):
    return await process_document(
        document_id=document_id,
        file_path=file_path,
        source_type=source_type,
        db=ctx["db"],
        provider=ctx.get("provider"),
        tracer=ctx.get("tracer"),
    )


async def startup(ctx):
    settings = get_settings()
    pool = await asyncpg.create_pool(
        dsn=settings.postgres_dsn,
        min_size=1,
        max_size=5,
        command_timeout=60,
    )
    ctx["pool"] = pool
    ctx["db"] = DocumentRepository(pool)
    ctx["tracer"] = trace.get_tracer("neuroflow.ingestion.worker")
    ctx["provider"] = (
        OpenAIProvider(model="gpt-4o-mini", api_key=settings.llm_api_key)
        if settings.llm_api_key
        else None
    )


async def shutdown(ctx):
    pool = ctx.get("pool")
    if pool is not None:
        await pool.close()


class WorkerSettings:
    functions = [ingest_job]
    redis_settings = RedisSettings(
        host=get_settings().redis_host,
        port=get_settings().redis_port,
        password=get_settings().redis_password,
        database=0,
    )
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
    job_timeout = 900
    keep_result = 3600

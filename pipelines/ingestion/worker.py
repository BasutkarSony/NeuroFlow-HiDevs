import asyncpg
import logging
import os
import uuid
from arq.connections import RedisSettings
from arq.worker import Retry
from opentelemetry import trace

from config import get_settings
from pipelines.ingestion.pipeline import process_document
from pipelines.ingestion.repository import DocumentRepository
from providers.openai_provider import OpenAIProvider


MAX_INGESTION_TRIES = 5
PERMANENT_INGESTION_ERRORS = (
    ValueError,
    TypeError,
    UnicodeError,
    FileNotFoundError,
    PermissionError,
)


async def ingest_job(ctx, document_id: str, file_path: str, source_type: str, client_id: str):
    db = ctx["db"]
    try:
        return await process_document(
            document_id=document_id,
            file_path=file_path,
            source_type=source_type,
            client_id=client_id,
            db=db,
            provider=ctx.get("provider"),
            tracer=ctx.get("tracer"),
        )
    except Exception as exc:
        job_try = int(ctx.get("job_try", 1))
        if (
            not isinstance(exc, PERMANENT_INGESTION_ERRORS)
            and job_try < MAX_INGESTION_TRIES
        ):
            # Short exponential backoff, capped at one minute.
            raise Retry(defer=min(2 ** (job_try - 1), 60)) from exc

        try:
            await db.update_document_status(
                document_id,
                "failed",
                metadata={
                    "error": str(exc)[:500],
                    "attempts": job_try,
                },
            )
        except Exception:
            # Preserve the original ingestion exception; a later reconciliation
            # pass can identify records left in processing state.
            import logging

            logging.getLogger(__name__).exception(
                "Could not persist final failure for document %s", document_id
            )
        raise


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

    # Recover requests interrupted between the database insert and Redis enqueue,
    # plus documents left processing after ARQ's in-progress lease has expired.
    recoverable = await ctx["db"].recoverable_ingestion_documents()
    for document in recoverable:
        metadata = document["metadata"] or {}
        storage_path = metadata.get("storage_path")
        client_id = metadata.get("client_id")
        if not storage_path or not client_id:
            await ctx["db"].update_document_status(
                document["document_id"],
                "failed",
                metadata={"error": "Recovery metadata is missing storage_path or client_id"},
            )
            continue

        job_id = (
            f"ingest:{document['document_id']}"
            if metadata.get("processing_started_at") is None
            else f"ingest-recovery:{document['document_id']}:{uuid.uuid4().hex}"
        )
        try:
            await ctx["redis"].enqueue_job(
                "ingest_job",
                document["document_id"],
                storage_path,
                document["source_type"],
                client_id,
                _job_id=job_id,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Could not requeue recovered document %s",
                document["document_id"],
            )


async def shutdown(ctx):
    pool = ctx.get("pool")
    if pool is not None:
        await pool.close()


class WorkerSettings:
    functions = [ingest_job]
    # Keep module import side-effect free; runtime settings are loaded in startup().
    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        database=0,
    )
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
    max_tries = MAX_INGESTION_TRIES
    job_timeout = 900
    keep_result = 3600

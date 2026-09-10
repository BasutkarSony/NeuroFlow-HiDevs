from arq.connections import RedisSettings

from config import get_settings
from pipelines.ingestion.pipeline import process_document


async def ingest_job(
    ctx,
    document_id: str,
    file_path: str | None,
    source_type: str,
):
    return await process_document(
        document_id=document_id,
        file_path=file_path,
        source_type=source_type,
        db=ctx["db"],
        provider=ctx.get("provider"),
        tracer=ctx.get("tracer"),
    )


class WorkerSettings:
    functions = [ingest_job]

    @staticmethod
    async def startup(ctx):
        settings = get_settings()

        ctx["redis_settings"] = RedisSettings(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            database=0,
        )
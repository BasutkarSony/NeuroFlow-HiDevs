import hashlib
import os
import tempfile
import uuid
from pathlib import Path

import asyncpg
import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker

from backend.db.migrations import ensure_schema
from pipelines.ingestion.repository import DocumentRepository
from pipelines.ingestion.worker import ingest_job


@pytest.mark.asyncio
async def test_arq_worker_consumes_queued_job_and_persists_document():
    database_url = os.getenv("TEST_DATABASE_URL")
    redis_url = os.getenv("TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("TEST_DATABASE_URL and TEST_REDIS_URL are required")

    database = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    repository = DocumentRepository(database)
    queue = await create_pool(RedisSettings.from_dsn(redis_url))
    document_id = None
    source_path = None
    job_id = f"ingestion-worker-e2e:{uuid.uuid4()}"

    content = (
        "NeuroFlow processes documents through a durable queue. "
        "This test verifies that an ARQ worker consumes a Redis job, "
        "extracts the source text, and persists document chunks."
    )

    try:
        # Each integration test must prepare its own schema; test order is not guaranteed.
        await ensure_schema(database)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            delete=False,
        ) as source:
            source.write(content)
            source_path = Path(source.name)

        document_id = await repository.create_document(
            filename="arq-worker-e2e.txt",
            source_type="text",
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            pipeline_id=None,
            metadata={"client_id": "arq-worker-e2e"},
        )
        assert document_id is not None

        queued_job = await queue.enqueue_job(
            "ingest_job",
            document_id,
            str(source_path),
            "text",
            "arq-worker-e2e",
            _job_id=job_id,
        )
        assert queued_job is not None

        worker = Worker(
            functions=[ingest_job],
            redis_settings=RedisSettings.from_dsn(redis_url),
            burst=True,
            max_jobs=1,
            poll_delay=0.01,
            handle_signals=False,
            ctx={"db": repository, "provider": None, "tracer": None},
        )
        await worker.main()

        async with database.acquire() as connection:
            document = await connection.fetchrow(
                "SELECT status, chunk_count FROM documents WHERE id = $1",
                uuid.UUID(document_id),
            )
            chunks = await connection.fetch(
                "SELECT content FROM chunks WHERE document_id = $1 ORDER BY chunk_index",
                uuid.UUID(document_id),
            )

        assert document is not None
        assert document["status"] == "complete"
        assert document["chunk_count"] == len(chunks)
        assert chunks
        assert content in " ".join(row["content"] for row in chunks)

        result = await queued_job.result(timeout=1)
        assert result["document_id"] == document_id
        assert result["duplicate"] is False
    finally:
        if document_id:
            async with database.acquire() as connection:
                await connection.execute(
                    "DELETE FROM documents WHERE id = $1",
                    uuid.UUID(document_id),
                )
        if source_path:
            source_path.unlink(missing_ok=True)
        await queue.aclose()
        await database.close()

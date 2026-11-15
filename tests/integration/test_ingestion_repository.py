import os
import uuid

import asyncpg
import pytest
from arq import create_pool
from arq.connections import RedisSettings

from pipelines.ingestion.repository import DocumentRepository


@pytest.mark.asyncio
async def test_document_repository_persists_chunks_and_embeddings():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    assert pool is not None
    document_id = None
    try:
        repository = DocumentRepository(pool)
        content_hash = uuid.uuid4().hex
        document_id = await repository.create_document(
            filename="integration.txt",
            source_type="text",
            content_hash=content_hash,
            pipeline_id=None,
            metadata={"client_id": "integration-test"},
        )
        assert document_id is not None

        embedding = [0.01] * 1536
        await repository.insert_chunks(
            document_id,
            [
                {
                    "content": "NeuroFlow ingestion integration test",
                    "token_count": 5,
                    "embedding": embedding,
                    "metadata": {"strategy": "integration"},
                }
            ],
        )
        await repository.update_document_status(
            document_id,
            "complete",
            metadata={"page_count": 1},
            chunk_count=1,
        )

        async with pool.acquire() as connection:
            document = await connection.fetchrow(
                "SELECT status, chunk_count FROM documents WHERE id = $1",
                uuid.UUID(document_id),
            )
            chunk = await connection.fetchrow(
                "SELECT content, embedding IS NOT NULL AS embedded FROM chunks WHERE document_id = $1",
                uuid.UUID(document_id),
            )

        assert document["status"] == "complete"
        assert document["chunk_count"] == 1
        assert chunk["content"] == "NeuroFlow ingestion integration test"
        assert chunk["embedded"] is True
    finally:
        if document_id:
            async with pool.acquire() as connection:
                await connection.execute(
                    "DELETE FROM documents WHERE id = $1",
                    uuid.UUID(document_id),
                )
        await pool.close()


@pytest.mark.asyncio
async def test_arq_can_enqueue_ingestion_job():
    redis_url = os.getenv("TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_REDIS_URL is not configured")

    settings = RedisSettings.from_dsn(redis_url)
    queue = await create_pool(settings)
    job_id = f"ingestion-integration:{uuid.uuid4()}"
    try:
        job = await queue.enqueue_job(
            "ingest_job",
            str(uuid.uuid4()),
            "/tmp/neuroflow-integration-source",
            "text",
            _job_id=job_id,
        )
        assert job is not None
        assert job.job_id == job_id
    finally:
        await queue.aclose()

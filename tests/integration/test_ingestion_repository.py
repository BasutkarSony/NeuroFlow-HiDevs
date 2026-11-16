import hashlib
import os
import tempfile
import uuid
from pathlib import Path

import asyncpg
import pytest
from arq import create_pool
from arq.connections import RedisSettings

from pipelines.ingestion.repository import DocumentRepository
from pipelines.ingestion.worker import ingest_job


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

        owned_document = await repository.get_document_for_client(
            document_id,
            "integration-test",
        )
        foreign_document = await repository.get_document_for_client(
            document_id,
            "another-client",
        )
        assert owned_document is not None
        assert str(owned_document["id"]) == document_id
        assert foreign_document is None

        owned_duplicate = await repository.get_document_by_hash(
            content_hash,
            "integration-test",
        )
        foreign_duplicate = await repository.get_document_by_hash(
            content_hash,
            "another-client",
        )
        assert owned_duplicate is not None
        assert str(owned_duplicate["id"]) == document_id
        assert foreign_duplicate is None
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
            "integration-test",
            _job_id=job_id,
        )
        assert job is not None
        assert job.job_id == job_id
    finally:
        await queue.aclose()

@pytest.mark.asyncio
async def test_ingestion_worker_processes_text_document_end_to_end():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    repository = DocumentRepository(pool)
    document_id = None
    source_path = None
    try:
        content = (
            "NeuroFlow is a document processing platform. "
            "This integration test verifies that the worker handler extracts "
            "plain text, chunks it, and persists the result in PostgreSQL."
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            delete=False,
        ) as source:
            source.write(content)
            source_path = Path(source.name)

        document_id = await repository.create_document(
            filename="worker-integration.txt",
            source_type="text",
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            pipeline_id=None,
            metadata={"client_id": "worker-integration-test"},
        )
        assert document_id is not None

        result = await ingest_job(
            {"db": repository, "provider": None, "tracer": None},
            document_id,
            str(source_path),
            "text",
            "worker-integration-test",
        )

        assert result["document_id"] == document_id
        assert result["duplicate"] is False
        assert result["chunk_count"] >= 1
        assert result["embedding_count"] == 0

        async with pool.acquire() as connection:
            document = await connection.fetchrow(
                "SELECT status, chunk_count FROM documents WHERE id = $1",
                uuid.UUID(document_id),
            )
            chunks = await connection.fetch(
                "SELECT content FROM chunks WHERE document_id = $1 ORDER BY chunk_index",
                uuid.UUID(document_id),
            )

        assert document["status"] == "complete"
        assert document["chunk_count"] == len(chunks)
        assert content in " ".join(row["content"] for row in chunks)
    finally:
        if document_id:
            async with pool.acquire() as connection:
                await connection.execute(
                    "DELETE FROM documents WHERE id = $1",
                    uuid.UUID(document_id),
                )
        if source_path:
            source_path.unlink(missing_ok=True)
        await pool.close()

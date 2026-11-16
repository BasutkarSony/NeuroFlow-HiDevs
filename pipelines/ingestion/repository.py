import json
import uuid
from typing import Any

import asyncpg


class DocumentRepository:
    """Persistence adapter used by the ingestion API and ARQ worker."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create_document(
        self,
        *,
        filename: str,
        source_type: str,
        content_hash: str,
        pipeline_id: str | None,
        metadata: dict[str, Any],
    ) -> str | None:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO documents (
                    filename, source_type, content_hash, pipeline_id,
                    metadata, status
                )
                VALUES ($1, $2, $3, $4, $5::jsonb, 'queued')
                ON CONFLICT ((metadata->>'client_id'), content_hash) DO NOTHING
                RETURNING id
                """,
                filename,
                source_type,
                content_hash,
                uuid.UUID(pipeline_id) if pipeline_id else None,
                json.dumps(metadata),
            )
        return str(row["id"]) if row else None

    async def get_document_by_hash(self, content_hash: str, client_id: str):
        """Return a duplicate only when it belongs to the requesting client."""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(
                """
                SELECT id, status
                FROM documents
                WHERE content_hash = $1
                  AND metadata->>'client_id' = $2
                """,
                content_hash,
                client_id,
            )

    async def update_document_status(
        self,
        document_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
        chunk_count: int | None = None,
    ) -> None:
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE documents
                SET status = $2,
                    metadata = metadata || $3::jsonb,
                    chunk_count = COALESCE($4, chunk_count)
                WHERE id = $1
                """,
                uuid.UUID(document_id),
                status,
                json.dumps(metadata or {}),
                chunk_count,
            )

    async def insert_chunks(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM chunks WHERE document_id = $1",
                    uuid.UUID(document_id),
                )
                for index, chunk in enumerate(chunks):
                    embedding = chunk.get("embedding")
                    vector_value = (
                        "[" + ",".join(str(value) for value in embedding) + "]"
                        if embedding is not None
                        else None
                    )
                    await connection.execute(
                        """
                        INSERT INTO chunks (
                            document_id, content, embedding, chunk_index,
                            token_count, metadata
                        )
                        VALUES ($1, $2, $3::vector, $4, $5, $6::jsonb)
                        """,
                        uuid.UUID(document_id),
                        chunk["content"],
                        vector_value,
                        index,
                        chunk["token_count"],
                        json.dumps(chunk.get("metadata", {})),
                    )

    async def get_document_for_client(
        self,
        document_id: str,
        client_id: str,
    ):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(
                """
                SELECT id, filename, source_type, status, chunk_count,
                       metadata, created_at
                FROM documents
                WHERE id = $1
                  AND metadata->>'client_id' = $2
                """,
                uuid.UUID(document_id),
                client_id,
            )

    async def recoverable_ingestion_documents(self):
        """
        Claim queued documents whose enqueue may have been interrupted and
        processing documents whose ARQ worker lease should have expired.
        A transaction-scoped advisory lock prevents concurrent workers from
        claiming the same recovery batch.
        """
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext('neuroflow-ingestion-recovery'))"
                )
                rows = await connection.fetch(
                    """
                    SELECT id, source_type, metadata
                    FROM documents
                    WHERE (
                        status = 'queued'
                        AND created_at < NOW() - INTERVAL '30 seconds'
                    )
                    OR (
                        status = 'processing'
                        AND COALESCE(
                            NULLIF(metadata->>'processing_started_at', '')::timestamptz,
                            created_at
                        ) < NOW() - INTERVAL '16 minutes'
                    )
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 100
                    """
                )
                if rows:
                    await connection.execute(
                        """
                        UPDATE documents
                        SET status = 'queued'
                        WHERE id = ANY($1::uuid[])
                        """,
                        [row["id"] for row in rows],
                    )
                return [
                    {
                        "document_id": str(row["id"]),
                        "source_type": row["source_type"],
                        "metadata": (
                            json.loads(row["metadata"])
                            if isinstance(row["metadata"], str)
                            else row["metadata"]
                        ),
                    }
                    for row in rows
                ]

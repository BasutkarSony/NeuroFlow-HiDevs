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
                ON CONFLICT (content_hash) DO NOTHING
                RETURNING id
                """,
                filename,
                source_type,
                content_hash,
                uuid.UUID(pipeline_id) if pipeline_id else None,
                json.dumps(metadata),
            )
        return str(row["id"]) if row else None

    async def get_document_by_hash(self, content_hash: str):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(
                "SELECT id, status FROM documents WHERE content_hash = $1",
                content_hash,
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
                document_id,
                status,
                json.dumps(metadata or {}),
                chunk_count,
            )

    async def insert_chunks(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        if not chunks:
            return

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM chunks WHERE document_id = $1",
                    document_id,
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
                        document_id,
                        chunk["content"],
                        vector_value,
                        index,
                        chunk["token_count"],
                        json.dumps(chunk.get("metadata", {})),
                    )

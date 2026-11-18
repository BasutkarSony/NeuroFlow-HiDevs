import asyncio
import json
from typing import Any

from pipelines.retrieval.fusion import (
    RetrievalResult,
    reciprocal_rank_fusion,
)
from pipelines.retrieval.query_processor import (
    ProcessedQuery,
    QueryProcessor,
)


class HybridRetriever:
    def __init__(
        self,
        db,
        client_id: str,
        embedding_provider=None,
        query_processor=None,
        dense_k: int = 20,
        sparse_k: int = 20,
        metadata_k: int = 20,
        query_expansion: bool = True,
        fusion_k: int = 60,
        fusion_weights: list[float] | None = None,
    ):
        if not client_id or not client_id.strip():
            raise ValueError("client_id is required for tenant-scoped retrieval.")
        self.db = db
        self.client_id = client_id
        self.embedding_provider = embedding_provider
        self.query_processor = (
            query_processor or QueryProcessor(
                enable_expansion=query_expansion
            )
        )
        self.dense_k = dense_k
        self.sparse_k = sparse_k
        self.metadata_k = metadata_k
        self.fusion_k = fusion_k
        self.fusion_weights = fusion_weights or [1.0, 1.0, 1.0]

    async def retrieve(
        self,
        query: str,
        k: int = 20,
    ) -> list[RetrievalResult]:
        processed = await self.query_processor.process(query)

        queries = processed.expansions or [query]

        dense_tasks = [
            self._dense_retrieval(
                item,
                self.dense_k,
            )
            for item in queries
        ]

        dense_results = await asyncio.gather(
            *dense_tasks
        )

        dense = self._union_results(
            dense_results
        )

        sparse, metadata = await asyncio.gather(
            self._sparse_retrieval(
                query,
                self.sparse_k,
            ),
            self._metadata_retrieval(
                query,
                processed,
                self.metadata_k,
            ),
        )

        return reciprocal_rank_fusion(
            [dense, sparse, metadata],
            k=self.fusion_k,
            weights=self.fusion_weights,
        )

    async def _dense_retrieval(
        self,
        query: str,
        k: int,
    ) -> list[RetrievalResult]:
        if self.embedding_provider is None:
            return []

        embeddings = await self.embedding_provider.embed(
            [query]
        )

        embedding = embeddings[0]

        rows = await self.db.fetch(
            """
            SELECT
                c.id,
                c.content,
                c.metadata,
                c.embedding <=> $1::vector AS distance
            FROM chunks AS c
            JOIN documents AS d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL
              AND d.metadata->>'client_id' = $2
            ORDER BY c.embedding <=> $1::vector
            LIMIT $3
            """,
            embedding,
            self.client_id,
            k,
        )

        return [
            RetrievalResult(
                chunk_id=str(row["id"]),
                content=row["content"],
                score=1.0 - float(row["distance"]),
                metadata=row["metadata"],
                source="dense",
            )
            for row in rows
        ]

    async def _sparse_retrieval(
        self,
        query: str,
        k: int,
    ) -> list[RetrievalResult]:
        rows = await self.db.fetch(
            """
            SELECT
                c.id,
                c.content,
                c.metadata,
                ts_rank_cd(
                    to_tsvector('english', c.content),
                    plainto_tsquery('english', $1)
                ) AS rank
            FROM chunks AS c
            JOIN documents AS d ON d.id = c.document_id
            WHERE d.metadata->>'client_id' = $2
              AND to_tsvector(
                  'english',
                  c.content
              ) @@ plainto_tsquery(
                  'english',
                  $1
              )
            ORDER BY rank DESC
            LIMIT $3
            """,
            query,
            self.client_id,
            k,
        )

        return [
            RetrievalResult(
                chunk_id=str(row["id"]),
                content=row["content"],
                score=float(row["rank"]),
                metadata=row["metadata"],
                source="sparse",
            )
            for row in rows
        ]

    async def _metadata_retrieval(
        self,
        query: str,
        processed: ProcessedQuery,
        k: int,
    ) -> list[RetrievalResult]:
        filters = processed.filters

        if not filters:
            return []

        metadata = json.dumps(filters)

        if self.embedding_provider is None:
            return []

        embeddings = await self.embedding_provider.embed(
            [query]
        )

        embedding = embeddings[0]

        rows = await self.db.fetch(
            """
            SELECT
                c.id,
                c.content,
                c.metadata,
                c.embedding <=> $1::vector AS distance
            FROM chunks AS c
            JOIN documents AS d ON d.id = c.document_id
            WHERE d.metadata->>'client_id' = $3
              AND c.metadata @> $2::jsonb
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> $1::vector
            LIMIT $4
            """,
            embedding,
            metadata,
            self.client_id,
            k,
        )

        return [
            RetrievalResult(
                chunk_id=str(row["id"]),
                content=row["content"],
                score=1.0 - float(row["distance"]),
                metadata=row["metadata"],
                source="metadata",
            )
            for row in rows
        ]

    @staticmethod
    def _union_results(
        result_lists: list[list[RetrievalResult]],
    ) -> list[RetrievalResult]:
        merged: dict[str, RetrievalResult] = {}

        for results in result_lists:
            for result in results:
                existing = merged.get(result.chunk_id)

                if existing is None or result.score > existing.score:
                    merged[result.chunk_id] = result

        return list(merged.values())
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
        embedding_provider=None,
        query_processor=None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider
        self.query_processor = (
            query_processor or QueryProcessor()
        )

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
                k,
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
                k,
            ),
            self._metadata_retrieval(
                query,
                processed,
                k,
            ),
        )

        return reciprocal_rank_fusion(
            [dense, sparse, metadata],
            k=60,
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
                id,
                content,
                metadata,
                embedding <=> $1::vector AS distance
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding,
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
                id,
                content,
                metadata,
                ts_rank_cd(
                    to_tsvector('english', content),
                    plainto_tsquery('english', $1)
                ) AS rank
            FROM chunks
            WHERE to_tsvector(
                'english',
                content
            ) @@ plainto_tsquery(
                'english',
                $1
            )
            ORDER BY rank DESC
            LIMIT $2
            """,
            query,
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
                id,
                content,
                metadata,
                embedding <=> $1::vector AS distance
            FROM chunks
            WHERE metadata @> $2::jsonb
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            embedding,
            metadata,
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
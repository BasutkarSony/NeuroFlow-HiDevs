from typing import Any

from pipelines.retrieval.context_assembler import ContextAssembler
from pipelines.retrieval.reranker import CrossEncoderReranker
from pipelines.retrieval.retriever import HybridRetriever


class RetrievalPipeline:
    def __init__(
        self,
        db,
        embedding_provider=None,
        query_processor=None,
        reranker=None,
        token_budget: int = 4000,
        dense_k: int = 20,
        sparse_k: int = 20,
        metadata_k: int = 20,
        candidate_k: int = 40,
        reranker_candidate_k: int | None = None,
        query_expansion: bool = True,
        fusion_k: int = 60,
        fusion_weights: list[float] | None = None,
    ):
        self.candidate_k = candidate_k
        self.reranker_candidate_k = (
            reranker_candidate_k or candidate_k
        )

        self.retriever = HybridRetriever(
            db=db,
            embedding_provider=embedding_provider,
            query_processor=query_processor,
            dense_k=dense_k,
            sparse_k=sparse_k,
            metadata_k=metadata_k,
            query_expansion=query_expansion,
            fusion_k=fusion_k,
            fusion_weights=fusion_weights,
        )

        self.reranker = (
            reranker or CrossEncoderReranker()
        )

        self.context_assembler = ContextAssembler(
            token_budget=token_budget
        )

    async def retrieve(
        self,
        query: str,
        k: int = 10,
    ) -> dict[str, Any]:
        fused = await self.retriever.retrieve(
            query,
            k=self.candidate_k,
        )

        rerank_candidates = fused[
            :self.reranker_candidate_k
        ]

        reranked = await self.reranker.rerank(
            query,
            rerank_candidates,
            top_k=k,
        )

        return self.context_assembler.assemble(
            reranked
        )

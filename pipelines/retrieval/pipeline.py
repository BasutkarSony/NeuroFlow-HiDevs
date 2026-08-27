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
    ):
        self.retriever = HybridRetriever(
            db=db,
            embedding_provider=embedding_provider,
            query_processor=query_processor,
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
            k=40,
        )

        reranked = await self.reranker.rerank(
            query,
            fused[:40],
            top_k=k,
        )

        return self.context_assembler.assemble(
            reranked
        )

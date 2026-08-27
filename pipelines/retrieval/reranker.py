from pipelines.retrieval.fusion import RetrievalResult


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        import asyncio

        if not candidates:
            return []

        pairs = [
            (query, candidate.content)
            for candidate in candidates[:40]
        ]

        scores = await asyncio.to_thread(
            self.model.predict,
            pairs,
        )

        ranked = list(
            zip(candidates[:40], scores)
        )

        ranked.sort(
            key=lambda item: float(item[1]),
            reverse=True,
        )

        results = []

        for candidate, score in ranked[:top_k]:
            candidate.score = float(score)
            results.append(candidate)

        return results
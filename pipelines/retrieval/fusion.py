from dataclasses import dataclass
from typing import Any


@dataclass
class RetrievalResult:
    chunk_id: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] | None = None
    source: str = ""


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievalResult]],
    k: int = 60,
) -> list[RetrievalResult]:
    fused: dict[str, RetrievalResult] = {}
    scores: dict[str, float] = {}

    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            scores[result.chunk_id] = (
                scores.get(result.chunk_id, 0.0)
                + 1.0 / (k + rank)
            )

            if result.chunk_id not in fused:
                fused[result.chunk_id] = result

    ranked = sorted(
        fused.values(),
        key=lambda result: scores[result.chunk_id],
        reverse=True,
    )

    for result in ranked:
        result.score = scores[result.chunk_id]

    return ranked
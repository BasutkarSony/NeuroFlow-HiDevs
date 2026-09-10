from dataclasses import dataclass, replace
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
    weights: list[float] | None = None,
) -> list[RetrievalResult]:
    fused: dict[str, RetrievalResult] = {}
    scores: dict[str, float] = {}

    if weights is None:
        weights = [1.0] * len(result_lists)

    if len(weights) != len(result_lists):
        raise ValueError("weights must match result_lists")

    for list_index, results in enumerate(result_lists):
        weight = max(float(weights[list_index]), 0.0)

        for rank, result in enumerate(results, start=1):
            scores[result.chunk_id] = (
                scores.get(result.chunk_id, 0.0)
                + weight / (k + rank)
            )

            if result.chunk_id not in fused:
                fused[result.chunk_id] = result

    ranked = sorted(
        fused.values(),
        key=lambda result: scores[result.chunk_id],
        reverse=True,
    )

    return [
        replace(result, score=scores[result.chunk_id])
        for result in ranked
    ]

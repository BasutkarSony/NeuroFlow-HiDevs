import asyncio
import json
from pathlib import Path
from typing import Any


async def evaluate(
    pipeline,
    test_set: list[dict[str, Any]],
    k: int = 10,
) -> dict[str, Any]:
    hits = 0
    reciprocal_ranks = []

    details = []

    for test in test_set:
        results = await pipeline.retrieve(
            test["query"],
            k=k,
        )

        relevant_ids = {
            str(chunk_id)
            for chunk_id in test["relevant_chunk_ids"]
        }

        hit_rank = None

        for rank, result in enumerate(results["chunks_used"], start=1):
            if str(result.chunk_id) in relevant_ids:
                hit_rank = rank
                break

        if hit_rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / hit_rank)
        else:
            reciprocal_ranks.append(0.0)

        details.append(
            {
                "query": test["query"],
                "hit": hit_rank is not None,
                "rank": hit_rank,
            }
        )

    total = len(test_set)

    hit_rate = hits / total if total else 0.0
    mrr = (
        sum(reciprocal_ranks) / total
        if total
        else 0.0
    )

    return {
        "test_count": total,
        "hit_rate": hit_rate,
        "mrr": mrr,
        "details": details,
    }


def save_results(
    results: dict[str, Any],
    output_path: str = "evaluation/retrieval_results.json",
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            results,
            indent=2,
        )
    )


if __name__ == "__main__":
    print(
        "Load the evaluation dataset and RetrievalPipeline "
        "before running evaluate()."
    )

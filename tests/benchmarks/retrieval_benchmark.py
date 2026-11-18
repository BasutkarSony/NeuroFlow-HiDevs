import json
import math
import time
from pathlib import Path
from typing import Any


def validate_dataset(dataset: Any) -> list[dict[str, Any]]:
    """Validate manually labelled retrieval examples before running a benchmark."""
    if not isinstance(dataset, list) or not dataset:
        raise ValueError("The retrieval evaluation dataset must be a non-empty list.")

    for index, item in enumerate(dataset):
        if not isinstance(item, dict):
            raise ValueError(f"Dataset item {index} must be an object.")

        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Dataset item {index} must contain a non-empty query.")

        relevant_ids = item.get("relevant_chunk_ids")
        if (
            not isinstance(relevant_ids, list)
            or not relevant_ids
            or any(
                not isinstance(chunk_id, (str, int))
                or not str(chunk_id).strip()
                for chunk_id in relevant_ids
            )
        ):
            raise ValueError(
                f"Dataset item {index} must contain non-empty relevant_chunk_ids."
            )

    return dataset


async def benchmark(
    pipeline,
    dataset: list[dict[str, Any]],
    k: int = 10,
) -> dict[str, Any]:
    if k < 1:
        raise ValueError("k must be greater than zero.")

    dataset = validate_dataset(dataset)
    hits = 0
    reciprocal_ranks = []
    latencies = []

    for item in dataset:
        started = time.perf_counter()
        result = await pipeline.retrieve(item["query"], k=k)
        latencies.append((time.perf_counter() - started) * 1000)

        relevant = {str(value) for value in item["relevant_chunk_ids"]}
        rank = next(
            (
                index
                for index, chunk in enumerate(result["chunks_used"], start=1)
                if str(chunk.chunk_id) in relevant
            ),
            None,
        )

        if rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    total = len(dataset)
    return {
        "test_count": total,
        "k": k,
        "hit_rate_at_k": hits / total,
        "mrr_at_k": sum(reciprocal_ranks) / total,
        "p95_latency_ms": percentile(latencies, 0.95),
    }


def percentile(values: list[float], p: float) -> float:
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be between 0 and 1.")
    if not values:
        return 0.0
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Percentile values must all be finite.")

    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower

    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def load_dataset(
    path: str = "evaluation/retrieval_test_set.json",
) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Retrieval dataset not found: {path}")

    try:
        dataset = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Retrieval dataset is not valid JSON: {path}") from exc

    return validate_dataset(dataset)


if __name__ == "__main__":
    try:
        dataset = load_dataset()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Retrieval benchmark is not ready: {exc}") from exc

    print(
        f"Validated {len(dataset)} labelled retrieval examples. "
        "Load the configured retrieval pipeline and call benchmark()."
    )

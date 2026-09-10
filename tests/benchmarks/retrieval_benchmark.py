import asyncio
import json
import time
from pathlib import Path


async def benchmark(
    pipeline,
    dataset,
    k=10,
):
    hits = 0
    reciprocal_ranks = []
    latencies = []

    for item in dataset:
        started = time.perf_counter()

        result = await pipeline.retrieve(
            item["query"],
            k=k,
        )

        latencies.append(
            (time.perf_counter() - started) * 1000
        )

        relevant = {
            str(value)
            for value in item["relevant_chunk_ids"]
        }

        rank = None

        for index, chunk in enumerate(
            result["chunks_used"],
            start=1,
        ):
            if str(chunk.chunk_id) in relevant:
                rank = index
                break

        if rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    total = len(dataset)

    return {
        "test_count": total,
        "hit_rate_at_10": hits / total if total else 0.0,
        "mrr_at_10": (
            sum(reciprocal_ranks) / total
            if total
            else 0.0
        ),
        "p95_latency_ms": percentile(
            latencies,
            0.95,
        ),
    }


def percentile(values, p):
    if not values:
        return 0.0

    values = sorted(values)
    position = (len(values) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower

    return (
        values[lower]
        + (values[upper] - values[lower]) * fraction
    )


def load_dataset(
    path="evaluation/retrieval_test_set.json",
):
    file = Path(path)

    if not file.exists():
        raise FileNotFoundError(
            f"Retrieval dataset not found: {path}"
        )

    return json.loads(file.read_text())


if __name__ == "__main__":
    print(
        "Load the retrieval pipeline and call "
        "benchmark() with evaluation/retrieval_test_set.json."
    )

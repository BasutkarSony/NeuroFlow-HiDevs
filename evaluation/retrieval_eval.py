import argparse
import asyncio
import json
from pathlib import Path
from typing import Any


async def evaluate(
    pipeline,
    test_set: list[dict[str, Any]],
    k: int = 10,
) -> dict[str, Any]:
    """Evaluate retrieval results against manually labelled relevant chunk IDs."""
    if not test_set:
        raise ValueError("The retrieval evaluation dataset is empty.")

    hits = 0
    reciprocal_ranks = []
    details = []

    for test in test_set:
        results = await pipeline.retrieve(test["query"], k=k)
        relevant_ids = {
            str(chunk_id) for chunk_id in test["relevant_chunk_ids"]
        }
        hit_rank = next(
            (
                rank
                for rank, result in enumerate(results["chunks_used"], start=1)
                if str(result.chunk_id) in relevant_ids
            ),
            None,
        )

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
    return {
        "test_count": total,
        "hit_rate": hits / total,
        "mrr": sum(reciprocal_ranks) / total,
        "details": details,
    }


def save_results(
    results: dict[str, Any],
    output_path: str = "evaluation/retrieval_results.json",
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def check_evaluation_readiness() -> int:
    """Validate checked-in evaluation metadata without inventing benchmark scores."""
    quality_path = Path("evaluation/quality_final.json")
    if not quality_path.is_file():
        raise FileNotFoundError(f"Missing evaluation record: {quality_path}")

    record = json.loads(quality_path.read_text(encoding="utf-8"))
    status = record.get("status")
    if status not in {"measured", "not_measurable"}:
        raise ValueError(
            "quality_final.json must declare status as measured or not_measurable."
        )

    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("quality_final.json must contain a metrics object.")

    if status == "not_measurable":
        populated = [name for name, value in metrics.items() if value is not None]
        if populated:
            raise ValueError(
                "Metrics must remain null while status is not_measurable: "
                + ", ".join(populated)
            )
        print(
            "Evaluation metadata is valid. Retrieval scores remain unmeasured "
            "because no labelled ground-truth dataset is available."
        )
        return 0

    mrr = metrics.get("retrieval_mrr_at_10")
    if not isinstance(mrr, (int, float)) or not 0.0 <= mrr <= 1.0:
        raise ValueError(
            "A measured record must include retrieval_mrr_at_10 between 0 and 1."
        )
    print("Evaluation metadata is valid and contains a measured MRR.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate NeuroFlow retrieval evaluation readiness."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate evaluation metadata without claiming benchmark results.",
    )
    args = parser.parse_args()

    if args.check:
        try:
            return check_evaluation_readiness()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            parser.exit(1, f"Evaluation readiness check failed: {exc}\n")

    parser.error(
        "Direct benchmark execution is not configured yet. Use --check to "
        "validate the checked-in evaluation metadata."
    )


if __name__ == "__main__":
    raise SystemExit(main())

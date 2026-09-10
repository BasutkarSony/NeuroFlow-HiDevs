import json
from pathlib import Path
from statistics import mean
from typing import Any


FIELDS = (
    "faithfulness",
    "answer_relevance",
    "context_precision",
    "context_recall",
    "overall_score",
)


def load_dataset(
    path: str = "evaluation/calibration/annotated_set.json",
) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text())


def summarize_scores(
    scores: list[dict[str, Any]],
) -> dict[str, Any]:
    averages = {}

    for field in FIELDS:
        values = [
            float(item[field])
            for item in scores
            if item.get(field) is not None
        ]
        averages[field] = (
            mean(values)
            if values
            else 0.0
        )

    return {
        "test_count": len(scores),
        "averages": averages,
        "details": scores,
    }


async def evaluate(
    judge,
    dataset: list[dict[str, Any]],
    run_id_factory,
) -> dict[str, Any]:
    """
    Evaluate a dataset using a configured EvaluationJudge.

    run_id_factory(item) must return a valid pipeline-run UUID
    associated with the evaluation in the application's database.
    """
    scores = []

    for item in dataset:
        chunks = [
            item["context"]
        ]

        result = await judge.evaluate(
            run_id=run_id_factory(item),
            query=item["query"],
            answer=item["answer"],
            context=item["context"],
            chunks=chunks,
        )

        scores.append(result)

    return summarize_scores(scores)


def save_results(
    results: dict[str, Any],
    output_path: str = "evaluation/generation_results.json",
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
    dataset = load_dataset()

    print(
        f"Loaded {len(dataset)} calibration examples."
    )
    print(
        "A configured EvaluationJudge and valid "
        "pipeline-run IDs are required for live scoring."
    )

from statistics import mean
from pathlib import Path

import mlflow


def start_training_job(
    job_id,
    pairs,
    base_model: str,
    training_data_path: str,
) -> str:
    scores = [float(pair.quality_score) for pair in pairs]

    dates = []
    for pair in pairs:
        if hasattr(pair, "created_at") and pair.created_at:
            dates.append(pair.created_at)

    date_range = (
        f"{min(dates)} to {max(dates)}"
        if dates
        else "unknown"
    )

    with mlflow.start_run(
        run_name=f"finetune-{job_id}"
    ) as run:
        mlflow.log_params(
            {
                "base_model": base_model,
                "training_pair_count": len(pairs),
                "avg_quality_score": (
                    mean(scores) if scores else 0.0
                ),
                "date_range": date_range,
            }
        )

        if Path(training_data_path).exists():
            mlflow.log_artifact(training_data_path)

        return run.info.run_id


def log_training_metrics(
    training_loss: float,
    validation_loss: float,
    trained_tokens: int,
) -> None:
    mlflow.log_metrics(
        {
            "training_loss": training_loss,
            "validation_loss": validation_loss,
            "training_token_count": trained_tokens,
        }
    )


def register_fine_tuned_model(
    run_id: str,
    job_id: str,
):
    return mlflow.register_model(
        f"runs:/{run_id}/model",
        f"neuroflow-finetune-{job_id}",
    )

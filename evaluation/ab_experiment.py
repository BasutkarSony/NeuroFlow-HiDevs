import os
from typing import Any

import mlflow


EXPERIMENT_NAME = "NeuroFlow-Task18-Quality"


BASELINE_CONFIG = {
    "candidate_k": 20,
    "reranker_candidate_k": 20,
    "fusion_k": 60,
    "dense_weight": 1.0,
    "sparse_weight": 1.0,
    "metadata_weight": 1.0,
    "metadata_k": 20,
    "query_expansion": False,
}

IMPROVED_CONFIG = {
    "candidate_k": 40,
    "reranker_candidate_k": 40,
    "fusion_k": 60,
    "dense_weight": 1.5,
    "sparse_weight": 1.0,
    "metadata_weight": 1.0,
    "metadata_k": 20,
    "query_expansion": True,
}


def log_run(name: str, config: dict[str, Any], metrics: dict[str, float] | None = None):
    with mlflow.start_run(run_name=name):
        mlflow.log_params(config)
        mlflow.set_tag("task", "task-18")
        mlflow.set_tag("measurement_status", "not_measurable")
        if metrics:
            mlflow.log_metrics(metrics)


def main():
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    log_run("baseline", BASELINE_CONFIG)
    log_run("improved", IMPROVED_CONFIG)

    print(f"MLflow experiment: {EXPERIMENT_NAME}")
    print(f"Tracking URI: {tracking_uri}")
    print("A/B configurations logged successfully.")
    print("Metrics remain not measurable until a retrieval ground-truth dataset is available.")


if __name__ == "__main__":
    main()

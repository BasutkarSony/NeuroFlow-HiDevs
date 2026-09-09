import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from db.pool import db_pool
from pipelines.finetuning.extractor import (
    extract_training_pairs,
    _format_pair,
)
from pipelines.finetuning.job_manager import (
    submit_finetune_job,
)
from pipelines.finetuning.tracker import (
    start_training_job,
)
from security.auth import ClientProfile, require_scope


router = APIRouter(prefix="/finetune")


class FinetuneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_model: str = "gpt-4o-mini"


@router.get("/training-data/preview")
async def preview_training_data():
    db = db_pool.get_pool()

    rows = await db.fetch(
        """
        SELECT
            tp.id,
            tp.system_prompt,
            tp.user_message,
            tp.assistant_message,
            tp.quality_score
        FROM training_pairs tp
        JOIN pipeline_runs pr
            ON pr.id = tp.run_id
        LEFT JOIN evaluations e
            ON e.run_id = pr.id
        WHERE tp.quality_score >= 0.82
          AND tp.included_in_job IS NULL
          AND (e.user_rating >= 4 OR e.user_rating IS NULL)
        ORDER BY tp.created_at ASC
        LIMIT 5
        """
    )

    return {
        "count": len(rows),
        "samples": [
            _format_pair(dict(row))
            for row in rows
        ],
    }


@router.post("/jobs")
async def create_finetune_job(
    request: FinetuneRequest,
    current_user: ClientProfile = Depends(require_scope("admin")),
):
    db = db_pool.get_pool()
    job_id = str(uuid.uuid4())

    pairs = await extract_training_pairs(
        db,
        job_id,
    )

    if not pairs:
        raise HTTPException(
            400,
            "No qualifying training pairs found",
        )

    path = f"training_data/{job_id}.jsonl"

    mlflow_run_id = start_training_job(
        job_id,
        pairs,
        request.base_model,
        path,
    )

    provider_job_id = await submit_finetune_job(
        path,
        request.base_model,
    )

    await db.execute(
        """
        INSERT INTO finetune_jobs (
            id,
            provider_job_id,
            base_model,
            status,
            training_pair_count,
            mlflow_run_id
        )
        VALUES (
            $1::uuid,
            $2,
            $3,
            'submitted',
            $4,
            $5
        )
        """,
        job_id,
        provider_job_id,
        request.base_model,
        len(pairs),
        mlflow_run_id,
    )

    return {
        "job_id": job_id,
        "provider_job_id": provider_job_id,
        "training_pair_count": len(pairs),
        "mlflow_run_id": mlflow_run_id,
    }


@router.get("/jobs")
async def list_finetune_jobs():
    db = db_pool.get_pool()

    rows = await db.fetch(
        """
        SELECT
            id,
            provider_job_id,
            base_model,
            status,
            training_pair_count,
            mlflow_run_id,
            metrics,
            created_at,
            completed_at
        FROM finetune_jobs
        ORDER BY created_at DESC
        """
    )

    return [
        {
            "job_id": str(row["id"]),
            "provider_job_id": row["provider_job_id"],
            "base_model": row["base_model"],
            "status": row["status"],
            "training_pair_count": row["training_pair_count"],
            "mlflow_run_id": row["mlflow_run_id"],
            "metrics": row["metrics"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }
        for row in rows
    ]


@router.get("/jobs/{job_id}")
async def get_finetune_job(job_id: str):
    db = db_pool.get_pool()

    row = await db.fetchrow(
        """
        SELECT *
        FROM finetune_jobs
        WHERE id = $1::uuid
        """,
        job_id,
    )

    if row is None:
        raise HTTPException(404, "Fine-tuning job not found")

    return {
        "job_id": str(row["id"]),
        "provider_job_id": row["provider_job_id"],
        "base_model": row["base_model"],
        "status": row["status"],
        "training_pair_count": row["training_pair_count"],
        "mlflow_run_id": row["mlflow_run_id"],
        "metrics": row["metrics"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }

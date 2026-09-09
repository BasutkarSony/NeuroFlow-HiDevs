import json
import statistics
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from db.pool import db_pool
from models.pipeline import PipelineConfig
from security.auth import ClientProfile, require_scope
from security.validators import sanitize_text, validate_pipeline_name


router = APIRouter(prefix="/pipelines")


@router.post("")
async def create_pipeline(
    config: PipelineConfig,
    current_user: ClientProfile = Depends(require_scope("admin")),
):
    config.name = validate_pipeline_name(config.name)
    config.description = sanitize_text(config.description).strip()

    db = db_pool.get_pool()

    row = await db.fetchrow(
        """
        INSERT INTO pipelines (
            name,
            description,
            config,
            version,
            status
        )
        VALUES ($1, $2, $3::jsonb, 1, 'active')
        RETURNING id, version
        """,
        config.name,
        config.description,
        json.dumps(config.model_dump()),
    )

    return {
        "pipeline_id": str(row["id"]),
        "version": row["version"],
    }


@router.get("")
async def list_pipelines():
    db = db_pool.get_pool()

    rows = await db.fetch(
        """
        SELECT
            p.id,
            p.name,
            p.description,
            p.version,
            p.status,
            p.created_at,
            MAX(pr.created_at) AS last_run,
            AVG(e.overall_score) AS average_eval_score
        FROM pipelines p
        LEFT JOIN pipeline_runs pr
            ON pr.pipeline_id = p.id
        LEFT JOIN evaluations e
            ON e.run_id = pr.id
        WHERE p.status != 'archived'
        GROUP BY p.id
        ORDER BY p.created_at DESC
        """
    )

    return [
        {
            "pipeline_id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "version": row["version"],
            "status": row["status"],
            "last_run": row["last_run"],
            "average_eval_score": (
                float(row["average_eval_score"])
                if row["average_eval_score"] is not None
                else None
            ),
        }
        for row in rows
    ]


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    db = db_pool.get_pool()

    row = await db.fetchrow(
        """
        SELECT
            p.*,
            AVG(e.overall_score) AS average_eval_score
        FROM pipelines p
        LEFT JOIN pipeline_runs pr
            ON pr.pipeline_id = p.id
        LEFT JOIN evaluations e
            ON e.run_id = pr.id
        WHERE p.id = $1::uuid
        GROUP BY p.id
        """,
        pipeline_id,
    )

    if row is None:
        raise HTTPException(404, "Pipeline not found")

    return {
        "pipeline_id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "config": row["config"],
        "version": row["version"],
        "status": row["status"],
        "average_eval_score": (
            float(row["average_eval_score"])
            if row["average_eval_score"] is not None
            else None
        ),
    }


@router.patch("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str,
    config: PipelineConfig,
):
    config.name = validate_pipeline_name(config.name)
    config.description = sanitize_text(config.description).strip()

    db = db_pool.get_pool()

    current = await db.fetchrow(
        """
        SELECT version
        FROM pipelines
        WHERE id = $1::uuid
          AND status != 'archived'
        """,
        pipeline_id,
    )

    if current is None:
        raise HTTPException(404, "Pipeline not found")

    new_version = current["version"] + 1

    row = await db.fetchrow(
        """
        UPDATE pipelines
        SET
            name = $1,
            description = $2,
            config = $3::jsonb,
            version = $4
        WHERE id = $5::uuid
        RETURNING id, version
        """,
        config.name,
        config.description,
        json.dumps(config.model_dump()),
        new_version,
        pipeline_id,
    )

    return {
        "pipeline_id": str(row["id"]),
        "version": row["version"],
    }


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    db = db_pool.get_pool()

    row = await db.fetchrow(
        """
        UPDATE pipelines
        SET status = 'archived'
        WHERE id = $1::uuid
        RETURNING id, status
        """,
        pipeline_id,
    )

    if row is None:
        raise HTTPException(404, "Pipeline not found")

    return {
        "pipeline_id": str(row["id"]),
        "status": row["status"],
    }


@router.get("/{pipeline_id}/runs")
async def pipeline_runs(
    pipeline_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = db_pool.get_pool()
    offset = (page - 1) * page_size

    rows = await db.fetch(
        """
        SELECT
            pr.id,
            pr.pipeline_version,
            pr.query,
            pr.generation,
            pr.latency_ms,
            pr.input_tokens,
            pr.output_tokens,
            pr.model_used,
            pr.status,
            pr.created_at,
            e.overall_score
        FROM pipeline_runs pr
        LEFT JOIN evaluations e
            ON e.run_id = pr.id
        WHERE pr.pipeline_id = $1::uuid
        ORDER BY pr.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        pipeline_id,
        page_size,
        offset,
    )

    return {
        "page": page,
        "page_size": page_size,
        "runs": [
            {
                "run_id": str(row["id"]),
                "pipeline_version": row["pipeline_version"],
                "query": row["query"],
                "generation": row["generation"],
                "latency_ms": row["latency_ms"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "model_used": row["model_used"],
                "status": row["status"],
                "created_at": row["created_at"],
                "eval_score": (
                    float(row["overall_score"])
                    if row["overall_score"] is not None
                    else None
                ),
            }
            for row in rows
        ],
    }


@router.get("/{pipeline_id}/analytics")
async def pipeline_analytics(pipeline_id: str):
    db = db_pool.get_pool()

    rows = await db.fetch(
        """
        SELECT
            pr.latency_ms,
            e.faithfulness,
            e.answer_relevance,
            e.context_precision,
            e.context_recall,
            e.overall_score,
            pr.input_tokens,
            pr.output_tokens,
            pr.created_at
        FROM pipeline_runs pr
        LEFT JOIN evaluations e
            ON e.run_id = pr.id
        WHERE pr.pipeline_id = $1::uuid
        ORDER BY pr.created_at DESC
        """,
        pipeline_id,
    )

    latencies = [
        float(row["latency_ms"])
        for row in rows
        if row["latency_ms"] is not None
    ]

    def percentile(values, percentile):
        if not values:
            return 0.0
        values = sorted(values)
        index = (len(values) - 1) * percentile
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        fraction = index - lower
        return (
            values[lower]
            + (values[upper] - values[lower]) * fraction
        )

    def average(field):
        values = [
            float(row[field])
            for row in rows
            if row[field] is not None
        ]
        return sum(values) / len(values) if values else 0.0

    return {
        "run_count": len(rows),
        "retrieval_latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "average_generation_latency_ms": average("latency_ms"),
        "average_evaluation_scores": {
            "faithfulness": average("faithfulness"),
            "answer_relevance": average("answer_relevance"),
            "context_precision": average("context_precision"),
            "context_recall": average("context_recall"),
            "overall": average("overall_score"),
        },
        "queries_per_day": {},
    }

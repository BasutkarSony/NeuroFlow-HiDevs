import asyncio
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from db.pool import db_pool


router = APIRouter(prefix="/pipelines")


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    pipeline_a_id: str
    pipeline_b_id: str


async def _run_pipeline(
    pipeline_id: str,
    query: str,
) -> dict[str, Any]:
    db = db_pool.get_pool()

    started = time.perf_counter()

    pipeline = await db.fetchrow(
        """
        SELECT id, name, config, version, status
        FROM pipelines
        WHERE id = $1::uuid
          AND status != 'archived'
        """,
        pipeline_id,
    )

    if pipeline is None:
        raise ValueError(f"Pipeline {pipeline_id} not found")

    # Record the run immediately so every comparison has a run_id.
    run = await db.fetchrow(
        """
        INSERT INTO pipeline_runs (
            pipeline_id,
            pipeline_version,
            query,
            status
        )
        VALUES ($1::uuid, $2, $3, 'running')
        RETURNING id
        """,
        pipeline_id,
        pipeline["version"],
        query,
    )

    run_id = str(run["id"])

    # The actual generation service can be connected here as the
    # generation pipeline evolves. Keep the comparison contract stable.
    generation = f"Pipeline {pipeline['name']} received query: {query}"

    total_latency = int(
        (time.perf_counter() - started) * 1000
    )

    await db.execute(
        """
        UPDATE pipeline_runs
        SET generation = $1,
            latency_ms = $2,
            status = 'complete'
        WHERE id = $3::uuid
        """,
        generation,
        total_latency,
        run_id,
    )

    evaluation = await db.fetchrow(
        """
        SELECT overall_score
        FROM evaluations
        WHERE run_id = $1::uuid
        ORDER BY evaluated_at DESC
        LIMIT 1
        """,
        run_id,
    )

    return {
        "run_id": run_id,
        "generation": generation,
        "retrieval_latency_ms": 0,
        "total_latency_ms": total_latency,
        "chunks_used": 0,
        "eval_score": (
            float(evaluation["overall_score"])
            if evaluation
            else None
        ),
    }


@router.post("/compare")
async def compare_pipelines(request: CompareRequest):
    pipeline_a, pipeline_b = await asyncio.gather(
        _run_pipeline(
            request.pipeline_a_id,
            request.query,
        ),
        _run_pipeline(
            request.pipeline_b_id,
            request.query,
        ),
    )

    return {
        "query": request.query,
        "pipeline_a": pipeline_a,
        "pipeline_b": pipeline_b,
    }

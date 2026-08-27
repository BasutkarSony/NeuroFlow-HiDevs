from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.pool import db_pool


router = APIRouter()


class RatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


@router.patch("/runs/{run_id}/rating")
async def rate_run(run_id: str, request: RatingRequest):
    db = db_pool.get_pool()

    row = await db.fetchrow(
        """
        UPDATE evaluations
        SET
            user_rating = $1,
            metadata = CASE
                WHEN ABS(
                    overall_score - ($1::float / 5.0)
                ) > 0.3
                THEN COALESCE(metadata, '{}'::jsonb)
                     || '{"calibration_needed": true}'::jsonb
                ELSE COALESCE(metadata, '{}'::jsonb)
            END
        WHERE run_id = $2::uuid
        RETURNING
            run_id,
            user_rating,
            overall_score,
            metadata
        """,
        request.rating,
        run_id,
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Evaluation not found.",
        )

    return {
        "run_id": str(row["run_id"]),
        "user_rating": row["user_rating"],
        "overall_score": float(row["overall_score"]),
        "metadata": row["metadata"],
    }

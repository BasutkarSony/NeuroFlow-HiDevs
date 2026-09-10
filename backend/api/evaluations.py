import asyncio
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

@router.get("/evaluations/stream")
async def evaluation_stream():
    async def events():
        if redis is None:
            yield {"event": "error", "data": json.dumps({"message": "Redis client unavailable"})}
            return

        client = redis.from_url("redis://localhost:6379", decode_responses=True)
        pubsub = client.pubsub()

        try:
            await pubsub.subscribe("evaluations:new")
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    yield {"event": "evaluation", "data": message["data"]}
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe("evaluations:new")
            await pubsub.close()
            await client.close()

    return EventSourceResponse(events(), ping=15)


@router.get("/evaluations/{run_id}")
async def get_evaluation(run_id: str):
    from db.pool import db_pool
    from fastapi import HTTPException
    db = db_pool.get_pool()
    row = await db.fetchrow("""
        SELECT id, run_id, faithfulness, answer_relevance,
               context_precision, context_recall, overall_score,
               judge_model, user_rating, evaluated_at
        FROM evaluations
        WHERE run_id = $1::uuid
        ORDER BY evaluated_at DESC
        LIMIT 1
    """, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return dict(row)

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

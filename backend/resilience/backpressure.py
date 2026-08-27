class Backpressure:
    def __init__(self, redis, queue_key="queue:ingest"):
        self.redis = redis
        self.queue_key = queue_key

    async def check(self):
        depth = await self.redis.llen(self.queue_key)

        if depth > 100:
            return {
                "allowed": False,
                "status_code": 503,
                "error": "ingestion_queue_full",
                "queue_depth": depth,
                "retry_after": 30,
            }

        if depth > 50:
            return {
                "allowed": True,
                "status_code": 202,
                "queue_depth": depth,
                "warning": "high_queue_depth",
                "estimated_wait_minutes": max(1, depth // 10),
            }

        return {
            "allowed": True,
            "status_code": 200,
            "queue_depth": depth,
        }

import asyncio


class TimeoutManager:
    timeouts = {
        "embedding": 10,
        "chat_completion": 60,
        "reranking": 15,
        "evaluation": 120,
        "file_extraction": 30,
        "url_fetch": 15,
    }

    def __init__(self, redis=None):
        self.redis = redis

    async def run(self, coro, task_type):
        if task_type not in self.timeouts:
            raise ValueError(f"Unknown task type: {task_type}")

        try:
            return await asyncio.wait_for(
                coro,
                timeout=self.timeouts[task_type],
            )
        except asyncio.TimeoutError as exc:
            if self.redis is not None:
                await self.redis.incr(
                    f"timeouts:{task_type}"
                )

            raise TimeoutError(
                f"{task_type} timed out"
            ) from exc

import asyncio
import time


class RateLimitExceeded(Exception):
    pass


class TokenBucketRateLimiter:
    def __init__(self, redis, key, capacity, refill_rate):
        self.redis = redis
        self.key = key
        self.capacity = capacity
        self.refill_rate = refill_rate

    async def acquire(self, tokens=1):
        while True:
            now = time.time()
            data = await self.redis.hgetall(self.key)

            if data:
                current = float(data.get("tokens", self.capacity))
                last = float(data.get("timestamp", now))
            else:
                current = float(self.capacity)
                last = now

            current = min(
                self.capacity,
                current + (now - last) * self.refill_rate,
            )

            if current >= tokens:
                await self.redis.hset(
                    self.key,
                    mapping={
                        "tokens": current - tokens,
                        "timestamp": now,
                    },
                )
                return

            await asyncio.sleep(
                (tokens - current) / self.refill_rate
            )


async def check_rate_limit(redis, key, limit, window_seconds):
    window = int(time.time()) // window_seconds
    redis_key = f"rate:{key}:{window}"

    count = await redis.incr(redis_key)

    if count == 1:
        await redis.expire(redis_key, window_seconds)

    return count <= limit



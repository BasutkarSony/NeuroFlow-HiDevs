import time
from contextlib import asynccontextmanager


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        redis_client,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.redis = redis_client
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

    @property
    def prefix(self):
        return f"circuit:{self.name}"

    async def _state(self):
        state = await self.redis.get(f"{self.prefix}:state")
        if not state:
            return "closed"
        return state.decode() if isinstance(state, bytes) else state

    async def _failure_count(self):
        value = await self.redis.get(f"{self.prefix}:failure_count")
        return int(value or 0)

    async def allow(self):
        state = await self._state()

        if state == "closed":
            return True

        if state == "open":
            opened_at = await self.redis.get(
                f"{self.prefix}:opened_at"
            )

            if opened_at and (
                time.time() - float(opened_at)
                >= self.recovery_timeout
            ):
                await self.redis.set(
                    f"{self.prefix}:state",
                    "half_open",
                )
                await self.redis.set(
                    f"{self.prefix}:half_open_calls",
                    0,
                )
                state = "half_open"
            else:
                return False

        if state == "half_open":
            calls = await self.redis.incr(
                f"{self.prefix}:half_open_calls"
            )

            if calls > self.half_open_max_calls:
                await self.redis.decr(
                    f"{self.prefix}:half_open_calls"
                )
                return False

        return True

    async def record_success(self):
        await self.redis.set(
            f"{self.prefix}:state",
            "closed",
        )
        await self.redis.set(
            f"{self.prefix}:failure_count",
            0,
        )
        await self.redis.delete(
            f"{self.prefix}:opened_at",
            f"{self.prefix}:half_open_calls",
        )

    async def record_failure(self):
        failures = await self.redis.incr(
            f"{self.prefix}:failure_count"
        )

        if failures >= self.failure_threshold:
            await self.redis.set(
                f"{self.prefix}:state",
                "open",
            )
            await self.redis.set(
                f"{self.prefix}:opened_at",
                time.time(),
            )

    @asynccontextmanager
    async def __call__(self):
        if not await self.allow():
            raise CircuitOpenError(
                f"Circuit '{self.name}' is open"
            )

        try:
            yield
        except Exception:
            await self.record_failure()
            raise
        else:
            await self.record_success()


def circuit_breaker(
    name: str,
    redis_client,
    **kwargs,
):
    return CircuitBreaker(
        name,
        redis_client,
        **kwargs,
    )()

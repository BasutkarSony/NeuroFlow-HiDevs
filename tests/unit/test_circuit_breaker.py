import pytest

from backend.resilience.circuit_breaker import CircuitBreaker


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value

    async def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)

    async def incr(self, key):
        self.data[key] = int(self.data.get(key, 0)) + 1
        return self.data[key]

    async def decr(self, key):
        self.data[key] = int(self.data.get(key, 0)) - 1
        return self.data[key]


@pytest.mark.asyncio
async def test_initial_state_is_closed():
    cb = CircuitBreaker("test", FakeRedis())
    assert await cb._state() == "closed"


@pytest.mark.asyncio
async def test_closed_circuit_allows_calls():
    cb = CircuitBreaker("test", FakeRedis())
    assert await cb.allow() is True


@pytest.mark.asyncio
async def test_failure_increments_counter():
    cb = CircuitBreaker("test", FakeRedis(), failure_threshold=3)
    await cb.record_failure()
    assert await cb._failure_count() == 1


@pytest.mark.asyncio
async def test_threshold_opens_circuit():
    cb = CircuitBreaker("test", FakeRedis(), failure_threshold=2)
    await cb.record_failure()
    await cb.record_failure()
    assert await cb._state() == "open"


@pytest.mark.asyncio
async def test_open_circuit_blocks_calls():
    cb = CircuitBreaker("test", FakeRedis(), failure_threshold=1)
    await cb.record_failure()
    assert await cb.allow() is False

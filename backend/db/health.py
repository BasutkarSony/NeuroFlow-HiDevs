import asyncio
from urllib.parse import urlparse

import asyncpg
import redis.asyncio as redis

from config import get_settings


async def check_postgres(pool: asyncpg.Pool) -> bool:
    """Verify PostgreSQL connectivity."""
    try:
        async with pool.acquire() as connection:
            await connection.execute("SELECT 1")
        return True
    except Exception:
        return False


async def check_redis() -> bool:
    """Verify Redis connectivity."""
    try:
        settings = get_settings()
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

        result = await client.ping()
        await client.aclose()

        return bool(result)
    except Exception:
        return False


async def check_mlflow() -> bool:
    """Verify MLflow server connectivity."""
    try:
        settings = get_settings()

        parsed = urlparse(settings.mlflow_url)
        host = parsed.hostname or settings.mlflow_host
        port = parsed.port or settings.mlflow_port

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=3,
        )

        writer.close()
        await writer.wait_closed()

        return True
    except Exception:
        return False


async def check_all(
    pool: asyncpg.Pool,
) -> dict[str, bool]:
    """Run all infrastructure health checks concurrently."""
    postgres, redis_status, mlflow = await asyncio.gather(
        check_postgres(pool),
        check_redis(),
        check_mlflow(),
    )

    return {
        "postgres": postgres,
        "redis": redis_status,
        "mlflow": mlflow,
    }
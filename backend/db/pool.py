import asyncpg

from config import get_settings


class DatabasePool:
    """Manages the PostgreSQL async connection pool."""

    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def create(self) -> asyncpg.Pool:
        """Create the connection pool once during application startup."""
        if self.pool is None:
            settings = get_settings()

            self.pool = await asyncpg.create_pool(
                dsn=settings.postgres_dsn,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )

        return self.pool

    async def close(self) -> None:
        """Close the connection pool during application shutdown."""
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def get_pool(self) -> asyncpg.Pool:
        """Return the initialized connection pool."""
        if self.pool is None:
            raise RuntimeError("Database pool has not been initialized.")

        return self.pool


db_pool = DatabasePool()
from pathlib import Path

import asyncpg


SCHEMA_FILE = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "init"
    / "001_schema.sql"
)


async def schema_exists(pool: asyncpg.Pool) -> bool:
    """Check whether the core NeuroFlow schema has already been applied."""
    async with pool.acquire() as connection:
        result = await connection.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'documents'
            )
            """
        )

    return bool(result)


async def apply_schema(pool: asyncpg.Pool) -> None:
    """Apply the initial database schema when it is not already present."""
    if await schema_exists(pool):
        return

    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_FILE}"
        )

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(schema_sql)


async def ensure_schema(pool: asyncpg.Pool) -> None:
    """Ensure the NeuroFlow database schema is available."""
    await apply_schema(pool)
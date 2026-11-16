from pathlib import Path

import asyncpg


def _find_project_root() -> Path:
    """Find the repository root in both source and container layouts."""
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "infra" / "init" / "001_schema.sql").is_file():
            return parent
    raise FileNotFoundError(
        "Could not locate infra/init/001_schema.sql relative to "
        f"{current_file}"
    )


ROOT = _find_project_root()
SCHEMA_FILE = ROOT / "infra" / "init" / "001_schema.sql"
MIGRATIONS_DIR = ROOT / "infra" / "migrations"
MIGRATION_LOCK_ID = 726_104_202
REQUIRED_TABLES = {
    "documents",
    "chunks",
    "pipelines",
    "pipeline_runs",
    "evaluations",
    "training_pairs",
    "finetune_jobs",
}


async def _schema_exists(connection: asyncpg.Connection) -> bool:
    existing_tables = await connection.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY($1::text[])
        """,
        list(REQUIRED_TABLES),
    )
    existing = {row["table_name"] for row in existing_tables}
    if not existing:
        return False

    missing = REQUIRED_TABLES - existing
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise RuntimeError(
            "Incomplete NeuroFlow database schema; missing tables: "
            f"{missing_list}. Restore the missing tables before migrating."
        )
    return True


async def _apply_initial_schema(connection: asyncpg.Connection) -> None:
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    async with connection.transaction():
        await connection.execute(schema_sql)


async def _apply_migrations(connection: asyncpg.Connection) -> None:
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # The original schema was applied by Docker's init script or the
    # previous ensure_schema implementation. Record it as migration 1.
    await connection.execute(
        """
        INSERT INTO schema_migrations (version, filename)
        VALUES (1, '001_initial_schema.sql')
        ON CONFLICT (version) DO NOTHING
        """
    )

    if not MIGRATIONS_DIR.exists():
        return

    migration_files = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    for migration_file in migration_files:
        version = int(migration_file.name.split("_", 1)[0])
        already_applied = await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = $1)",
            version,
        )
        if already_applied:
            continue

        migration_sql = migration_file.read_text(encoding="utf-8")
        async with connection.transaction():
            await connection.execute(migration_sql)
            await connection.execute(
                """
                INSERT INTO schema_migrations (version, filename)
                VALUES ($1, $2)
                """,
                version,
                migration_file.name,
            )


async def ensure_schema(pool: asyncpg.Pool) -> None:
    """Create the initial schema and apply pending migrations exactly once."""
    async with pool.acquire() as connection:
        await connection.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_ID)
        try:
            if not await _schema_exists(connection):
                await _apply_initial_schema(connection)

            await _apply_migrations(connection)
        finally:
            await connection.execute(
                "SELECT pg_advisory_unlock($1)",
                MIGRATION_LOCK_ID,
            )

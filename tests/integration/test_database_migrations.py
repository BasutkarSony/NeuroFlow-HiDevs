import os
import asyncpg
import pytest

from backend.db.migrations import ensure_schema


@pytest.mark.asyncio
async def test_fresh_schema_and_existing_schema_upgrade():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    assert pool is not None

    try:
        # This test uses a dedicated disposable CI database.
        async with pool.acquire() as connection:
            await connection.execute("DROP SCHEMA public CASCADE")
            await connection.execute("CREATE SCHEMA public")

        # Fresh database: create all tables and apply the latest migration.
        await ensure_schema(pool)

        async with pool.acquire() as connection:
            fresh_columns = await connection.fetch(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
            fresh = {(row["table_name"], row["column_name"]) for row in fresh_columns}
            assert ("pipelines", "description") in fresh
            assert ("pipelines", "version") in fresh
            assert ("pipelines", "status") in fresh
            assert ("pipeline_runs", "pipeline_version") in fresh
            assert ("pipeline_runs", "metadata") in fresh
            assert ("evaluations", "metadata") in fresh

            # Recreate the old schema shape to exercise migration 002.
            await connection.execute(
                """
                ALTER TABLE pipelines
                    DROP COLUMN description,
                    DROP COLUMN version,
                    DROP COLUMN status;
                ALTER TABLE pipeline_runs
                    DROP COLUMN pipeline_version,
                    DROP COLUMN metadata;
                ALTER TABLE pipeline_runs
                    ALTER COLUMN pipeline_id SET NOT NULL;
                ALTER TABLE evaluations DROP COLUMN metadata;
                DELETE FROM schema_migrations WHERE version = 2;
                """
            )

        # Existing database: the pending migration must restore the API columns.
        await ensure_schema(pool)

        async with pool.acquire() as connection:
            upgraded_columns = await connection.fetch(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
            upgraded = {
                (row["table_name"], row["column_name"])
                for row in upgraded_columns
            }
            assert ("pipelines", "description") in upgraded
            assert ("pipelines", "version") in upgraded
            assert ("pipelines", "status") in upgraded
            assert ("pipeline_runs", "pipeline_version") in upgraded
            assert ("pipeline_runs", "metadata") in upgraded
            assert ("evaluations", "metadata") in upgraded

            pipeline_id_nullable = await connection.fetchval(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'pipeline_runs'
                  AND column_name = 'pipeline_id'
                """
            )
            assert pipeline_id_nullable == "YES"

            applied_version = await connection.fetchval(
                "SELECT version FROM schema_migrations WHERE version = 2"
            )
            assert applied_version == 2
    finally:
        await pool.close()

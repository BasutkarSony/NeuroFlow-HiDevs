-- Reconcile the initial schema with the columns used by the API and pipelines.
-- Safe to run against databases created from the original 001_schema.sql.

ALTER TABLE pipelines
    ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active';

ALTER TABLE pipeline_runs
    ALTER COLUMN pipeline_id DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS pipeline_version INTEGER,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

ALTER TABLE evaluations
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS pipeline_runs_pipeline_created_idx
    ON pipeline_runs (pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS evaluations_run_evaluated_idx
    ON evaluations (run_id, evaluated_at DESC);

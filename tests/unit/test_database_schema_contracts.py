from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INITIAL_SCHEMA = (ROOT / "infra" / "init" / "001_schema.sql").read_text(
    encoding="utf-8"
)
UPGRADE_SCHEMA = (
    ROOT / "infra" / "migrations" / "002_align_api_schema.sql"
).read_text(encoding="utf-8")


def test_fresh_schema_contains_pipeline_api_columns():
    pipelines = INITIAL_SCHEMA.split("CREATE TABLE pipelines", 1)[1].split(");", 1)[0]
    assert "description TEXT" in pipelines
    assert "version INTEGER" in pipelines
    assert "status VARCHAR" in pipelines


def test_fresh_schema_supports_unassigned_runs_and_run_metadata():
    runs = INITIAL_SCHEMA.split("CREATE TABLE pipeline_runs", 1)[1].split(");", 1)[0]
    assert "pipeline_id UUID REFERENCES pipelines(id)" in runs
    assert "pipeline_version INTEGER" in runs
    assert "metadata JSONB" in runs


def test_fresh_schema_contains_evaluation_metadata():
    evaluations = INITIAL_SCHEMA.split("CREATE TABLE evaluations", 1)[1].split(");", 1)[0]
    assert "metadata JSONB" in evaluations


def test_upgrade_migration_reconciles_existing_databases():
    assert "ADD COLUMN IF NOT EXISTS description" in UPGRADE_SCHEMA
    assert "ADD COLUMN IF NOT EXISTS version" in UPGRADE_SCHEMA
    assert "ADD COLUMN IF NOT EXISTS status" in UPGRADE_SCHEMA
    assert "ALTER COLUMN pipeline_id DROP NOT NULL" in UPGRADE_SCHEMA
    assert "ADD COLUMN IF NOT EXISTS pipeline_version" in UPGRADE_SCHEMA
    assert "ADD COLUMN IF NOT EXISTS metadata" in UPGRADE_SCHEMA

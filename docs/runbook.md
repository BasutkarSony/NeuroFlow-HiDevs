# NeuroFlow Operations Runbook

## 1. High query latency — P95 >10s
- [ ] Inspect Jaeger traces.
- [ ] Check Redis memory and hit rate.
- [ ] Inspect PostgreSQL `pg_stat_statements`
- [ ] Flush stale cache if required.
- [ ] Add missing indexes.
- [ ] Scale replicas if capacity is the bottleneck.

## 2. Evaluation degradation
- [ ] Identify affected pipeline and metric.
- [ ] Check recently ingested documents.
- [ ] Review MLflow fine-tuning runs.
- [ ] Revert the model if degradation is confirmed.
- [ ] Inspect training data quality.

## 3. Circuit breaker open
- [ ] GET `/health`
- [ ] Check provider status.
- [ ] Wait for recovery if the provider is transiently unavailable.
- [ ] POST `/admin/circuit-breaker/reset` when manual recovery is required.

## 4. Ingestion queue >100
- [ ] GET `/health`
- [ ] Inspect worker logs.
- [ ] Restart workers if required.
- [ ] Check Redis for stuck jobs.

## 5. Database disk >80%
- [ ] Identify the fastest-growing table.
- [ ] Clean up eligible historical data.
- [ ] Run the configured retention process.

## Data retention
The retention scheduler runs daily. It deletes completed pipeline runs older than 90 days with no evaluations, evaluations older than 180 days, and chunks belonging to archived documents. Retention counts are logged with structlog.

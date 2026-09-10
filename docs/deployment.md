# NeuroFlow Cloud Deployment

## Deployment Target
Railway.

## Environment Management
Configure all variables documented in `.env.example` as Railway service variables. Never commit real secrets.

## Deployment Steps
1. Create a Railway project.
2. Add PostgreSQL and configure POSTGRES_URL.
3. Add Redis and configure REDIS_URL.
4. Deploy the API using backend/Dockerfile.
5. Configure production environment variables.
6. Deploy the worker.
7. Deploy MLflow with PostgreSQL as its backend.

## Production Verification
1. GET /health — Pending
2. POST /ingest using tests/fixtures/test_doc.pdf — Pending
3. Query the test document — Pending
4. GET /evaluations — Pending
5. GET /query/{run_id}/stream — Pending
6. MLflow dashboard — Pending
7. GET /metrics — Pending
8. Locust 10 users for 2 minutes — Pending

## Load Test
locust -f tests/performance/locustfile.py -H https://YOUR_APP_URL --headless -u 10 -r 2 --run-time 2m

## Rollback
1. Redeploy the previous working Docker image tag.
2. Reverse database migrations if required.
3. Verify health and the complete pipeline.

## Production URL
Pending deployment.

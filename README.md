# NeuroFlow

NeuroFlow is a production-grade multi-modal LLM orchestration platform designed for Retrieval-Augmented Generation (RAG), automated evaluation, fine-tuning workflows, model routing, and real-time observability.

## What is NeuroFlow

NeuroFlow provides an end-to-end architecture for building reliable LLM applications that can ingest information from multiple modalities, retrieve relevant context, generate grounded responses, evaluate generation quality, and continuously improve model performance.

## Key Features

- Multi-modal document ingestion
- Text extraction and intelligent chunking
- Vector and keyword-based hybrid retrieval
- Reciprocal Rank Fusion (RRF)
- Cross-encoder reranking
- RAG-based generation
- Multi-model LLM routing
- Server-Sent Events (SSE) streaming
- Citation and provenance tracking
- Automated LLM-as-Judge evaluation
- RAGAS-based quality metrics
- Named, config-driven RAG pipelines
- Fine-tuning data extraction and model tracking
- MLflow experiment tracking
- Production resilience and observability
- Secure API and prompt-injection defenses

## Tech Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- pgvector
- Redis

### AI and RAG

- LLM provider abstraction
- Embedding models
- Hybrid search
- Reciprocal Rank Fusion
- Cross-encoder reranking
- RAGAS evaluation
- LLM-as-Judge evaluation
- Fine-tuning pipelines

### Frontend

- Next.js
- React
- TypeScript

### MLOps and Observability

- MLflow
- OpenTelemetry
- Prometheus
- Structured logging

### Infrastructure

- Docker
- Docker Compose
- GitHub Actions
- Railway / Render

## Architecture

NeuroFlow is organized into five primary AI subsystems:

1. **Ingestion** — processes documents and multimodal inputs into queryable vector representations.
2. **Retrieval** — combines vector search, keyword search, metadata filtering, RRF fusion, and reranking.
3. **Generation** — assembles grounded prompts, routes requests to appropriate LLMs, and streams responses.
4. **Evaluation** — asynchronously measures generation and retrieval quality.
5. **Fine-Tuning** — extracts high-quality examples, manages training jobs, tracks experiments, and evaluates improved models.

Detailed architecture and data flows are documented in [`docs/architecture.md`](docs/architecture.md).

## API

The implemented REST API contracts are documented in [`docs/api-contracts.md`](docs/api-contracts.md).

## Architecture Decision Records

Key architectural decisions are documented as ADRs:

- [`ADR 001 — Vector Store`](docs/adr/001-vector-store.md)
- [`ADR 002 — Chunking Strategy`](docs/adr/002-chunking-strategy.md)
- [`ADR 003 — Evaluation Framework`](docs/adr/003-evaluation-framework.md)
- [`ADR 004 — Model Routing`](docs/adr/004-model-routing.md)

## Project Structure

```text
NeuroFlow-HiDevs/
├── backend/
├── frontend/
├── pipelines/
├── evaluation/
├── infra/
├── docs/
│   ├── architecture.md
│   ├── api-contracts.md
│   ├── data-models.md
│   └── adr/
├── .gitignore
└── README.md
```
## Production Deployment

The production stack uses Nginx for TLS termination with a self-signed certificate for development/testing. For production, replace `infra/nginx/certs/server.crt` and `infra/nginx/certs/server.key` with certificates issued by Let's Encrypt (for example, using Certbot), while keeping the same certificate paths configured in Nginx.


## Quality Metrics

Final evaluation status is recorded in `evaluation/quality_final.json`. The repository currently reports the metrics as not measurable because the required retrieval ground-truth dataset with `relevant_chunk_ids` is absent. No metric values are fabricated.

| Metric | Final Value | Target |
|---|---:|---:|
| Retrieval Hit Rate @10 | Not measurable | >0.80 |
| Retrieval MRR @10 | Not measurable | >0.60 |
| Faithfulness | Not measurable | >0.78 |
| Answer Relevance | Not measurable | >0.75 |
| Context Precision | Not measurable | >0.72 |
| Overall Evaluation Score | Not measurable | >0.75 |
| P95 Query Latency | Not measurable | <4000 ms |

Implemented improvements: configurable candidate depth, reranker candidate depth, weighted Reciprocal Rank Fusion, query expansion, and pipeline configuration consumed by the query API.

## Quick Start

```bash
git clone https://github.com/BasutkarSony/NeuroFlow-HiDevs.git
cd NeuroFlow-HiDevs
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

Set `POSTGRES_PASSWORD` and `REDIS_PASSWORD` in `.env`. Configure an LLM provider key when embedding or image extraction is required, and replace development authentication secrets before production use. Redis uses append-only persistence (`appendfsync everysec`) on the `redis_data` volume and `noeviction` so memory pressure cannot silently evict queued jobs; if Redis reaches its memory limit, new writes fail and the API reports queue submission failure instead. The Redis, API, and worker Compose services use `restart: unless-stopped` so they recover after process/container exits. The ARQ worker retries transient ingestion exceptions up to five attempts with short exponential backoff; invalid input and missing source files fail immediately. A process killed mid-job relies on ARQ's in-progress lease expiry before the job can be picked up again.

## API Reference

The implemented FastAPI endpoints are listed below. Protected endpoints require Bearer authentication.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/token` | No | Issue an access token |
| GET | `/health` | No | Service health |
| GET | `/metrics` | No | Prometheus metrics |
| GET | `/` | No | Service information |
| POST | `/query` | Yes | Execute a RAG query |
| GET | `/query/{run_id}/stream` | Yes | Stream query output using SSE |
| GET | `/evaluations/stream` | Yes | Stream evaluation events |
| GET | `/evaluations/{run_id}` | Yes | Retrieve an evaluation |
| PATCH | `/runs/{run_id}/rating` | Yes | Rate a run |
| GET | `/finetune/training-data/preview` | Yes | Preview training data |
| GET | `/finetune/jobs` | Yes | List fine-tuning jobs |
| POST | `/finetune/jobs` | Yes | Create a fine-tuning job |
| GET | `/finetune/jobs/{job_id}` | Yes | Retrieve a fine-tuning job |
| GET | `/pipelines` | Yes | List pipelines |
| POST | `/pipelines` | Yes | Create a pipeline |
| GET | `/pipelines/{pipeline_id}` | Yes | Retrieve a pipeline |
| PATCH | `/pipelines/{pipeline_id}` | Yes | Update a pipeline |
| DELETE | `/pipelines/{pipeline_id}` | Yes | Delete a pipeline |
| GET | `/pipelines/{pipeline_id}/runs` | Yes | List pipeline runs |
| GET | `/pipelines/{pipeline_id}/analytics` | Yes | Pipeline analytics |
| POST | `/pipelines/compare` | Yes | Compare pipelines |
| POST | `/ingest` | Yes | Queue URL ingestion |
| POST | `/ingest/file` | Yes | Queue file ingestion (25 MiB max) |
| GET | `/ingest/{document_id}` | Yes | Retrieve tenant-scoped ingestion status |

Full request and response contracts are documented in `docs/api-contracts.md`.

## SDK Usage

Install the local Python SDK with `pip install ./sdk`.

See sdk/examples/quickstart.py for the complete ingest-to-query streaming example. The SDK supports Bearer authentication, rate-limit retries, SSE streaming, evaluation polling, and pipeline management.

## Configuration

Copy `.env.example` to `.env`.

**Required for Docker Compose:** `POSTGRES_PASSWORD` and `REDIS_PASSWORD`. Configure at least one LLM provider key for embedding and image ingestion. The API settings also support `JWT_SECRET_KEY`; development defaults must be replaced before production. `POSTGRES_URL` and `REDIS_URL` in `.env.example` are not consumed by the current backend settings.

**Optional:** `MLFLOW_TRACKING_URI`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN`, `ENVIRONMENT`, and `LOG_LEVEL`.

Never commit `.env` or provider credentials.

## Known Limitations

- Retrieval and generation quality metrics cannot currently be measured because the required retrieval ground-truth dataset is absent.
- The ingestion-status endpoint is available at `GET /ingest/{document_id}`; SDK polling support is not currently documented or verified.
- Non-image documents can be processed without an embedding provider, but they will have no vector embeddings. Image ingestion requires a configured OpenAI provider.
- Uploaded source files are retained in the shared ingestion volume; an automated retention policy is not yet defined.
- Production TLS expects certificate files at the configured Nginx paths; trusted production certificates must replace development/testing certificates.
- Fine-tuning depends on configured model/runtime infrastructure and available training data.
- No live deployment URL is currently configured in the repository.

## What to Build Next

1. Add and version a representative retrieval ground-truth dataset.
2. Run the complete evaluation sprint and populate `evaluation/quality_final.json` with measured values.
3. Add SDK polling support for the ingestion-status API.
4. Expand integration and production deployment tests.
5. Replace development TLS certificates with managed production certificates.

## Operations

Operational troubleshooting procedures are documented in `docs/runbook.md`.

## Architecture Diagram

NeuroFlow architecture: see `docs/image.png`.

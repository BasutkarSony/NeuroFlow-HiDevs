# NeuroFlow

NeuroFlow is a production-grade multi-modal LLM orchestration platform designed for Retrieval-Augmented Generation (RAG), automated evaluation, fine-tuning workflows, model routing, and real-time observability.

## Project Overview

NeuroFlow provides an end-to-end architecture for building reliable LLM applications that can ingest information from multiple modalities, retrieve relevant context, generate grounded responses, evaluate generation quality, and continuously improve model performance.

## Core Capabilities

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

## Planned Technology Stack

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

The planned REST API contracts are documented in [`docs/api-contracts.md`](docs/api-contracts.md).

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
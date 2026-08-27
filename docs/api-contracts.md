# NeuroFlow API Contracts

## 1. API Conventions

NeuroFlow exposes a REST API through FastAPI.

### Base Path

```text
/api/v1
```

### Authentication

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

The `/health` endpoint does not require authentication.

### Common Error Response

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "request_id": "req_123456"
  }
}
```

### Common HTTP Status Codes

| Status | Meaning                                      |
| ------ | -------------------------------------------- |
| 200    | Request completed successfully               |
| 201    | Resource created successfully                |
| 202    | Request accepted for asynchronous processing |
| 400    | Invalid request                              |
| 401    | Authentication required or invalid           |
| 403    | Insufficient permissions                     |
| 404    | Resource not found                           |
| 409    | Resource conflict                            |
| 413    | Payload too large                            |
| 422    | Request validation failed                    |
| 429    | Rate limit exceeded                          |
| 500    | Internal server error                        |
| 503    | Service unavailable                          |

---

# 2. POST /ingest

## Purpose

Accepts a file or web URL and starts asynchronous ingestion.

Supported sources:

* PDF
* DOCX
* Images
* CSV
* Web URLs

## Authentication

Required.

## Rate Limit

```text
30 requests/minute/user
```

## Request

File ingestion uses `multipart/form-data`.

URL ingestion uses JSON.

### URL Request Schema

```json
{
  "source_type": "url",
  "source_url": "https://example.com/document",
  "filename": null,
  "pipeline_id": "default-rag",
  "metadata": {
    "department": "hr",
    "document_type": "policy"
  }
}
```

### Request Fields

| Field         | Type   | Required    | Description            |
| ------------- | ------ | ----------- | ---------------------- |
| `source_type` | string | Yes         | `file` or `url`        |
| `source_url`  | string | Conditional | URL to ingest          |
| `filename`    | string | Conditional | Uploaded filename      |
| `pipeline_id` | string | No          | Pipeline configuration |
| `metadata`    | object | No          | Source metadata        |

For file ingestion, `source_type`, `filename`, `pipeline_id`, and `metadata` are submitted as multipart fields together with the binary file.

## Response

**HTTP 202 Accepted**

```json
{
  "ingestion_id": "ing_123456",
  "status": "queued",
  "source_type": "file",
  "pipeline_id": "default-rag",
  "created_at": "2026-08-25T10:00:00Z"
}
```

## Errors

| Code                    | HTTP Status | Meaning                        |
| ----------------------- | ----------: | ------------------------------ |
| `INVALID_SOURCE_TYPE`   |         400 | Unsupported source type        |
| `INVALID_URL`           |         400 | Invalid or inaccessible URL    |
| `UNSUPPORTED_FILE_TYPE` |         400 | File format is not supported   |
| `FILE_TOO_LARGE`        |         413 | File exceeds configured size   |
| `PIPELINE_NOT_FOUND`    |         404 | Pipeline does not exist        |
| `DUPLICATE_SOURCE`      |         409 | Source already exists          |
| `INGESTION_FAILED`      |         500 | Ingestion could not be started |

---

# 3. POST /query

## Purpose

Executes a RAG query using the configured retrieval and generation pipeline.

## Authentication

Required.

## Rate Limit

```text
60 requests/minute/user
```

## Request Schema

```json
{
  "query": "What is the refund policy?",
  "pipeline_id": "default-rag",
  "top_k": 10,
  "filters": {
    "document_type": "policy"
  },
  "stream": true
}
```

| Field         | Type    | Required | Description                    |
| ------------- | ------- | -------- | ------------------------------ |
| `query`       | string  | Yes      | User question                  |
| `pipeline_id` | string  | No       | Pipeline to execute            |
| `top_k`       | integer | No       | Number of retrieval candidates |
| `filters`     | object  | No       | Metadata filters               |
| `stream`      | boolean | No       | Enables SSE streaming          |

## Response

**HTTP 202 Accepted**

```json
{
  "query_id": "qry_123456",
  "status": "processing",
  "pipeline_id": "default-rag",
  "stream_url": "/api/v1/query/qry_123456/stream",
  "created_at": "2026-08-25T10:01:00Z"
}
```

## Errors

| Code                      | HTTP Status | Meaning                          |
| ------------------------- | ----------: | -------------------------------- |
| `EMPTY_QUERY`             |         400 | Query is empty                   |
| `QUERY_TOO_LONG`          |         400 | Query exceeds maximum length     |
| `PIPELINE_NOT_FOUND`      |         404 | Pipeline does not exist          |
| `RETRIEVAL_UNAVAILABLE`   |         503 | Retrieval service is unavailable |
| `MODEL_UNAVAILABLE`       |         503 | No suitable LLM is available     |
| `QUERY_VALIDATION_FAILED` |         422 | Request validation failed        |

---

# 4. GET /query/{query_id}/stream

## Purpose

Streams the generated response using Server-Sent Events (SSE).

## Authentication

Required.

## Rate Limit

```text
120 requests/minute/user
```

## Path Parameter

| Parameter  | Type   | Required | Description      |
| ---------- | ------ | -------- | ---------------- |
| `query_id` | string | Yes      | Query identifier |

## Response

**HTTP 200**

Content type:

```http
Content-Type: text/event-stream
```

Example:

```text
event: token
data: {"text":"The"}

event: token
data: {"text":" refund"}

event: token
data: {"text":" policy"}

event: citation
data: {"chunk_id":"chunk_123","document_id":"doc_456"}

event: complete
data: {"query_id":"qry_123456","status":"completed"}
```

## SSE Event Types

| Event      | Description                 |
| ---------- | --------------------------- |
| `token`    | Generated text fragment     |
| `citation` | Source citation information |
| `metadata` | Generation metadata         |
| `complete` | Generation completed        |
| `error`    | Generation error            |

## Errors

| Code                | HTTP Status | Meaning                       |
| ------------------- | ----------: | ----------------------------- |
| `QUERY_NOT_FOUND`   |         404 | Query ID does not exist       |
| `STREAM_EXPIRED`    |         404 | Stream is no longer available |
| `GENERATION_FAILED` |         500 | Generation failed             |
| `MODEL_UNAVAILABLE` |         503 | Selected model is unavailable |

---

# 5. GET /evaluations

## Purpose

Returns paginated evaluation results for completed generations.

## Authentication

Required.

## Rate Limit

```text
60 requests/minute/user
```

## Query Parameters

| Parameter          | Type     | Default | Description                |
| ------------------ | -------- | ------- | -------------------------- |
| `page`             | integer  | 1       | Page number                |
| `page_size`        | integer  | 20      | Number of results          |
| `pipeline_id`      | string   | null    | Filter by pipeline         |
| `from`             | datetime | null    | Start timestamp            |
| `to`               | datetime | null    | End timestamp              |
| `min_faithfulness` | float    | null    | Minimum faithfulness score |

## Response

**HTTP 200 OK**

```json
{
  "items": [
    {
      "evaluation_id": "eval_123",
      "query_id": "qry_123456",
      "generation_id": "gen_123",
      "pipeline_id": "default-rag",
      "faithfulness": 0.92,
      "answer_relevance": 0.88,
      "context_precision": 0.84,
      "context_recall": 0.91,
      "user_rating": 5,
      "evaluator_model": "judge-model",
      "created_at": "2026-08-25T10:05:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 125,
    "pages": 7
  }
}
```

## Errors

| Code                      | HTTP Status | Meaning                       |
| ------------------------- | ----------: | ----------------------------- |
| `INVALID_PAGE`            |         400 | Invalid pagination parameters |
| `INVALID_DATE_RANGE`      |         400 | Invalid date range            |
| `EVALUATION_QUERY_FAILED` |         500 | Evaluation query failed       |

---

# 6. GET /evaluations/aggregate

## Purpose

Returns rolling quality metrics for NeuroFlow.

## Authentication

Required.

## Rate Limit

```text
30 requests/minute/user
```

## Query Parameters

| Parameter     | Type   | Default | Description        |
| ------------- | ------ | ------- | ------------------ |
| `window`      | string | `24h`   | Aggregation window |
| `pipeline_id` | string | null    | Pipeline filter    |

Supported windows:

```text
1h
6h
24h
7d
30d
```

## Response

**HTTP 200 OK**

```json
{
  "window": "24h",
  "pipeline_id": "default-rag",
  "sample_count": 450,
  "metrics": {
    "faithfulness": {
      "mean": 0.91,
      "minimum": 0.62,
      "maximum": 1.0
    },
    "answer_relevance": {
      "mean": 0.89,
      "minimum": 0.58,
      "maximum": 1.0
    },
    "context_precision": {
      "mean": 0.86,
      "minimum": 0.51,
      "maximum": 1.0
    },
    "context_recall": {
      "mean": 0.90,
      "minimum": 0.55,
      "maximum": 1.0
    }
  }
}
```

## Errors

| Code                 | HTTP Status | Meaning                             |
| -------------------- | ----------: | ----------------------------------- |
| `INVALID_WINDOW`     |         400 | Unsupported aggregation window      |
| `AGGREGATION_FAILED` |         500 | Aggregation could not be calculated |

---

# 7. POST /pipelines

## Purpose

Creates a named, configuration-driven RAG pipeline.

## Authentication

Required.

## Rate Limit

```text
30 requests/minute/user
```

## Request Schema

```json
{
  "name": "customer-support-rag",
  "description": "Customer support knowledge pipeline",
  "retrieval": {
    "top_k": 20,
    "vector_weight": 0.5,
    "keyword_weight": 0.5,
    "reranker": "cross-encoder"
  },
  "generation": {
    "model_tier": "balanced",
    "temperature": 0.2,
    "max_tokens": 1000
  },
  "evaluation": {
    "enabled": true
  }
}
```

| Field         | Type   | Required | Description              |
| ------------- | ------ | -------- | ------------------------ |
| `name`        | string | Yes      | Unique pipeline name     |
| `description` | string | No       | Pipeline description     |
| `retrieval`   | object | Yes      | Retrieval configuration  |
| `generation`  | object | Yes      | Generation configuration |
| `evaluation`  | object | No       | Evaluation configuration |

## Response

**HTTP 201 Created**

```json
{
  "id": "pipe_123456",
  "name": "customer-support-rag",
  "version": 1,
  "status": "active",
  "created_at": "2026-08-25T10:10:00Z"
}
```

## Errors

| Code                        | HTTP Status | Meaning                          |
| --------------------------- | ----------: | -------------------------------- |
| `PIPELINE_NAME_EXISTS`      |         409 | Pipeline name already exists     |
| `INVALID_RETRIEVAL_CONFIG`  |         422 | Invalid retrieval configuration  |
| `INVALID_GENERATION_CONFIG` |         422 | Invalid generation configuration |
| `INVALID_EVALUATION_CONFIG` |         422 | Invalid evaluation configuration |

---

# 8. GET /pipelines/{id}/runs

## Purpose

Returns execution history for a named pipeline.

## Authentication

Required.

## Rate Limit

```text
60 requests/minute/user
```

## Path Parameter

| Parameter | Type   | Required | Description         |
| --------- | ------ | -------- | ------------------- |
| `id`      | string | Yes      | Pipeline identifier |

## Query Parameters

| Parameter   | Type    | Default | Description                |
| ----------- | ------- | ------- | -------------------------- |
| `page`      | integer | 1       | Page number                |
| `page_size` | integer | 20      | Results per page           |
| `status`    | string  | null    | Filter by execution status |

## Response

**HTTP 200 OK**

```json
{
  "pipeline_id": "pipe_123456",
  "items": [
    {
      "run_id": "run_123",
      "status": "completed",
      "query_count": 120,
      "average_latency_ms": 850,
      "evaluation_score": 0.90,
      "started_at": "2026-08-25T09:00:00Z",
      "completed_at": "2026-08-25T09:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 120
  }
}
```

## Errors

| Code                 | HTTP Status | Meaning                   |
| -------------------- | ----------: | ------------------------- |
| `PIPELINE_NOT_FOUND` |         404 | Pipeline does not exist   |
| `INVALID_STATUS`     |         400 | Invalid run status filter |

---

# 9. POST /finetune/jobs

## Purpose

Submits an asynchronous fine-tuning job using an approved training dataset.

The dataset is expected to contain high-quality examples selected according to the evaluation criteria defined by the Fine-Tuning Subsystem.

## Authentication

Required.

## Rate Limit

```text
5 requests/hour/user
```

## Request Schema

```json
{
  "base_model": "base-model-v1",
  "dataset_id": "dataset_123",
  "pipeline_id": "customer-support-rag",
  "hyperparameters": {
    "epochs": 3,
    "learning_rate": 0.0001
  }
}
```

| Field             | Type   | Required | Description            |
| ----------------- | ------ | -------- | ---------------------- |
| `base_model`      | string | Yes      | Base model identifier  |
| `dataset_id`      | string | Yes      | Approved JSONL dataset |
| `pipeline_id`     | string | No       | Associated pipeline    |
| `hyperparameters` | object | No       | Training parameters    |

## Response

**HTTP 202 Accepted**

```json
{
  "job_id": "ftjob_123456",
  "status": "queued",
  "base_model": "base-model-v1",
  "dataset_id": "dataset_123",
  "created_at": "2026-08-25T10:15:00Z"
}
```

## Errors

| Code                       | HTTP Status | Meaning                                    |
| -------------------------- | ----------: | ------------------------------------------ |
| `DATASET_NOT_FOUND`        |         404 | Dataset does not exist                     |
| `DATASET_NOT_APPROVED`     |         400 | Dataset does not meet quality requirements |
| `MODEL_NOT_SUPPORTED`      |         400 | Base model does not support fine-tuning    |
| `INVALID_HYPERPARAMETERS`  |         422 | Invalid training configuration             |
| `FINE_TUNE_LIMIT_EXCEEDED` |         429 | Fine-tuning rate limit exceeded            |

---

# 10. GET /finetune/jobs/{id}

## Purpose

Returns fine-tuning job status and evaluation metrics.

## Authentication

Required.

## Rate Limit

```text
60 requests/minute/user
```

## Path Parameter

| Parameter | Type   | Required | Description                |
| --------- | ------ | -------- | -------------------------- |
| `id`      | string | Yes      | Fine-tuning job identifier |

## Response

**HTTP 200 OK**

```json
{
  "job_id": "ftjob_123456",
  "status": "completed",
  "base_model": "base-model-v1",
  "fine_tuned_model": "support-model-v2",
  "mlflow_run_id": "run_789",
  "metrics": {
    "faithfulness": 0.94,
    "answer_relevance": 0.92,
    "context_precision": 0.88,
    "context_recall": 0.91,
    "latency_ms": 720
  },
  "model_comparison": {
    "base_model_score": 0.87,
    "fine_tuned_model_score": 0.91,
    "promoted": true
  },
  "created_at": "2026-08-25T10:15:00Z",
  "completed_at": "2026-08-25T12:15:00Z"
}
```

## Errors

| Code                           | HTTP Status | Meaning                        |
| ------------------------------ | ----------: | ------------------------------ |
| `FINE_TUNE_JOB_NOT_FOUND`      |         404 | Fine-tuning job does not exist |
| `FINE_TUNE_STATUS_UNAVAILABLE` |         503 | Job status cannot be retrieved |

---

# 11. GET /health

## Purpose

Returns the health status of the API and critical dependencies.

## Authentication

Not required.

## Rate Limit

```text
120 requests/minute/IP
```

## Response

**HTTP 200 OK**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "postgres": "healthy",
    "redis": "healthy",
    "mlflow": "healthy"
  },
  "timestamp": "2026-08-25T10:20:00Z"
}
```

If a critical dependency is unavailable:

**HTTP 503 Service Unavailable**

```json
{
  "status": "unhealthy",
  "dependencies": {
    "postgres": "unhealthy",
    "redis": "healthy",
    "mlflow": "healthy"
  }
}
```

## Errors

| Code                | HTTP Status | Meaning                                           |
| ------------------- | ----------: | ------------------------------------------------- |
| `SERVICE_UNHEALTHY` |         503 | One or more critical dependencies are unavailable |

---

# 12. GET /metrics

## Purpose

Exposes operational metrics for monitoring systems such as Prometheus.

## Authentication

Required in production deployments.

## Rate Limit

```text
30 requests/minute
```

## Response

**HTTP 200 OK**

Content type:

```text
text/plain; version=0.0.4
```

Example metrics:

```text
neuroflow_http_requests_total
neuroflow_http_request_duration_seconds
neuroflow_llm_requests_total
neuroflow_llm_latency_seconds
neuroflow_llm_tokens_total
neuroflow_retrieval_latency_seconds
neuroflow_retrieval_results_total
neuroflow_evaluation_score
neuroflow_ingestion_jobs_total
neuroflow_finetune_jobs_total
```

## Errors

| Code                  | HTTP Status | Meaning                          |
| --------------------- | ----------: | -------------------------------- |
| `FORBIDDEN`           |         403 | Metrics access is not authorized |
| `METRICS_UNAVAILABLE` |         503 | Metrics could not be generated   |

---

# 13. Authentication and Authorization

Protected endpoints use bearer-token authentication.

Authentication validates:

* token signature
* token expiration
* issuer
* user identity
* required permissions

Example permissions include:

```text
ingest:write
query:read
evaluation:read
pipeline:write
finetune:write
metrics:read
```

Authorization is enforced at the resource level.

---

# 14. Rate Limiting

Rate limiting is enforced using Redis.

Limits are applied per authenticated user or IP depending on the endpoint.

When a limit is exceeded, the API returns:

**HTTP 429 Too Many Requests**

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "request_id": "req_123456"
  }
}
```

The response may include:

```http
Retry-After: 30
```

---

# 15. Request Tracing

Every request receives an `X-Request-ID`.

The request ID is propagated through:

```text
API
  ↓
Retrieval
  ↓
Generation
  ↓
Evaluation
  ↓
Background Jobs
```

This allows individual requests to be traced across asynchronous components.

---

# 16. API Versioning

The API uses URL-based versioning:

```text
/api/v1
```

Breaking changes require a new API version.

Existing versions remain supported according to the project's compatibility policy.

---

# 17. API Design Principles

NeuroFlow APIs follow these principles:

1. Validate input at the API boundary.
2. Use asynchronous processing for long-running workloads.
3. Return resource IDs for asynchronous operations.
4. Use consistent error response structures.
5. Require authentication for protected resources.
6. Apply rate limits to resource-intensive endpoints.
7. Propagate request IDs for observability.
8. Preserve backward compatibility within an API version.
9. Never expose secrets or sensitive internal configuration.
10. Return explicit status information for background jobs.

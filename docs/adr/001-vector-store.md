# ADR 001: Vector Store Selection

## Context

NeuroFlow requires a vector storage solution for its Retrieval-Augmented Generation (RAG) pipeline.

The vector store must support:

- High-dimensional embeddings
- Similarity search
- Metadata filtering
- Efficient retrieval at scale
- Integration with the existing application database
- Reliable persistence
- Local development
- Production deployment
- Low operational complexity

The main alternatives considered are:

1. PostgreSQL with pgvector
2. Pinecone
3. Weaviate
4. Qdrant

NeuroFlow also requires relational data for documents, chunks, users, pipelines, evaluations, and model metadata. Maintaining separate systems for relational and vector data would increase infrastructure complexity.

## Decision

NeuroFlow will use **PostgreSQL with the pgvector extension** as its primary vector store.

PostgreSQL will store both relational application data and vector embeddings.

The architecture will use pgvector for:

- Vector similarity search
- Embedding storage
- Retrieval candidate generation
- Metadata-aware retrieval

PostgreSQL will also store associated metadata such as:

- document ID
- chunk ID
- source
- modality
- page or section
- content hash
- embedding model
- pipeline ID
- timestamps

This allows vector retrieval and relational filtering to operate within the same database system.

### Comparison

| Criterion | pgvector | Pinecone | Weaviate | Qdrant |
|---|---|---|---|---|
| Vector similarity search | Strong | Strong | Strong | Strong |
| Relational data support | Native | External database required | Limited relational capability | Limited relational capability |
| Metadata filtering | Strong | Strong | Strong | Strong |
| Existing PostgreSQL integration | Excellent | None | None | None |
| Operational complexity | Low | Low-Medium | Medium | Medium |
| Local development | Excellent | Requires external service | Good | Good |
| Transaction support | Native PostgreSQL | External | Limited | Limited |
| Infrastructure footprint | One primary database | Additional service | Additional service | Additional service |
| Cost for project scale | Low | Usage-based | Infrastructure dependent | Infrastructure dependent |

### Why pgvector

The primary reason for selecting pgvector is architectural simplicity.

NeuroFlow already requires PostgreSQL for relational application data. Using pgvector allows embeddings and relational metadata to remain in the same persistence layer.

This provides:

- simpler deployment
- fewer services
- simpler backups
- transactional consistency
- easier local development
- easier testing
- straightforward metadata filtering
- reduced infrastructure overhead

The decision also fits the project's production architecture because PostgreSQL can support both traditional relational workloads and vector retrieval without requiring a separate vector database for the expected project scale.

## Consequences

### Positive Consequences

1. **Simpler architecture**

   PostgreSQL becomes the primary persistent data store instead of introducing a separate vector database.

2. **Lower operational overhead**

   The platform does not need to deploy and maintain an additional vector database.

3. **Unified data model**

   Documents, chunks, embeddings, evaluation records, pipeline configurations, and other metadata can be managed through PostgreSQL.

4. **Transactional consistency**

   Relational metadata and vector records can participate in PostgreSQL transactions.

5. **Easy local development**

   Developers can run PostgreSQL with pgvector locally or through Docker.

6. **Efficient metadata filtering**

   Retrieval can combine vector similarity with structured PostgreSQL filtering.

7. **Simplified deployment**

   Fewer infrastructure dependencies make the initial production deployment easier.

### Negative Consequences

1. A specialized vector database may provide better optimization for very large-scale vector workloads.

2. PostgreSQL performance must be carefully monitored as vector data volume increases.

3. Vector indexes require appropriate configuration and maintenance.

4. Scaling vector workloads independently from relational workloads is less flexible than using a dedicated vector database.

5. Advanced vector-specific features available in specialized systems may not be available immediately.

## Migration Consideration

The application will isolate vector-store operations behind a repository/service abstraction.

This allows the retrieval layer to be changed in the future if NeuroFlow reaches a scale where a dedicated vector database becomes necessary.

A future migration to Pinecone, Weaviate, Qdrant, or another vector store would therefore require replacing the vector-store implementation rather than redesigning the entire retrieval subsystem.

## Status

**Accepted**

## Date

2026-08-25
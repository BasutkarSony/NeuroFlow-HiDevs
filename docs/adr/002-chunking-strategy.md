# ADR 002: Chunking Strategy

## Context

NeuroFlow must split extracted content into smaller chunks before generating embeddings and storing them in PostgreSQL with pgvector.

Chunking directly affects:

- Retrieval accuracy
- Context quality
- Embedding quality
- Context-window usage
- Citation precision
- Generation quality
- Storage and retrieval cost

The main strategies considered are:

1. Fixed-size chunking
2. Sentence-boundary chunking
3. Semantic chunking

## Strategy Comparison

| Criterion | Fixed-Size | Sentence-Boundary | Semantic |
|---|---|---|---|
| Implementation complexity | Low | Low-Medium | High |
| Preserves sentence boundaries | No | Yes | Yes |
| Preserves semantic meaning | Limited | Good | Excellent |
| Processing cost | Low | Low | Higher |
| Predictable chunk size | Excellent | Good | Moderate |
| Retrieval quality | Moderate | Good | Excellent |
| Suitable for mixed modalities | Moderate | Good | Good |
| Easy to tune | Excellent | Good | Moderate |
| Latency | Very low | Low | Higher |

## Decision

NeuroFlow will use **adaptive sentence-aware chunking** as its default chunking strategy.

The system will first identify logical text boundaries such as:

- headings
- paragraphs
- sentences
- sections

Chunks will then be constructed within configurable size limits while preserving sentence and section boundaries whenever possible.

A controlled overlap will be used between adjacent chunks to preserve context across boundaries.

The default configuration will target approximately:

```text
Chunk size: 500-800 tokens
Overlap: 10-15%

The exact values will remain configurable at the pipeline level.

Why Sentence-Aware Chunking

Sentence-aware chunking provides a practical balance between retrieval quality, implementation complexity, and predictable resource usage.

Compared with fixed-size chunking, it avoids splitting sentences or concepts arbitrarily.

Compared with fully semantic chunking, it requires less computation and is easier to reproduce and operate in a production system.

This makes it an appropriate default for the initial NeuroFlow implementation.

Modality Considerations

The chunking strategy will adapt to the input modality.

PDF and DOCX

The system will preserve:

headings
paragraphs
sections
page boundaries
tables where possible

Chunks should avoid crossing unrelated sections when sufficient boundaries are available.

Images

OCR output will be normalized into text before sentence-aware chunking.

Image metadata and source information will remain attached to the resulting chunks.

CSV

Structured records will be grouped according to logical row and column relationships rather than blindly splitting character ranges.

Relevant column names and metadata will be preserved with each chunk.

Web Content

Extracted web content will be cleaned and grouped according to headings, paragraphs, and sentence boundaries.

Navigation elements and unrelated page content should be excluded during preprocessing.

Chunk Metadata

Each chunk will contain metadata including:

document_id
chunk_id
chunk_index
source
modality
page
section
content_hash
embedding_model
created_at

This metadata supports retrieval filtering, provenance, citation tracking, and evaluation.

When to Switch Strategies

Sentence-aware chunking will remain the default unless evaluation demonstrates that it is insufficient for a particular workload.

The system may switch to semantic chunking when:

retrieval recall is consistently below the target threshold
documents contain long, loosely structured sections
related concepts are frequently split across chunk boundaries
evaluation shows that semantic boundaries improve answer quality
domain-specific documents require stronger topic preservation

The system may use fixed-size chunking when:

predictable chunk sizes are more important than semantic boundaries
a modality produces poorly structured text
the extraction process does not provide reliable sentence boundaries
performance constraints require the lowest possible chunking overhead
Evaluation-Based Decision

Chunking strategy changes will be driven by retrieval and generation metrics rather than assumptions.

The following metrics will be monitored:

Context Recall
Context Precision
Faithfulness
Answer Relevance
Retrieval latency
Embedding cost
Number of chunks generated per document

A new strategy should only be adopted when it provides a measurable improvement without unacceptable increases in cost or latency.

Consequences
Positive Consequences
Sentence boundaries are preserved in most chunks.
Retrieval receives coherent units of information.
Citation boundaries are easier to maintain.
Chunk sizes remain reasonably predictable.
The approach is computationally efficient.
The strategy works well for common document formats.
Pipeline-level configuration allows tuning without changing the architecture.
Negative Consequences
Sentence-aware chunking may still separate closely related concepts.
Some documents may have poor sentence or section structure.
Semantic chunking can produce better results for highly unstructured content.
Different modalities may require specialized preprocessing.
Chunk-size and overlap parameters require evaluation and tuning.
Implementation Constraints

The chunking component must:

produce deterministic results for the same input and configuration
preserve source provenance
expose configurable chunk size
expose configurable overlap
preserve document and section metadata
generate stable chunk identifiers
support future semantic chunking
avoid embedding duplicate content unnecessarily
Future Evolution

The chunking implementation will be isolated behind a common interface.

Future strategies can therefore be introduced without changing the ingestion or retrieval architecture.

Possible future strategies include:

semantic chunking
hierarchical chunking
structure-aware chunking
modality-specific chunking

The selected strategy and configuration will be recorded with each ingestion pipeline to maintain reproducibility.

Status

Accepted

Date

2026-08-25
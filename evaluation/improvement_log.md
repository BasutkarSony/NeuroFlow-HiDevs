# Task 18 — Quality Improvement Log

## Baseline

| Metric | Before | Target |
|---|---:|---:|
| Retrieval Hit Rate@10 | TBD | > 0.80 |
| Retrieval MRR@10 | TBD | > 0.60 |
| Faithfulness | TBD | > 0.78 |
| Answer Relevance | TBD | > 0.75 |
| Context Precision | TBD | > 0.72 |
| Overall Eval Score | TBD | > 0.75 |
| P95 Query Latency | TBD | < 4000 ms |

## Improvement 1 — Candidate Depth

**Parameter:** `retrieval.candidate_k`

Increased/configured the number of fused candidates passed toward reranking.

**Before:** hardcoded retrieval/reranking depth.

**After:** configurable `candidate_k` and `reranker_candidate_k`.

**Result:** Record measured A/B result after running the retrieval benchmark.

**Decision:** Keep or revert based on measured quality/latency.

## Improvement 2 — Weighted RRF

**Parameters:**
- `retrieval.dense_weight`
- `retrieval.sparse_weight`
- `retrieval.metadata_weight`
- `retrieval.fusion_k`

RRF now supports configurable source weights.

**Before:** equal unweighted RRF.

**After:** configurable weighted RRF.

**Result:** Record measured A/B result after running the retrieval benchmark.

**Decision:** Keep or revert based on measured quality/latency.

## Improvement 3 — Query Expansion

**Parameter:** `retrieval.query_expansion`

Query expansion can now be explicitly enabled or disabled through pipeline configuration.

**Before:** retrieval always relied on the default query processor behavior.

**After:** expansion is configurable.

**Result:** Record measured A/B result after running the retrieval benchmark.

**Decision:** Keep or revert based on measured quality/latency.

## Improvement 4 — Reranker Candidate Depth

**Parameter:** `retrieval.reranker_candidate_k`

The reranker candidate pool is now configurable rather than fixed at 40.

**Result:** Record measured A/B result after running the retrieval benchmark.

**Decision:** Keep or revert based on measured quality/latency.

## MLflow

A/B experiment runs should record:

- configuration parameters
- Hit Rate@10
- MRR@10
- P95 latency
- generation quality metrics where available
- overall evaluation score

## Measurement Status

The repository was checked for a retrieval ground-truth dataset containing
`relevant_chunk_ids`. None was present. Therefore Hit Rate@10, MRR@10 and
P95 live query latency cannot be honestly calculated from repository data.

The baseline and final JSON files intentionally record these metrics as
`null` rather than inventing results. Once a populated retrieval test set
and configured evaluation environment are available, the existing
`evaluation/retrieval_eval.py` and `tests/benchmarks/retrieval_benchmark.py`
can calculate the required metrics.

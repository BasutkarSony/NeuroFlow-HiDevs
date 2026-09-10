# NeuroFlow Retrieval Benchmark

## Final Status

Status: Not measurable.

The repository does not contain a retrieval ground-truth dataset with relevant_chunk_ids, so final retrieval quality cannot be calculated without inventing evidence. The values in evaluation/quality_final.json therefore remain null.

## Target Metrics

| Metric | Target |
|---|---:|
| Retrieval Hit Rate @10 | >0.80 |
| Retrieval MRR @10 | >0.60 |
| Faithfulness | >0.78 |
| Answer Relevance | >0.75 |
| Context Precision | >0.72 |
| Overall Evaluation Score | >0.75 |
| P95 Query Latency | <4000 ms |

## Improvements Implemented

- Configurable retrieval candidate depth
- Configurable reranker candidate depth
- Weighted Reciprocal Rank Fusion
- Configurable query expansion
- Pipeline configuration consumed by the query API

## Required Next Benchmark

Create and version a representative retrieval dataset containing queries, expected relevant chunk identifiers, and the associated evaluation protocol. Run the retrieval and generation evaluation suite against that fixed dataset and record measured results in evaluation/quality_final.json.

No target is marked as achieved until it is supported by reproducible benchmark evidence.

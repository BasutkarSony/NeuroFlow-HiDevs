# Retrieval benchmark corpus v1

This directory contains a small, controlled corpus for the first reproducible NeuroFlow retrieval benchmark. The CSV files describe six distinct areas of the platform. Each file is intentionally a separate ingestion unit so the benchmark can distinguish the expected source for each query.

## Corpus inventory

| File | Topic |
| --- | --- |
| `ingestion-lifecycle.csv` | Upload validation, asynchronous processing, and status polling |
| `chunking-strategy.csv` | Chunk sizes, overlap, strategy selection, and chunk identifiers |
| `embedding-configuration.csv` | Optional embeddings and behavior without a provider |
| `hybrid-retrieval.csv` | Dense, sparse, metadata retrieval, RRF, and query expansion |
| `reranking-and-context.csv` | Cross-encoder reranking and context assembly |
| `evaluation-metrics.csv` | Hit Rate, MRR, and latency measurement |
| `tenant-and-provenance.csv` | Tenant scoping and chunk provenance |

The documents are authored benchmark fixtures, not external product documentation. Their expected facts are deliberately explicit and should be treated as the benchmark's controlled reference material.

## Ingestion procedure

Run this against a NeuroFlow environment you control. Do not commit API tokens, passwords, or live ingestion identifiers.

1. Configure the API with PostgreSQL and Redis, and configure `LLM_API_KEY` if dense embeddings are part of the run. The API also needs its configured client credentials.
2. Obtain a bearer token:

   ```bash
   curl -sS -X POST "$NEUROFLOW_API/auth/token" \
     -H "Content-Type: application/json" \
     -d "{\"client_id\":\"$NEUROFLOW_CLIENT_ID\",\"client_secret\":\"$NEUROFLOW_CLIENT_SECRET\"}"
   ```

3. Upload each CSV separately. Replace the token placeholder with the returned access token:

   ```bash
   curl -sS -X POST "$NEUROFLOW_API/ingest/file" \
     -H "Authorization: Bearer $NEUROFLOW_TOKEN" \
     -F "source_type=file" \
     -F "filename=ingestion-lifecycle.csv" \
     -F 'metadata={"benchmark":"retrieval-v1","source_id":"ING-001"}' \
     -F "file=@evaluation/corpus/ingestion-lifecycle.csv;type=text/csv"
   ```

   Repeat for every CSV in this directory, changing the filename, `source_id`, and local file path. Save each returned `ingestion_id` outside the repository.

4. Poll `GET $NEUROFLOW_API/ingest/{ingestion_id}` with the same bearer token until every document reports `status: complete`. Confirm `chunk_count > 0`. If embeddings are part of the run, also confirm `embedding_count > 0`. A document with zero embeddings can still participate in sparse-only retrieval, but it is not a dense-retrieval benchmark.

## Collect the real chunk identifiers

The API's ingestion status response intentionally does not expose chunk IDs. After ingestion completes, query the database using the saved document IDs. Run this read-only query in the same database used by the API:

```sql
SELECT
    d.id AS document_id,
    d.filename,
    c.id AS chunk_id,
    c.chunk_index,
    c.content,
    c.metadata
FROM documents AS d
JOIN chunks AS c ON c.document_id = d.id
WHERE d.id = ANY($1::uuid[])
ORDER BY d.filename, c.chunk_index;
```

Pass the seven ingestion UUIDs as the `$1` UUID array. Verify that each returned chunk belongs to the expected source file. Copy the actual `chunks.id` UUIDs—not document IDs—into the annotation template.

## Human annotation

Use [`retrieval_annotation_template.csv`](../retrieval_annotation_template.csv). For each query:

1. Inspect the stored chunk content returned by the SQL query.
2. Identify every chunk that directly supports the stated fact. Do not label a chunk merely because it comes from the expected document.
3. Put all relevant chunk UUIDs in `relevant_chunk_ids`, separated by semicolons if there is more than one.
4. Have a second reviewer verify the evidence-to-query match where possible.
5. Keep queries whose expected fact is not present in the ingested chunks out of the benchmark until the corpus or query is corrected.

The template is intentionally not a benchmark input yet: its `relevant_chunk_ids` cells are blank. Do not fill them with guessed IDs. Once every row has been reviewed, convert the approved annotations into the JSON format consumed by `tests/benchmarks/retrieval_benchmark.py`:

```json
[
  {
    "query": "What is the maximum supported file upload size?",
    "relevant_chunk_ids": ["<actual-chunk-uuid>"]
  }
]
```

Replace the illustrative placeholder with the actual database UUID. The JSON benchmark dataset must be non-empty and every query must have at least one real relevant chunk ID.

## Generate the benchmark input

After every annotation row has been reviewed and populated with real chunk UUIDs, generate the JSON file consumed by the benchmark:

```bash
python -m evaluation.build_retrieval_dataset \
  --input evaluation/retrieval_annotation_template.csv \
  --output evaluation/retrieval_test_set.json
```

The builder rejects blank labels, duplicate query IDs, malformed or repeated chunk UUIDs, and missing required columns. It does not invent labels or modify the CSV. The generated JSON is created only after the complete CSV passes validation. Then run:

```bash
python tests/benchmarks/retrieval_benchmark.py
```

The benchmark still requires a configured retrieval pipeline to calculate scores; generating the JSON validates annotations but does not claim retrieval quality.

## Benchmark controls and limitations

- Keep this corpus version fixed for a benchmark run. If source content or chunking configuration changes, ingest a new version and relabel it.
- Record the API commit, pipeline configuration, embedding model, reranker model, and ingestion IDs alongside the benchmark output.
- Do not mix chunks from different tenants or ingestion runs.
- Run at least one sparse-only benchmark and, when embeddings are available, a dense/hybrid benchmark. Record the configuration for each.
- The current retrieval implementation initializes a cross-encoder reranker by default. Ensure its model is available in the runtime before running the benchmark.
- The repository does not provide a live API URL, database connection, or credentials to this workflow. Therefore no ingestion was performed here and no chunk IDs or retrieval scores are claimed.

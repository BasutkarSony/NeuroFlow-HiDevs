import asyncio
import json
from types import SimpleNamespace

import pytest

from tests.benchmarks.retrieval_benchmark import (
    benchmark,
    load_dataset,
    percentile,
    validate_dataset,
)


def test_validate_dataset_accepts_manually_labelled_examples():
    dataset = [
        {
            "query": "What is retrieval augmented generation?",
            "relevant_chunk_ids": ["chunk-1", "chunk-2"],
        }
    ]

    assert validate_dataset(dataset) == dataset


@pytest.mark.parametrize(
    "dataset",
    [
        [],
        {},
        [{"query": "", "relevant_chunk_ids": ["chunk-1"]}],
        [{"query": "What is RAG?", "relevant_chunk_ids": []}],
        [{"query": "What is RAG?", "relevant_chunk_ids": [" "]}],
        [None],
    ],
)
def test_validate_dataset_rejects_invalid_examples(dataset):
    with pytest.raises(ValueError):
        validate_dataset(dataset)


def test_load_dataset_reads_and_validates_json(tmp_path):
    path = tmp_path / "retrieval_test_set.json"
    expected = [{"query": "What is RAG?", "relevant_chunk_ids": ["chunk-1"]}]
    path.write_text(json.dumps(expected), encoding="utf-8")

    assert load_dataset(str(path)) == expected


def test_load_dataset_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(str(tmp_path / "missing.json"))


def test_load_dataset_rejects_invalid_json(tmp_path):
    path = tmp_path / "retrieval_test_set.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="valid JSON"):
        load_dataset(str(path))


def test_percentile_interpolates_between_values():
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0


def test_percentile_handles_empty_values():
    assert percentile([], 0.95) == 0.0


@pytest.mark.parametrize("p", [-0.1, 1.1])
def test_percentile_rejects_out_of_range_percentiles(p):
    with pytest.raises(ValueError):
        percentile([1.0, 2.0], p)


def test_percentile_rejects_non_finite_values():
    with pytest.raises(ValueError):
        percentile([1.0, float("inf")], 0.95)


def test_benchmark_reports_hit_rate_mrr_and_latency():
    class Pipeline:
        async def retrieve(self, query, k):
            assert k == 2
            if query == "first":
                chunks = [
                    SimpleNamespace(chunk_id="irrelevant"),
                    SimpleNamespace(chunk_id="relevant"),
                ]
            else:
                chunks = [SimpleNamespace(chunk_id="other")]
            return {"chunks_used": chunks}

    dataset = [
        {"query": "first", "relevant_chunk_ids": ["relevant"]},
        {"query": "second", "relevant_chunk_ids": ["missing"]},
    ]

    result = asyncio.run(benchmark(Pipeline(), dataset, k=2))

    assert result["test_count"] == 2
    assert result["k"] == 2
    assert result["hit_rate_at_k"] == 0.5
    assert result["mrr_at_k"] == 0.25
    assert result["p95_latency_ms"] >= 0


def test_benchmark_rejects_zero_k():
    with pytest.raises(ValueError, match="k must be greater"):
        asyncio.run(benchmark(None, [{"query": "q", "relevant_chunk_ids": ["id"]}], k=0))

import csv
import json
import uuid

import pytest

from evaluation.build_retrieval_dataset import build_dataset, write_dataset


def write_annotations(path, rows, fieldnames=None):
    columns = fieldnames or [
        "query_id",
        "query",
        "expected_source_file",
        "supporting_fact",
        "relevant_chunk_ids",
        "reviewer",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def annotation(**overrides):
    row = {
        "query_id": "Q01",
        "query": "What is the upload limit?",
        "expected_source_file": "ingestion-lifecycle.csv",
        "supporting_fact": "The upload limit is 25 MiB.",
        "relevant_chunk_ids": str(uuid.uuid4()),
        "reviewer": "reviewer-1",
        "notes": "",
    }
    row.update(overrides)
    return row


def test_build_dataset_converts_reviewed_csv_to_benchmark_schema(tmp_path):
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    source = tmp_path / "annotations.csv"
    write_annotations(
        source,
        [annotation(relevant_chunk_ids=f"{first_id}; {second_id}")],
    )

    dataset = build_dataset(source)

    assert dataset == [
        {
            "query": "What is the upload limit?",
            "relevant_chunk_ids": [first_id, second_id],
        }
    ]


def test_build_dataset_rejects_blank_ground_truth(tmp_path):
    source = tmp_path / "annotations.csv"
    write_annotations(source, [annotation(relevant_chunk_ids="")])

    with pytest.raises(ValueError, match="complete human annotation"):
        build_dataset(source)


def test_build_dataset_rejects_invalid_chunk_uuid(tmp_path):
    source = tmp_path / "annotations.csv"
    write_annotations(source, [annotation(relevant_chunk_ids="not-a-uuid")])

    with pytest.raises(ValueError, match="invalid chunk UUID"):
        build_dataset(source)


def test_build_dataset_rejects_duplicate_query_ids(tmp_path):
    source = tmp_path / "annotations.csv"
    write_annotations(source, [annotation(), annotation()])

    with pytest.raises(ValueError, match="repeats query_id"):
        build_dataset(source)


def test_build_dataset_rejects_duplicate_chunk_ids_in_one_row(tmp_path):
    chunk_id = str(uuid.uuid4())
    source = tmp_path / "annotations.csv"
    write_annotations(
        source,
        [annotation(relevant_chunk_ids=f"{chunk_id};{chunk_id}")],
    )

    with pytest.raises(ValueError, match="repeats chunk UUID"):
        build_dataset(source)


def test_build_dataset_rejects_missing_required_columns(tmp_path):
    source = tmp_path / "annotations.csv"
    write_annotations(
        source,
        [{"query": "What is RAG?"}],
        fieldnames=["query"],
    )

    with pytest.raises(ValueError, match="missing required columns"):
        build_dataset(source)


def test_write_dataset_outputs_benchmark_json(tmp_path):
    source = tmp_path / "annotations.csv"
    output = tmp_path / "generated" / "retrieval_test_set.json"
    chunk_id = str(uuid.uuid4())
    write_annotations(source, [annotation(relevant_chunk_ids=chunk_id)])

    count = write_dataset(source, output)

    assert count == 1
    assert json.loads(output.read_text(encoding="utf-8")) == [
        {"query": "What is the upload limit?", "relevant_chunk_ids": [chunk_id]}
    ]


def test_write_dataset_does_not_create_output_for_incomplete_annotations(tmp_path):
    source = tmp_path / "annotations.csv"
    output = tmp_path / "retrieval_test_set.json"
    write_annotations(source, [annotation(relevant_chunk_ids="")])

    with pytest.raises(ValueError):
        write_dataset(source, output)

    assert not output.exists()

"""Build the retrieval benchmark JSON from reviewed CSV annotations."""

import argparse
import csv
import json
import uuid
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("evaluation/retrieval_annotation_template.csv")
DEFAULT_OUTPUT = Path("evaluation/retrieval_test_set.json")
REQUIRED_COLUMNS = {
    "query_id",
    "query",
    "expected_source_file",
    "supporting_fact",
    "relevant_chunk_ids",
}


def build_dataset(input_path: str | Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
    """Load reviewed annotations and reject incomplete or invalid ground truth."""
    source = Path(input_path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                "Annotation CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )

        dataset = []
        seen_query_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            query_id = (row.get("query_id") or "").strip()
            query = (row.get("query") or "").strip()
            source_file = (row.get("expected_source_file") or "").strip()
            supporting_fact = (row.get("supporting_fact") or "").strip()
            raw_ids = (row.get("relevant_chunk_ids") or "").strip()

            if not query_id or not query or not source_file or not supporting_fact:
                raise ValueError(
                    f"Row {row_number} must include query_id, query, "
                    "expected_source_file, and supporting_fact."
                )
            if query_id in seen_query_ids:
                raise ValueError(f"Row {row_number} repeats query_id {query_id!r}.")
            seen_query_ids.add(query_id)

            if not raw_ids:
                raise ValueError(
                    f"Row {row_number} ({query_id}) has no relevant_chunk_ids; "
                    "complete human annotation before benchmarking."
                )

            relevant_ids = []
            for raw_id in raw_ids.split(";"):
                value = raw_id.strip()
                if not value:
                    continue
                try:
                    canonical_id = str(uuid.UUID(value))
                except (ValueError, AttributeError) as exc:
                    raise ValueError(
                        f"Row {row_number} ({query_id}) contains an invalid "
                        f"chunk UUID: {value!r}."
                    ) from exc
                if canonical_id in relevant_ids:
                    raise ValueError(
                        f"Row {row_number} ({query_id}) repeats chunk UUID "
                        f"{canonical_id}."
                    )
                relevant_ids.append(canonical_id)

            if not relevant_ids:
                raise ValueError(
                    f"Row {row_number} ({query_id}) has no valid relevant chunk UUIDs."
                )

            dataset.append(
                {"query": query, "relevant_chunk_ids": relevant_ids}
            )

    if not dataset:
        raise ValueError("The annotation CSV contains no benchmark rows.")
    return dataset


def write_dataset(
    input_path: str | Path = DEFAULT_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> int:
    """Write validated annotations in the format consumed by retrieval_benchmark."""
    dataset = build_dataset(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(dataset, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(dataset)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build retrieval_test_set.json from reviewed CSV annotations."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        count = write_dataset(args.input, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Dataset not generated: {exc}\n")

    print(f"Generated {args.output} with {count} reviewed queries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

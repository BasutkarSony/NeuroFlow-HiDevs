import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = (
    "You are a precise research assistant. Answer the user's question "
    "using ONLY the provided context."
)

PII_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b"),
)


@dataclass
class TrainingPair:
    id: str
    run_id: str
    system_prompt: str
    user_message: str
    assistant_message: str
    quality_score: float


def _token_count(text: str) -> int:
    # Lightweight validation without requiring a second tokenizer.
    return len(re.findall(r"\S+", text))


def _contains_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in PII_PATTERNS)


def validate_pair(row: dict[str, Any]) -> bool:
    answer = row["assistant_message"]
    query = row["user_message"]
    quality = row["quality_score"]

    if not quality or float(quality) <= 0.8:
        return False

    tokens = _token_count(answer)

    if tokens < 50 or tokens > 2000:
        return False

    if not re.search(r"\[Source\s+\d+\]", answer):
        return False

    if _contains_pii(query):
        return False

    return True


def _format_pair(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "system",
                "content": row.get("system_prompt") or SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": row["user_message"],
            },
            {
                "role": "assistant",
                "content": row["assistant_message"],
            },
        ]
    }


async def extract_training_pairs(
    db,
    job_id: str,
    output_dir: str = "training_data",
) -> list[TrainingPair]:
    rows = await db.fetch(
        """
        SELECT
            tp.id,
            tp.run_id,
            tp.system_prompt,
            tp.user_message,
            tp.assistant_message,
            tp.quality_score
        FROM training_pairs tp
        JOIN pipeline_runs pr
            ON pr.id = tp.run_id
        LEFT JOIN evaluations e
            ON e.run_id = pr.id
        WHERE tp.quality_score >= 0.82
          AND tp.included_in_job IS NULL
          AND (e.user_rating >= 4 OR e.user_rating IS NULL)
        ORDER BY tp.created_at ASC
        """
    )

    valid = [
        row for row in rows
        if validate_pair(dict(row))
    ]

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    jsonl_path = path / f"{job_id}.jsonl"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in valid:
            handle.write(
                json.dumps(
                    _format_pair(dict(row)),
                    ensure_ascii=False,
                )
                + "\n"
            )

    pairs = [
        TrainingPair(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            system_prompt=row.get("system_prompt") or SYSTEM_PROMPT,
            user_message=row["user_message"],
            assistant_message=row["assistant_message"],
            quality_score=float(row["quality_score"]),
        )
        for row in valid
    ]

    if valid:
        await db.execute(
            """
            UPDATE training_pairs
            SET included_in_job = $1::uuid
            WHERE id = ANY($2::uuid[])
            """,
            job_id,
            [row["id"] for row in valid],
        )

    return pairs

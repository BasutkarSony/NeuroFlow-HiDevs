import re
from dataclasses import dataclass
from typing import Any


SOURCE_PATTERN = re.compile(
    r"\[Source\s+(\d+)\]",
    re.IGNORECASE,
)


@dataclass
class Citation:
    reference: str
    chunk_id: str
    document_name: str
    page_number: int | None
    content_preview: str


def parse_citations(
    response: str,
    chunks: list[Any],
) -> list[dict[str, Any]]:
    citations = []
    seen = set()

    for match in SOURCE_PATTERN.finditer(response):
        source_number = int(match.group(1))
        reference = f"Source {source_number}"

        if source_number < 1 or source_number > len(chunks):
            citations.append(
                {
                    "reference": reference,
                    "invalid_citation": True,
                }
            )
            continue

        chunk = chunks[source_number - 1]

        if source_number in seen:
            continue

        seen.add(source_number)

        metadata = getattr(chunk, "metadata", None) or {}

        document_name = str(
            metadata.get(
                "filename",
                metadata.get("document", "unknown"),
            )
        )

        page = metadata.get(
            "page_number",
            metadata.get("page"),
        )

        try:
            page_number = int(page) if page is not None else None
        except (TypeError, ValueError):
            page_number = None

        citations.append(
            Citation(
                reference=reference,
                chunk_id=str(chunk.chunk_id),
                document_name=document_name,
                page_number=page_number,
                content_preview=chunk.content[:100],
            ).__dict__
        )

    return citations

import re

import tiktoken

from .extractors import ExtractedPage


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _fixed_size(text: str, max_tokens: int = 512) -> list[str]:
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    chunks = []
    start = 0
    overlap = 64

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        candidate = encoding.decode(tokens[start:end])

        if end < len(tokens):
            sentences = _sentences(candidate)
            if sentences:
                target = int(max_tokens * 0.9)
                running = 0
                selected = []

                for sentence in sentences:
                    count = len(encoding.encode(sentence))
                    if running + count > target and selected:
                        break
                    selected.append(sentence)
                    running += count

                candidate = " ".join(selected)
                end = start + len(
                    encoding.encode(candidate)
                )

        chunks.append(candidate.strip())

        if end >= len(tokens):
            break

        start = max(end - overlap, start + 1)

    return chunks


def _semantic(
    text: str,
    embedding_provider=None,
) -> list[str]:
    sentences = _sentences(text)

    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    if embedding_provider is None:
        return _fixed_size(text)

    import asyncio

    embeddings = asyncio.run(
        embedding_provider.embed(sentences)
    )

    chunks = []
    current = [sentences[0]]

    for index in range(1, len(sentences)):
        previous = embeddings[index - 1]
        current_embedding = embeddings[index]

        dot = sum(
            a * b
            for a, b in zip(previous, current_embedding)
        )

        norm_a = sum(a * a for a in previous) ** 0.5
        norm_b = sum(
            b * b
            for b in current_embedding
        ) ** 0.5

        similarity = (
            dot / (norm_a * norm_b)
            if norm_a and norm_b
            else 0.0
        )

        if similarity < 0.7:
            chunks.append(" ".join(current))
            current = [sentences[index]]
        else:
            current.append(sentences[index])

    if current:
        chunks.append(" ".join(current))

    return chunks


def _hierarchical(
    pages: list[ExtractedPage],
) -> list[dict]:
    chunks = []
    parent = None

    for page in pages:
        level = page.metadata.get("level")

        if level == "h1":
            parent = {
                "content": page.content,
                "metadata": {
                    "level": "h1",
                    "section": page.metadata.get(
                        "section",
                        page.content,
                    ),
                    "parent_id": None,
                },
            }
            chunks.append(parent)

        elif level and level.startswith("h"):
            child = {
                "content": page.content,
                "metadata": {
                    "level": level,
                    "section": page.metadata.get(
                        "section",
                        page.content,
                    ),
                    "parent_id": (
                        id(parent) if parent else None
                    ),
                },
            }
            chunks.append(child)

        else:
            chunks.append(
                {
                    "content": page.content,
                    "metadata": {
                        "parent_id": (
                            id(parent) if parent else None
                        ),
                    },
                }
            )

    return chunks


def select_strategy(
    pages: list[ExtractedPage],
) -> str:
    if not pages:
        return "fixed_size"

    if all(
        page.content_type == "table"
        for page in pages
    ):
        return "fixed_size"

    if any(
        page.metadata.get("level") == "h1"
        for page in pages
    ):
        return "hierarchical"

    if len(pages) > 50:
        return "semantic"

    return "fixed_size"


def chunk_pages(
    pages: list[ExtractedPage],
    embedding_provider=None,
) -> list[dict]:
    strategy = select_strategy(pages)

    if strategy == "hierarchical":
        chunks = _hierarchical(pages)
    else:
        chunks = []

        for page in pages:
            texts = (
                _semantic(
                    page.content,
                    embedding_provider,
                )
                if strategy == "semantic"
                else _fixed_size(page.content)
            )

            for text in texts:
                chunks.append(
                    {
                        "content": text,
                        "metadata": {
                            **page.metadata,
                            "page_number": page.page_number,
                            "strategy": strategy,
                        },
                    }
                )

    return chunks
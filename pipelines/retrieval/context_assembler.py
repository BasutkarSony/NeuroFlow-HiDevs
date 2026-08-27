import re
from typing import Any

import tiktoken

from pipelines.retrieval.fusion import RetrievalResult


class ContextAssembler:
    def __init__(
        self,
        token_budget: int = 4000,
    ):
        self.token_budget = token_budget
        self.encoding = tiktoken.get_encoding(
            "cl100k_base"
        )

    def assemble(
        self,
        chunks: list[RetrievalResult],
    ) -> dict[str, Any]:
        context_parts = []
        chunks_used = []
        sources = []
        total_tokens = 0

        for index, chunk in enumerate(chunks, start=1):
            source_name = self._source_name(chunk, index)
            page = self._page_number(chunk)

            header = (
                f"[Source {index} — "
                f"{source_name}, page {page}]\n"
            )

            candidate = header + chunk.content
            candidate_tokens = len(
                self.encoding.encode(candidate)
            )

            if total_tokens + candidate_tokens <= self.token_budget:
                context_parts.append(candidate)
                chunks_used.append(chunk)
                sources.append(source_name)
                total_tokens += candidate_tokens
                continue

            remaining = (
                self.token_budget - total_tokens
            )

            if remaining <= 0:
                break

            truncated = self._fit_sentence_boundary(
                candidate,
                remaining,
            )

            if truncated:
                context_parts.append(truncated)
                chunks_used.append(chunk)
                sources.append(source_name)
                total_tokens += len(
                    self.encoding.encode(truncated)
                )

            break

        return {
            "context": "\n\n".join(context_parts),
            "chunks_used": chunks_used,
            "total_tokens": total_tokens,
            "sources": sources,
        }

    @staticmethod
    def _source_name(
        chunk: RetrievalResult,
        index: int,
    ) -> str:
        metadata = chunk.metadata or {}

        return str(
            metadata.get(
                "filename",
                metadata.get(
                    "source",
                    f"document_{index}",
                ),
            )
        )

    @staticmethod
    def _page_number(
        chunk: RetrievalResult,
    ) -> str:
        metadata = chunk.metadata or {}

        return str(
            metadata.get(
                "page_number",
                metadata.get("page", "?"),
            )
        )

    def _fit_sentence_boundary(
        self,
        text: str,
        max_tokens: int,
    ) -> str:
        tokens = self.encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        candidate = self.encoding.decode(
            tokens[:max_tokens]
        )

        sentences = re.split(
            r"(?<=[.!?])\s+",
            candidate,
        )

        if len(sentences) <= 1:
            return ""

        sentences.pop()

        result = " ".join(
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        )

        return result

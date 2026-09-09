import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ProcessedQuery:
    original: str
    expansions: list[str]
    filters: dict[str, Any]
    query_type: str


class QueryProcessor:
    def __init__(self, llm=None):
        self.llm = llm

    async def process(self, query: str) -> ProcessedQuery:
        expansions = await self._expand_query(query)
        filters = self._extract_metadata_filters(query)
        query_type = self._classify_query(query)

        return ProcessedQuery(
            original=query,
            expansions=expansions,
            filters=filters,
            query_type=query_type,
        )

    async def _expand_query(self, query: str) -> list[str]:
        if self.llm is None:
            return [query]

        prompt = (
            "Generate 2 alternative phrasings of this query. "
            "Return only a JSON array of strings.\n"
            f"Query: {query}"
        )

        result = await self.llm.complete(
            [{"role": "user", "content": prompt}]
        )

        text = getattr(result, "text", str(result))

        try:
            alternatives = json.loads(text)
            if isinstance(alternatives, list):
                return [query] + [
                    str(item) for item in alternatives[:2]
                ]
        except (json.JSONDecodeError, TypeError):
            pass

        return [query]

    def _extract_metadata_filters(
        self,
        query: str,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {}

        year = re.search(
            r"\b(19|20)\d{2}\b",
            query,
        )

        if year:
            filters["year"] = int(year.group())

        climate_terms = re.search(
            r"\b(climate|climate change)\b",
            query,
            re.IGNORECASE,
        )

        if climate_terms:
            filters["topic"] = "climate"

        return filters

    def _classify_query(self, query: str) -> str:
        lowered = query.lower()

        if any(word in lowered for word in ("compare", "difference", "versus", "vs")):
            return "comparative"

        if any(word in lowered for word in ("why", "analyze", "analysis", "impact")):
            return "analytical"

        if any(word in lowered for word in ("how to", "steps to", "procedure", "implement")):
            return "procedural"

        return "factual"

from dataclasses import dataclass
from typing import Any


BASE_SYSTEM_PROMPT = """You are a precise research assistant. Answer the user's question using ONLY the provided context.
If the context does not contain enough information to answer fully, say so explicitly.
For every factual claim, include a citation in the format [Source N].
Do not introduce information not present in the context.
"""


QUERY_TYPE_INSTRUCTIONS = {
    "factual": (
        "Provide a direct, concise answer. "
        "If multiple sources agree, cite all of them."
    ),
    "analytical": (
        "Analyze and synthesize across the provided sources. "
        "Identify agreements and contradictions."
    ),
    "comparative": (
        "Organize your response as a structured comparison. "
        "Use a table if appropriate."
    ),
    "procedural": (
        "Provide numbered steps. Each step must be cited."
    ),
}


@dataclass
class BuiltPrompt:
    system: str
    user: str


class PromptBuilder:
    def build(
        self,
        query: str,
        context: str,
        query_type: str = "factual",
    ) -> BuiltPrompt:
        instruction = QUERY_TYPE_INSTRUCTIONS.get(
            query_type,
            QUERY_TYPE_INSTRUCTIONS["factual"],
        )

        system = (
            BASE_SYSTEM_PROMPT
            + "\n"
            + instruction
        )

        user = (
            "<context>\n"
            f"{context}\n"
            "</context>\n\n"
            f"{query}"
        )

        return BuiltPrompt(
            system=system,
            user=user,
        )

import asyncio
import time
from typing import Any, AsyncIterator

from pipelines.generation.citations import parse_citations
from pipelines.generation.prompt_builder import PromptBuilder


class RAGGenerator:
    def __init__(
        self,
        provider,
        db,
        redis=None,
        prompt_builder=None,
    ):
        self.provider = provider
        self.db = db
        self.redis = redis
        self.prompt_builder = prompt_builder or PromptBuilder()

    async def generate(
        self,
        query: str,
        context_result: dict[str, Any],
        query_type: str = "factual",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        prompt = self.prompt_builder.build(
            query=query,
            context=context_result["context"],
            query_type=query_type,
        )

        messages = [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ]

        if run_id is None:
            run_id = await self._create_run(
                query,
                prompt.system + "\n\n" + prompt.user,
            )

        start = time.perf_counter()
        output_parts = []

        async for token in self.provider.stream(messages):
            output_parts.append(self._extract_delta(token))

        generation = "".join(output_parts)

        citations = parse_citations(
            generation,
            context_result["chunks_used"],
        )

        latency_ms = int(
            (time.perf_counter() - start) * 1000
        )

        input_tokens = self._count_tokens(
            prompt.system + "\n" + prompt.user
        )
        output_tokens = self._count_tokens(generation)

        await self._complete_run(
            run_id,
            generation,
            input_tokens,
            output_tokens,
            latency_ms,
        )

        self._enqueue_evaluation(run_id)

        return {
            "run_id": run_id,
            "generation": generation,
            "citations": citations,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        }

    async def stream(
        self,
        query: str,
        context_result: dict[str, Any],
        query_type: str = "factual",
        run_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        prompt = self.prompt_builder.build(
            query=query,
            context=context_result["context"],
            query_type=query_type,
        )

        messages = [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ]

        if run_id is None:
            run_id = await self._create_run(
                query,
                prompt.system + "\n\n" + prompt.user,
            )

        start = time.perf_counter()
        output_parts = []

        async for token in self.provider.stream(messages):
            delta = self._extract_delta(token)

            if delta:
                output_parts.append(delta)
                yield {
                    "type": "token",
                    "delta": delta,
                }

        generation = "".join(output_parts)

        citations = parse_citations(
            generation,
            context_result["chunks_used"],
        )

        latency_ms = int(
            (time.perf_counter() - start) * 1000
        )

        await self._complete_run(
            run_id,
            generation,
            self._count_tokens(
                prompt.system + "\n" + prompt.user
            ),
            self._count_tokens(generation),
            latency_ms,
        )

        self._enqueue_evaluation(run_id)

        yield {
            "type": "done",
            "run_id": run_id,
            "citations": citations,
        }

    async def _create_run(
        self,
        query: str,
        prompt: str,
    ) -> str:
        row = await self.db.fetchrow(
            """
            INSERT INTO pipeline_runs (
                pipeline_id,
                query,
                status,
                metadata
            )
            VALUES (
                NULL,
                $1,
                'running',
                jsonb_build_object(
                    'assembled_prompt', $2
                )
            )
            RETURNING id
            """,
            query,
            prompt,
        )

        return str(row["id"])

    async def _complete_run(
        self,
        run_id: str,
        generation: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> None:
        await self.db.execute(
            """
            UPDATE pipeline_runs
            SET generation = $1,
                input_tokens = $2,
                output_tokens = $3,
                model_used = $4,
                latency_ms = $5,
                status = 'complete'
            WHERE id = $6
            """,
            generation,
            input_tokens,
            output_tokens,
            getattr(
                self.provider,
                "model_name",
                "unknown",
            ),
            latency_ms,
            run_id,
        )

    def _enqueue_evaluation(self, run_id: str) -> None:
        if self.redis is None:
            return

        asyncio.create_task(
            self.redis.enqueue_job(
                "evaluate_generation",
                run_id,
            )
        )

    @staticmethod
    def _extract_delta(token: Any) -> str:
        if isinstance(token, str):
            return token

        if isinstance(token, dict):
            return str(
                token.get(
                    "delta",
                    token.get("content", ""),
                )
            )

        return str(
            getattr(
                token,
                "delta",
                getattr(token, "content", ""),
            )
        )

    @staticmethod
    def _count_tokens(text: str) -> int:
        try:
            import tiktoken

            encoding = tiktoken.get_encoding(
                "cl100k_base"
            )
            return len(encoding.encode(text))
        except Exception:
            return len(text.split())

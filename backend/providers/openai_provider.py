import asyncio
import time

from openai import AsyncOpenAI, RateLimitError

from .base import BaseLLMProvider, ChatMessage, GenerationResult


class OpenAIProvider(BaseLLMProvider):
    PRICES = {
        "gpt-4o": {
            "input": 2.50,
            "output": 10.00,
        },
        "gpt-4o-mini": {
            "input": 0.15,
            "output": 0.60,
        },
    }

    CONTEXT_WINDOWS = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
    }

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def _messages_to_dict(
        self,
        messages: list[ChatMessage],
    ) -> list[dict]:
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        prices = self.PRICES.get(
            self.model,
            {
                "input": 0.0,
                "output": 0.0,
            },
        )

        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]

        return input_cost + output_cost

    async def complete(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ) -> GenerationResult:
        start_time = time.perf_counter()

        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=self._messages_to_dict(messages),
                    **kwargs,
                )

                latency_ms = (
                    time.perf_counter() - start_time
                ) * 1000

                usage = response.usage

                input_tokens = (
                    usage.prompt_tokens
                    if usage
                    else 0
                )

                output_tokens = (
                    usage.completion_tokens
                    if usage
                    else 0
                )

                return GenerationResult(
                    content=response.choices[0].message.content or "",
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost_usd=self._calculate_cost(
                        input_tokens,
                        output_tokens,
                    ),
                    finish_reason=response.choices[0].finish_reason
                    or "unknown",
                )

            except RateLimitError as exc:
                if attempt == 2:
                    raise

                retry_after = getattr(
                    exc,
                    "retry_after",
                    None,
                )

                if retry_after is None:
                    retry_after = 2 ** attempt

                await asyncio.sleep(retry_after)

        raise RuntimeError("OpenAI request failed")

    async def stream(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ):
        for attempt in range(3):
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=self._messages_to_dict(messages),
                    stream=True,
                    **kwargs,
                )

                async for chunk in stream:
                    if not chunk.choices:
                        continue

                    content = chunk.choices[0].delta.content

                    if content:
                        yield content

                return

            except RateLimitError as exc:
                if attempt == 2:
                    raise

                retry_after = getattr(
                    exc,
                    "retry_after",
                    None,
                )

                if retry_after is None:
                    retry_after = 2 ** attempt

                await asyncio.sleep(retry_after)

    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        embeddings = []

        for start in range(0, len(texts), 100):
            batch = texts[start:start + 100]

            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )

            embeddings.extend(
                item.embedding
                for item in response.data
            )

        return embeddings

    @property
    def cost_per_input_token(self) -> float:
        return (
            self.PRICES.get(
                self.model,
                {"input": 0.0, "output": 0.0},
            )["input"]
            / 1_000_000
        )

    @property
    def cost_per_output_token(self) -> float:
        return (
            self.PRICES.get(
                self.model,
                {"input": 0.0, "output": 0.0},
            )["output"]
            / 1_000_000
        )

    @property
    def context_window(self) -> int:
        return self.CONTEXT_WINDOWS.get(
            self.model,
            128000,
        )
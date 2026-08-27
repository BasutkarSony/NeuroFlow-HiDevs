import asyncio
import time

from anthropic import AsyncAnthropic, RateLimitError

from .base import BaseLLMProvider, ChatMessage, GenerationResult


class AnthropicProvider(BaseLLMProvider):
    PRICES = {
        "claude-3-5-haiku-latest": {
            "input": 0.80,
            "output": 4.00,
        },
        "claude-3-5-sonnet-latest": {
            "input": 3.00,
            "output": 15.00,
        },
    }

    CONTEXT_WINDOWS = {
        "claude-3-5-haiku-latest": 200000,
        "claude-3-5-sonnet-latest": 200000,
    }

    def __init__(
        self,
        model: str = "claude-3-5-haiku-latest",
        api_key: str | None = None,
    ):
        self.model = model
        self.client = AsyncAnthropic(
            api_key=api_key,
        )

    def _prepare_messages(
        self,
        messages: list[ChatMessage],
    ) -> tuple[str | None, list[dict]]:
        system_message = None
        api_messages = []

        for message in messages:
            if message.role == "system":
                system_message = (
                    f"{system_message}\n{message.content}"
                    if system_message
                    else str(message.content)
                )
            else:
                api_messages.append(
                    {
                        "role": message.role,
                        "content": message.content,
                    }
                )

        return system_message, api_messages

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

        system_message, api_messages = self._prepare_messages(messages)

        for attempt in range(3):
            try:
                request = {
                    "model": self.model,
                    "messages": api_messages,
                    "max_tokens": kwargs.pop("max_tokens", 1024),
                    **kwargs,
                }

                if system_message:
                    request["system"] = system_message

                response = await self.client.messages.create(
                    **request,
                )

                latency_ms = (
                    time.perf_counter() - start_time
                ) * 1000

                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                content = ""

                for block in response.content:
                    if getattr(block, "type", None) == "text":
                        content += block.text

                return GenerationResult(
                    content=content,
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost_usd=self._calculate_cost(
                        input_tokens,
                        output_tokens,
                    ),
                    finish_reason=response.stop_reason
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

        raise RuntimeError("Anthropic request failed")

    async def stream(
        self,
        messages: list[ChatMessage],
        **kwargs,
    ):
        system_message, api_messages = self._prepare_messages(messages)

        for attempt in range(3):
            try:
                request = {
                    "model": self.model,
                    "messages": api_messages,
                    "max_tokens": kwargs.pop("max_tokens", 1024),
                    **kwargs,
                }

                if system_message:
                    request["system"] = system_message

                async with self.client.messages.stream(
                    **request,
                ) as stream:
                    async for text in stream.text_stream:
                        yield text

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
        raise NotImplementedError(
            "Anthropic does not provide an embeddings API. "
            "Use OpenAIProvider for embeddings."
        )

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
            200000,
        )
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str
    content: str | list


@dataclass(init=False)
class GenerationResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    finish_reason: str

    def __init__(
        self,
        content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cost_usd: float,
        finish_reason: str,
    ) -> None:
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.cost_usd = cost_usd
        self.finish_reason = finish_reason


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[ChatMessage], **kwargs) -> GenerationResult:
        pass

    @abstractmethod
    async def stream(self, messages: list[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        pass

    @property
    @abstractmethod
    def cost_per_input_token(self) -> float:
        pass

    @property
    @abstractmethod
    def cost_per_output_token(self) -> float:
        pass

    @property
    @abstractmethod
    def context_window(self) -> int:
        pass

from collections import defaultdict

from .base import ChatMessage, GenerationResult
from .router import ModelRouter, RoutingCriteria


class NeuroFlowClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(
        self,
        providers=None,
        redis_client=None,
        tracer=None,
    ):
        if getattr(self, "_initialized", False):
            return

        self.providers = providers or {}
        self.redis = redis_client
        self.tracer = tracer

        self.router = ModelRouter(
            redis_client=self.redis,
            providers=self.providers,
        )

        self._initialized = True

    async def chat(
        self,
        messages: list[ChatMessage],
        routing_criteria: RoutingCriteria,
        **kwargs,
    ) -> GenerationResult:

        provider, model = await self.router.route(
            routing_criteria
        )

        if self.tracer:
            with self.tracer.start_as_current_span(
                "llm.provider.call"
            ) as span:

                result = await provider.complete(
                    messages,
                    **kwargs,
                )

                self._set_span_attributes(
                    span,
                    result,
                )

        else:
            result = await provider.complete(
                messages,
                **kwargs,
            )

        await self._track_metrics(
            model=result.model,
            cost=result.cost_usd,
        )

        return result

    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        provider = self.providers.get("openai")

        if provider is None:
            raise ValueError(
                "No embedding provider configured"
            )

        if self.tracer:
            with self.tracer.start_as_current_span(
                "llm.provider.embed"
            ) as span:

                embeddings = await provider.embed(texts)

                span.set_attribute(
                    "model",
                    "text-embedding-3-small",
                )

        else:
            embeddings = await provider.embed(texts)

        return embeddings

    async def _track_metrics(
        self,
        model: str,
        cost: float,
    ):
        if self.redis is None:
            return

        await self.redis.incr(
            f"metrics:model:{model}:calls"
        )

        await self.redis.incrbyfloat(
            f"metrics:model:{model}:cost_usd",
            cost,
        )

    @staticmethod
    def _set_span_attributes(
        span,
        result: GenerationResult,
    ):
        span.set_attribute(
            "model",
            result.model,
        )

        span.set_attribute(
            "input_tokens",
            result.input_tokens,
        )

        span.set_attribute(
            "output_tokens",
            result.output_tokens,
        )

        span.set_attribute(
            "cost_usd",
            result.cost_usd,
        )

        span.set_attribute(
            "latency_ms",
            result.latency_ms,
        )


_client = None


def get_client(
    providers=None,
    redis_client=None,
    tracer=None,
) -> NeuroFlowClient:
    global _client

    if _client is None:
        _client = NeuroFlowClient(
            providers=providers,
            redis_client=redis_client,
            tracer=tracer,
        )

    return _client
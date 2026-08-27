import json
from dataclasses import dataclass

from .base import BaseLLMProvider


@dataclass
class RoutingCriteria:
    task_type: str
    max_cost_per_call: float | None = None
    require_vision: bool = False
    require_long_context: bool = False
    latency_budget_ms: int | None = None
    prefer_fine_tuned: bool = False


class ModelRouter:
    def __init__(self, redis_client, providers: dict[str, BaseLLMProvider]):
        self.redis = redis_client
        self.providers = providers

    async def _get_models(self) -> list[dict]:
        data = await self.redis.get("router:models")

        if not data:
            return []

        if isinstance(data, bytes):
            data = data.decode("utf-8")

        return json.loads(data)

    async def route(
        self,
        criteria: RoutingCriteria,
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = 500,
    ) -> tuple[BaseLLMProvider, str]:

        models = await self._get_models()

        candidates = []

        for model_config in models:
            model_name = model_config["model"]
            provider_name = model_config["provider"]

            provider = self.providers.get(provider_name)

            if provider is None:
                continue

            capabilities = model_config.get("capabilities", {})

            if criteria.require_vision:
                if not capabilities.get("vision", False):
                    continue

            if criteria.require_long_context:
                context_window = model_config.get(
                    "context_window",
                    provider.context_window,
                )

                if context_window <= 100000:
                    continue

            if (
                criteria.latency_budget_ms is not None
                and model_config.get("latency_ms", 0)
                > criteria.latency_budget_ms
            ):
                continue

            if criteria.task_type == "evaluation":
                if not capabilities.get("judge", False):
                    continue

                if model_config.get("fine_tuned", False):
                    continue

            if (
                criteria.prefer_fine_tuned
                and criteria.task_type != "evaluation"
            ):
                fine_tuned_tasks = model_config.get(
                    "fine_tuned_tasks",
                    [],
                )

                if fine_tuned_tasks:
                    if criteria.task_type not in fine_tuned_tasks:
                        continue

            input_cost = (
                estimated_input_tokens
                * model_config.get(
                    "input_cost_per_token",
                    provider.cost_per_input_token,
                )
            )

            output_cost = (
                estimated_output_tokens
                * model_config.get(
                    "output_cost_per_token",
                    provider.cost_per_output_token,
                )
            )

            estimated_cost = input_cost + output_cost

            if (
                criteria.max_cost_per_call is not None
                and estimated_cost > criteria.max_cost_per_call
            ):
                continue

            candidates.append(
                {
                    "provider": provider,
                    "model": model_name,
                    "cost": estimated_cost,
                    "fine_tuned": model_config.get(
                        "fine_tuned",
                        False,
                    ),
                }
            )

        if not candidates:
            raise ValueError(
                "No model satisfies the routing criteria"
            )

        if (
            criteria.prefer_fine_tuned
            and criteria.task_type != "evaluation"
        ):
            fine_tuned_candidates = [
                candidate
                for candidate in candidates
                if candidate["fine_tuned"]
            ]

            if fine_tuned_candidates:
                candidates = fine_tuned_candidates

        selected = min(
            candidates,
            key=lambda candidate: candidate["cost"],
        )

        selected["provider"].model = selected["model"]

        return (
            selected["provider"],
            selected["model"],
        )
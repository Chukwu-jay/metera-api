from __future__ import annotations

from dataclasses import dataclass

from app.models.api import Usage


@dataclass(frozen=True, slots=True)
class ModelPricing:
    prompt_per_1k_tokens_usd: float
    completion_per_1k_tokens_usd: float


DEFAULT_PRICING = ModelPricing(
    prompt_per_1k_tokens_usd=0.005,
    completion_per_1k_tokens_usd=0.015,
)

MODEL_PRICING: dict[str, ModelPricing] = {
    "gpt-4o-mini": ModelPricing(prompt_per_1k_tokens_usd=0.00015, completion_per_1k_tokens_usd=0.0006),
    "gpt-4o": ModelPricing(prompt_per_1k_tokens_usd=0.005, completion_per_1k_tokens_usd=0.015),
}


def estimate_cost_usd(*, model: str, usage: Usage) -> float:
    pricing = _resolve_pricing(model)
    prompt_cost = (usage.prompt_tokens / 1000.0) * pricing.prompt_per_1k_tokens_usd
    completion_cost = (usage.completion_tokens / 1000.0) * pricing.completion_per_1k_tokens_usd
    return prompt_cost + completion_cost


def _resolve_pricing(model: str) -> ModelPricing:
    normalized = model.lower()
    if normalized in MODEL_PRICING:
        return MODEL_PRICING[normalized]
    for known_model, pricing in MODEL_PRICING.items():
        if normalized.startswith(known_model):
            return pricing
    return DEFAULT_PRICING

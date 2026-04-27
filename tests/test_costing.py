from app.models.api import Usage
from app.observability.costing import estimate_cost_usd


def test_estimate_cost_uses_model_pricing() -> None:
    usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    cost = estimate_cost_usd(model="gpt-4o-mini", usage=usage)
    assert cost == 0.00045


def test_estimate_cost_falls_back_for_unknown_model() -> None:
    usage = Usage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000)
    cost = estimate_cost_usd(model="unknown-model", usage=usage)
    assert cost == 0.02

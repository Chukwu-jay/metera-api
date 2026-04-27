import pytest

from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage, Usage
from app.models.domain import ProxyContext
from app.observability.metrics import COUNTERS, DISTRIBUTIONS, reset_metrics
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="fake-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="ok"))],
            usage=Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )


@pytest.mark.asyncio
async def test_scrub_metrics_increment_for_pii() -> None:
    reset_metrics()
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
        },
    )()
    service = ProxyService(settings=settings, provider=FakeProvider())
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Contact me at joshua@example.com")],
    )

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert response.metera["estimated_cost_usd"] > 0
    assert COUNTERS["requests_total"] == 1
    assert COUNTERS["scrubbed_requests"] == 1
    assert COUNTERS["scrubbed_pii_entities"] >= 1
    assert COUNTERS["usage_total_tokens_total"] == 30
    assert COUNTERS["estimated_upstream_cost_usd_total"] > 0
    assert DISTRIBUTIONS["request_latency_ms"]["count"] == 1

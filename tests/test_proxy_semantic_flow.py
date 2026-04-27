import pytest

from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def create_chat_completion(self, *, request, bearer_token=None):
        self.calls += 1
        return ChatCompletionResponse(
            id=f"fake-{self.calls}",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="upstream"))],
        )


@pytest.mark.asyncio
async def test_proxy_service_returns_semantic_hit_after_first_request() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "semantic_threshold": 0.95,
            "semantic_model_name": "fake-local",
            "dlp_enabled": False,
            "dlp_scrub_level": "off",
            "dlp_analyzer_mode": "regex",
            "dlp_detect_email": None,
            "dlp_detect_phone": None,
            "dlp_detect_ip": None,
            "dlp_detect_secrets": None,
            "dlp_custom_detectors_json": None,
            "dlp_custom_detectors_yaml_path": None,
        },
    )()
    provider = FakeProvider()
    service = ProxyService(settings=settings, provider=provider)

    request_a = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="summarize alpha")])
    request_b = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="summarize alpha")])

    first = await service.handle_chat_completion(request=request_a, context=ProxyContext(namespace="tenant-a"))
    second = await service.handle_chat_completion(request=request_b, context=ProxyContext(namespace="tenant-a"))

    assert first.metera["cache"] == "miss"
    assert second.metera["cache"] in {"exact_hit", "semantic_hit"}
    assert provider.calls == 1

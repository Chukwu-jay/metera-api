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
            choices=[Choice(message=ChoiceMessage(content="Hello from upstream"))],
        )

    async def create_chat_completion_stream(self, *, request, bearer_token=None):
        self.calls += 1

        async def _stream():
            yield b"data: {\"id\":\"stream-1\"}\n\n"
            yield b"data: [DONE]\n\n"

        return _stream()


@pytest.mark.asyncio
async def test_chat_completion_caches_per_namespace() -> None:
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
    provider = FakeProvider()
    service = ProxyService(settings=settings, provider=provider)
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello")],
    )

    first = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))
    second = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert first.model == "gpt-4o-mini"
    assert second.metera["cache"] == "exact_hit"
    assert second.metera["namespace"] == "tenant-a"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_streaming_requests_bypass_cache_writes() -> None:
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
    provider = FakeProvider()
    service = ProxyService(settings=settings, provider=provider)
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hello")],
        stream=True,
    )

    chunks = []
    stream = await service.handle_chat_completion_stream(request=request, context=ProxyContext(namespace="tenant-a"))
    async for chunk in stream:
        chunks.append(chunk)

    follow_up = await service.handle_chat_completion(
        request=ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")]),
        context=ProxyContext(namespace="tenant-a"),
    )

    assert any(b"[DONE]" in chunk for chunk in chunks)
    assert follow_up.metera["cache"] == "miss"
    assert provider.calls == 2

import pytest

from app.cache.normalization import build_exact_cache_key, canonicalize_request, compute_exact_hash
from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="fake-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="ok"))],
        )

    async def create_chat_completion_stream(self, *, request, bearer_token=None):
        async def _stream():
            yield b"data: [DONE]\n\n"

        return _stream()


@pytest.mark.asyncio
async def test_namespace_changes_cache_key() -> None:
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="same prompt")],
    )
    normalized = canonicalize_request(request)
    hash_a = compute_exact_hash(namespace="tenant-a", endpoint="chat.completions", normalized_text=normalized)
    hash_b = compute_exact_hash(namespace="tenant-b", endpoint="chat.completions", normalized_text=normalized)

    assert build_exact_cache_key(namespace="tenant-a", exact_hash=hash_a) != build_exact_cache_key(namespace="tenant-b", exact_hash=hash_b)


@pytest.mark.asyncio
async def test_namespace_is_preserved_in_service_flow() -> None:
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
        messages=[ChatMessage(role="user", content="same prompt")],
    )

    response_a = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))
    response_b = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-b"))

    assert response_a.metera["namespace"] == "tenant-a"
    assert response_b.metera["namespace"] == "tenant-b"


@pytest.mark.asyncio
async def test_admin_invalidation_only_clears_target_namespace() -> None:
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
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="same prompt")])

    await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))
    await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-b"))

    exact_deleted, semantic_deleted = await service.invalidate_namespace("tenant-a")

    response_a = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))
    response_b = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-b"))

    assert exact_deleted >= 1
    assert semantic_deleted >= 0
    assert response_a.metera["cache"] == "miss"
    assert response_b.metera["cache"] == "exact_hit"

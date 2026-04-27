import pytest

from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="event-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="persist me"))],
        )


class RecordingRequestEventRepository:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(self, payload: dict) -> None:
        self.events.append(payload)


@pytest.mark.asyncio
async def test_proxy_service_persists_request_event_for_miss() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "request_event_logging_enabled": True,
            "semantic_enabled": False,
        },
    )()
    repository = RecordingRequestEventRepository()
    service = ProxyService(settings=settings, provider=FakeProvider(), request_event_repository=repository)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")])
    context = ProxyContext(
        namespace="tenant-a",
        tenant_id="tenant_1",
        workspace_id="workspace_1",
        api_key_id="key_1",
        request_id="req_1",
        tenant_slug="acme",
        workspace_slug="default",
    )

    response = await service.handle_chat_completion(request=request, context=context)

    assert response.metera["cache"] == "miss"
    assert len(repository.events) == 1
    event = repository.events[0]
    assert event["request_id"] == "req_1"
    assert event["tenant_id"] == "tenant_1"
    assert event["workspace_id"] == "workspace_1"
    assert event["api_key_id"] == "key_1"
    assert event["cache_outcome"] == "miss"
    assert event["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_proxy_service_skips_request_event_when_disabled() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "request_event_logging_enabled": False,
            "semantic_enabled": False,
        },
    )()
    repository = RecordingRequestEventRepository()
    service = ProxyService(settings=settings, provider=FakeProvider(), request_event_repository=repository)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")])

    await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a", request_id="req_2"))

    assert repository.events == []

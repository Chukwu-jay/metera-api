import pytest

from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="ledger-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="ledger me"))],
        )


class RecordingLedgerRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def log_request(self, payload: dict) -> None:
        self.rows.append(payload)


@pytest.mark.asyncio
async def test_proxy_service_dual_writes_request_ledger_for_miss() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "request_event_logging_enabled": False,
            "request_ledger_enabled": True,
            "semantic_enabled": False,
        },
    )()
    repository = RecordingLedgerRepository()
    service = ProxyService(settings=settings, provider=FakeProvider(), request_ledger_repository=repository)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")])
    context = ProxyContext(
        namespace="tenant-a",
        tenant_id="tenant_1",
        workspace_id="workspace_1",
        environment_id="env_1",
        api_key_id="key_1",
        request_id="req_ledger_1",
        effective_policy_version_id="policy_1",
        effective_policy_mode="soft",
    )

    response = await service.handle_chat_completion(request=request, context=context)

    assert response.metera["cache"] == "miss"
    assert len(repository.rows) == 1
    row = repository.rows[0]
    assert row["request_id"] == "req_ledger_1"
    assert row["tenant_id"] == "tenant_1"
    assert row["workspace_id"] == "workspace_1"
    assert row["environment_id"] == "env_1"
    assert row["api_key_id"] == "key_1"
    assert row["effective_policy_version_id"] == "policy_1"
    assert row["effective_policy_mode"] == "soft"
    assert row["cache_outcome"] == "miss"


@pytest.mark.asyncio
async def test_proxy_service_skips_request_ledger_when_disabled() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "request_event_logging_enabled": False,
            "request_ledger_enabled": False,
            "semantic_enabled": False,
        },
    )()
    repository = RecordingLedgerRepository()
    service = ProxyService(settings=settings, provider=FakeProvider(), request_ledger_repository=repository)

    await service.handle_chat_completion(
        request=ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")]),
        context=ProxyContext(namespace="tenant-a", request_id="req_ledger_2"),
    )

    assert repository.rows == []

import pytest

from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="risk-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="upstream"))],
        )


class RecordingRiskRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def log_event(self, payload: dict) -> None:
        self.rows.append(payload)


class RecordingShadowSavingsRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def log_shadow_savings(self, payload: dict) -> None:
        self.rows.append(payload)


@pytest.mark.asyncio
async def test_proxy_service_persists_shadow_savings_when_threshold_gap_exists() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "semantic_enabled": True,
            "semantic_threshold": 0.95,
            "semantic_shadow_threshold": 0.8,
            "request_event_logging_enabled": False,
            "request_ledger_enabled": False,
            "shadow_savings_logging_enabled": True,
            "risk_event_logging_enabled": False,
        },
    )()
    shadow_repo = RecordingShadowSavingsRepository()
    service = ProxyService(settings=settings, provider=FakeProvider(), shadow_savings_repository=shadow_repo)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")])

    await service.handle_chat_completion(
        request=request,
        context=ProxyContext(namespace="tenant-a", request_id="req_shadow_1", tenant_id="tenant_1", workspace_id="workspace_1"),
    )

    assert len(shadow_repo.rows) == 1
    row = shadow_repo.rows[0]
    assert row["request_id"] == "req_shadow_1"
    assert row["live_threshold"] == 0.95
    assert row["shadow_threshold"] == 0.8


@pytest.mark.asyncio
async def test_proxy_service_persists_risk_event_when_called() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "semantic_enabled": True,
            "semantic_threshold": 0.95,
            "semantic_shadow_threshold": 0.8,
            "request_event_logging_enabled": False,
            "request_ledger_enabled": False,
            "shadow_savings_logging_enabled": False,
            "risk_event_logging_enabled": True,
        },
    )()
    risk_repo = RecordingRiskRepository()
    service = ProxyService(settings=settings, provider=FakeProvider(), risk_event_repository=risk_repo)
    context = ProxyContext(namespace="tenant-a", request_id="req_risk_1", tenant_id="tenant_1", workspace_id="workspace_1")

    await service._persist_risk_event(
        context=context,
        event_type="shadow_regression_alert",
        severity="warning",
        reason="semantic_candidate_rejected",
        payload={"model": "gpt-4o-mini"},
    )

    assert len(risk_repo.rows) == 1
    row = risk_repo.rows[0]
    assert row["request_id"] == "req_risk_1"
    assert row["event_type"] == "shadow_regression_alert"
    assert row["severity"] == "warning"

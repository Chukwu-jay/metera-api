import pytest

from app.controlplane.models.policy import EffectivePolicy
from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="policy-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="policy applied"))],
        )


class FakePolicyResolver:
    async def resolve(self, *, settings, context):
        return EffectivePolicy(
            policy_version_id="policy_999",
            policy_mode="hard",
            dlp_enabled=True,
            dlp_scrub_level="technical",
            semantic_enabled=True,
            semantic_threshold=0.97,
            semantic_shadow_threshold=0.88,
            semantic_max_temperature=0.1,
            identity_guard_enabled=True,
            identity_strict_mode_enabled=True,
            identity_partitioning_enabled=True,
            multimodal_hard_alignment_enabled=True,
            policy_timing_breakdown_enabled=True,
            strict_namespace_prefixes=["faq-billing"],
            high_risk_namespace_prefixes=["faq-billing"],
            source_scope="namespace",
            source_ref_id="workspace_1",
            extension_fields={},
        )


@pytest.mark.asyncio
async def test_proxy_service_applies_scoped_policy_to_context() -> None:
    settings = type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "semantic_enabled": True,
            "semantic_threshold": 0.9,
            "semantic_shadow_threshold": 0.8,
            "semantic_max_temperature": 0.2,
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "scoped_policy_enabled": True,
        },
    )()
    service = ProxyService(settings=settings, provider=FakeProvider(), policy_resolver=FakePolicyResolver())
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hello")])
    context = ProxyContext(namespace="faq-billing", tenant_id="tenant_1", workspace_id="workspace_1", request_id="req_policy")

    response = await service.handle_chat_completion(request=request, context=context)

    assert response.metera["cache"] == "miss"
    assert context.effective_policy_version_id == "policy_999"
    assert context.effective_policy_mode == "hard"
    assert service.policy_overrides["semantic_threshold"] == 0.97

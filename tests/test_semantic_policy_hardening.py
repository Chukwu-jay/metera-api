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
            choices=[Choice(message=ChoiceMessage(content=f"upstream-{self.calls}"))],
        )


class StubSemanticHit:
    def __init__(self, payload, metadata, similarity=0.99) -> None:
        self.payload = payload
        self.metadata = metadata
        self.similarity = similarity


class StubSemanticCache:
    def __init__(self, hit=None) -> None:
        self.hit = hit
        self.add_calls = []
        self.store = type("Store", (), {"invalidate_namespace": staticmethod(lambda namespace: 0)})()

    async def find_match(self, **kwargs):
        return self.hit

    async def add_entry(self, **kwargs):
        self.add_calls.append(kwargs)


class StubShadowAnalyticsStore:
    def __init__(self) -> None:
        self.regression_alerts = []

    async def log_shadow_regression_alert(self, **kwargs):
        self.regression_alerts.append(kwargs)


BASE_SETTINGS = {
    "upstream_base_url": "https://example.com",
    "upstream_api_key": None,
    "upstream_timeout_seconds": 5.0,
    "upstream_max_retries": 1,
    "default_exact_ttl_seconds": 60,
    "default_semantic_ttl_seconds": 60,
    "semantic_threshold": 0.95,
    "semantic_shadow_threshold": 0.8,
    "semantic_max_temperature": 0.2,
    "semantic_enabled": True,
    "dual_mode_enabled": True,
    "semantic_model_name": "fake-local",
    "semantic_disabled_namespace_prefixes": "browser-,faq-billing,agent-,workflow-",
    "semantic_high_risk_namespace_prefixes": "browser-,faq-billing",
    "identity_guard_enabled": True,
    "identity_strict_mode_enabled": False,
    "identity_partitioning_enabled": False,
    "multimodal_hard_alignment_enabled": False,
    "policy_timing_breakdown_enabled": True,
    "dlp_enabled": False,
    "dlp_scrub_level": "off",
    "dlp_analyzer_mode": "regex",
    "dlp_detect_email": None,
    "dlp_detect_phone": None,
    "dlp_detect_ip": None,
    "dlp_detect_secrets": None,
    "dlp_custom_detectors_json": None,
    "dlp_custom_detectors_yaml_path": None,
}


def make_settings(**overrides):
    values = dict(BASE_SETTINGS)
    values.update(overrides)
    return type("S", (), values)()


@pytest.mark.asyncio
async def test_agentic_browser_requests_bypass_semantic_reuse() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(settings=make_settings(), provider=provider, semantic_cache=semantic_cache)
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Navigate to leads and create a contact for Jane Doe. Current DOM: <html><body></body></html>")],
    )

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="browser-metera"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] in {"namespace_policy_disabled", "agentic_request"}
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_browser_namespace_remains_exact_cache_only() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(settings=make_settings(), provider=provider, semantic_cache=semantic_cache)
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Navigate to leads and create a contact for Jane Doe")],
    )

    first = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="browser-metera"))
    second = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="browser-metera"))

    assert first.metera["cache"] == "miss"
    assert first.metera["semantic_bypass_reason"] in {"namespace_policy_disabled", "agentic_request"}
    assert second.metera["cache"] == "exact_hit"
    assert provider.calls == 1
    assert semantic_cache.add_calls == []


@pytest.mark.asyncio
async def test_semantic_opt_out_header_mode_bypasses_semantic_reuse() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(settings=make_settings(), provider=provider, semantic_cache=semantic_cache)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="summarize alpha")])

    response = await service.handle_chat_completion(
        request=request,
        context=ProxyContext(namespace="tenant-a", semantic_cache_mode="off"),
    )

    assert response.metera["semantic_bypass_reason"] == "semantic_opt_out"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_incompatible_semantic_hit_is_rejected_when_dual_mode_enabled() -> None:
    provider = FakeProvider()
    hit_payload = ChatCompletionResponse(
        id="cached-1",
        model="gpt-4o-mini",
        choices=[Choice(message=ChoiceMessage(content="stale cached answer"))],
    ).model_dump()
    semantic_cache = StubSemanticCache(
        hit=StubSemanticHit(
            payload=hit_payload,
            metadata={
                "intent": "chat_generic",
                "module": None,
                "entity_fingerprint": "wrong",
                "has_visual_context": False,
                "has_dom_context": False,
                "is_agentic": False,
            },
        )
    )
    service = ProxyService(settings=make_settings(dual_mode_enabled=True), provider=provider, semantic_cache=semantic_cache)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="summarize alpha")])

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] == "shadow_regression_alert"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_incompatible_semantic_hit_logs_shadow_alert_when_dual_mode_disabled() -> None:
    provider = FakeProvider()
    shadow_store = StubShadowAnalyticsStore()
    hit_payload = ChatCompletionResponse(
        id="cached-1",
        model="gpt-4o-mini",
        choices=[Choice(message=ChoiceMessage(content="stale cached answer"))],
    ).model_dump()
    semantic_cache = StubSemanticCache(
        hit=StubSemanticHit(
            payload=hit_payload,
            metadata={
                "intent": "chat_generic",
                "module": None,
                "entity_fingerprint": "wrong",
                "has_visual_context": False,
                "has_dom_context": False,
                "is_agentic": False,
            },
        )
    )
    service = ProxyService(
        settings=make_settings(dual_mode_enabled=False),
        provider=provider,
        semantic_cache=semantic_cache,
        shadow_analytics_store=shadow_store,
    )
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="summarize alpha")])

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] == "shadow_regression_alert"
    assert len(shadow_store.regression_alerts) == 1
    assert shadow_store.regression_alerts[0]["rejection_reason"] == "entity_mismatch"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_visual_context_auto_hard_bypasses_semantic_reuse() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(settings=make_settings(), provider=provider, semantic_cache=semantic_cache)
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Please review this screenshot [visual_context image_b64_chars=2048] and summarize the issue.")],
    )

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="faq-general"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] == "visual_context_auto_hard"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_high_risk_text_namespace_hard_enforces_mismatch_rejection() -> None:
    provider = FakeProvider()
    shadow_store = StubShadowAnalyticsStore()
    hit_payload = ChatCompletionResponse(
        id="cached-1",
        model="gpt-4o-mini",
        choices=[Choice(message=ChoiceMessage(content="stale cached answer"))],
    ).model_dump()
    semantic_cache = StubSemanticCache(
        hit=StubSemanticHit(
            payload=hit_payload,
            metadata={
                "intent": "chat_generic",
                "module": None,
                "entity_fingerprint": "wrong",
                "has_visual_context": False,
                "has_dom_context": False,
                "is_agentic": False,
            },
        )
    )
    service = ProxyService(
        settings=make_settings(dual_mode_enabled=True, semantic_high_risk_namespace_prefixes="faq-billing"),
        provider=provider,
        semantic_cache=semantic_cache,
        shadow_analytics_store=shadow_store,
    )
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="What is the refund status for invoice INV-1002 for Acme South?")])

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="faq-billing"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] == "entity_mismatch"
    assert len(shadow_store.regression_alerts) == 0
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_soft_support_namespace_logs_shadow_alert_and_misses() -> None:
    provider = FakeProvider()
    shadow_store = StubShadowAnalyticsStore()
    hit_payload = ChatCompletionResponse(
        id="cached-1",
        model="gpt-4o-mini",
        choices=[Choice(message=ChoiceMessage(content="stale cached answer"))],
    ).model_dump()
    semantic_cache = StubSemanticCache(
        hit=StubSemanticHit(
            payload=hit_payload,
            metadata={
                "intent": "chat_generic",
                "module": None,
                "entity_fingerprint": "wrong",
                "identity_fingerprint": "wrong",
                "identity_scope_hash": "wrong",
                "has_visual_context": False,
                "has_dom_context": False,
                "is_agentic": False,
            },
        )
    )
    service = ProxyService(
        settings=make_settings(dual_mode_enabled=True, semantic_high_risk_namespace_prefixes="faq-billing"),
        provider=provider,
        semantic_cache=semantic_cache,
        shadow_analytics_store=shadow_store,
    )
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Summarize support ticket TCK-3002 for customer John Roe about MFA lockout.")])

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="support-bulk"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] == "shadow_regression_alert"
    assert len(shadow_store.regression_alerts) == 1
    assert shadow_store.regression_alerts[0]["rejection_reason"] in {"entity_mismatch", "identity_mismatch", "identity_partition_mismatch"}
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_identity_strict_mode_bypasses_semantic_for_identifier_requests() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(
        settings=make_settings(identity_strict_mode_enabled=True),
        provider=provider,
        semantic_cache=semantic_cache,
    )
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Lookup record UUID=123e4567e89b12d3a456426614174000 and summarize its state.")],
    )

    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert response.metera["cache"] == "miss"
    assert response.metera["semantic_bypass_reason"] == "identity_sensitive_request"
    assert semantic_cache.find_calls == []
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_identity_partitioning_filters_semantic_lookup() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(
        settings=make_settings(identity_partitioning_enabled=True),
        provider=provider,
        semantic_cache=semantic_cache,
    )
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Give me my account balance for USER_ID=user-01 ACCOUNT_ID=ACC-01.")],
    )

    await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert semantic_cache.find_calls
    assert semantic_cache.find_calls[0]["metadata_filters"]["identity_scope_hash"]


@pytest.mark.asyncio
async def test_semantic_entries_store_request_fingerprint_metadata() -> None:
    provider = FakeProvider()
    semantic_cache = StubSemanticCache()
    service = ProxyService(settings=make_settings(), provider=provider, semantic_cache=semantic_cache)
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="summarize alpha")])

    await service.handle_chat_completion(request=request, context=ProxyContext(namespace="tenant-a"))

    assert semantic_cache.add_calls
    metadata = semantic_cache.add_calls[0]["metadata"]
    assert metadata["request_fingerprint"]
    assert metadata["intent"] == "chat_generic"
    assert metadata["entity_fingerprint"]

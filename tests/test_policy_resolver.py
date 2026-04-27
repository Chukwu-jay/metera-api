import pytest

from app.controlplane.models.policy import EffectivePolicy
from app.controlplane.services.policy_resolver import PolicyResolver
from app.models.domain import ProxyContext


class FakePolicyRepository:
    async def resolve_effective_policy(self, *, tenant_id, workspace_id, environment_id, namespace):
        if tenant_id == "tenant_1" and workspace_id == "workspace_1" and namespace == "faq-billing":
            return EffectivePolicy(
                policy_version_id="policy_123",
                policy_mode="hard",
                dlp_enabled=True,
                dlp_scrub_level="technical",
                semantic_enabled=True,
                semantic_threshold=0.95,
                semantic_shadow_threshold=0.85,
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
        return None


@pytest.mark.asyncio
async def test_policy_resolver_returns_scoped_policy_when_available() -> None:
    resolver = PolicyResolver(repository=FakePolicyRepository())
    settings = type("S", (), {})()
    context = ProxyContext(namespace="faq-billing", tenant_id="tenant_1", workspace_id="workspace_1")

    policy = await resolver.resolve(settings=settings, context=context)

    assert policy.policy_version_id == "policy_123"
    assert policy.policy_mode == "hard"
    assert policy.semantic_threshold == 0.95


@pytest.mark.asyncio
async def test_policy_resolver_falls_back_to_runtime_settings() -> None:
    resolver = PolicyResolver(repository=None)
    settings = type(
        "S",
        (),
        {
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.9,
            "semantic_shadow_threshold": 0.8,
            "semantic_max_temperature": 0.2,
            "identity_guard_enabled": False,
            "identity_strict_mode_enabled": False,
            "identity_partitioning_enabled": False,
            "multimodal_hard_alignment_enabled": False,
            "policy_timing_breakdown_enabled": False,
            "semantic_disabled_namespace_prefixes": "browser-",
            "semantic_high_risk_namespace_prefixes": "faq-billing",
        },
    )()
    context = ProxyContext(namespace="tenant-a")

    policy = await resolver.resolve(settings=settings, context=context)

    assert policy.policy_version_id is None
    assert policy.source_scope == "runtime_default"
    assert policy.semantic_threshold == 0.9
    assert policy.strict_namespace_prefixes == ["browser-"]

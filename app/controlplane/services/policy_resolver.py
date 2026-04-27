from __future__ import annotations

from app.controlplane.models.policy import EffectivePolicy


class PolicyResolver:
    def __init__(self, repository=None) -> None:
        self.repository = repository

    async def inspect(self, *, settings, context) -> EffectivePolicy:
        return await self.resolve(settings=settings, context=context)

    async def resolve(self, *, settings, context) -> EffectivePolicy:
        if self.repository is not None and context.tenant_id and context.workspace_id:
            resolved = await self.repository.resolve_effective_policy(
                tenant_id=context.tenant_id,
                workspace_id=context.workspace_id,
                environment_id=context.environment_id,
                namespace=context.namespace,
            )
            if resolved is not None:
                return resolved
        return EffectivePolicy(
            policy_version_id=None,
            policy_mode="soft",
            dlp_enabled=bool(getattr(settings, "dlp_enabled", True)),
            dlp_scrub_level=getattr(settings, "dlp_scrub_level", "technical"),
            semantic_enabled=bool(getattr(settings, "semantic_enabled", True)),
            semantic_threshold=float(getattr(settings, "semantic_threshold", 0.9)),
            semantic_shadow_threshold=float(getattr(settings, "semantic_shadow_threshold", 0.8)),
            semantic_max_temperature=float(getattr(settings, "semantic_max_temperature", 0.2)),
            identity_guard_enabled=bool(getattr(settings, "identity_guard_enabled", False)),
            identity_strict_mode_enabled=bool(getattr(settings, "identity_strict_mode_enabled", False)),
            identity_partitioning_enabled=bool(getattr(settings, "identity_partitioning_enabled", False)),
            multimodal_hard_alignment_enabled=bool(getattr(settings, "multimodal_hard_alignment_enabled", False)),
            policy_timing_breakdown_enabled=bool(getattr(settings, "policy_timing_breakdown_enabled", False)),
            strict_namespace_prefixes=_split_prefixes(getattr(settings, "semantic_disabled_namespace_prefixes", "")),
            high_risk_namespace_prefixes=_split_prefixes(getattr(settings, "semantic_high_risk_namespace_prefixes", "")),
            source_scope="runtime_default",
            source_ref_id=None,
            extension_fields={},
        )


def _split_prefixes(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]

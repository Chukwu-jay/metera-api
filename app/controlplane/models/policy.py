from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EffectivePolicy:
    policy_version_id: str | None
    policy_mode: str
    dlp_enabled: bool
    dlp_scrub_level: str
    semantic_enabled: bool
    semantic_threshold: float
    semantic_shadow_threshold: float
    semantic_max_temperature: float
    identity_guard_enabled: bool
    identity_strict_mode_enabled: bool
    identity_partitioning_enabled: bool
    multimodal_hard_alignment_enabled: bool
    policy_timing_breakdown_enabled: bool
    strict_namespace_prefixes: list[str] = field(default_factory=list)
    high_risk_namespace_prefixes: list[str] = field(default_factory=list)
    source_scope: str = "runtime_default"
    source_ref_id: str | None = None
    extension_fields: dict[str, Any] = field(default_factory=dict)

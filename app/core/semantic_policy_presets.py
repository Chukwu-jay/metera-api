from __future__ import annotations

from typing import Any, Literal

SemanticHardeningPreset = Literal["conservative", "balanced", "aggressive"]

PRESET_FIELD_NAMES = {
    "semantic_enabled",
    "semantic_threshold",
    "semantic_shadow_threshold",
    "semantic_max_temperature",
}

SEMANTIC_HARDENING_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "label": "Conservative",
        "description": "Safest beta posture: near matches are measured in shadow mode unless reuse is very clearly safe.",
        "settings": {
            "semantic_enabled": True,
            "semantic_threshold": 0.9,
            "semantic_shadow_threshold": 0.8,
            "semantic_max_temperature": 0.2,
        },
    },
    "balanced": {
        "label": "Balanced",
        "description": "Allows more live semantic reuse for ordinary low-risk prompts while preserving shadow measurement below the live threshold.",
        "settings": {
            "semantic_enabled": True,
            "semantic_threshold": 0.86,
            "semantic_shadow_threshold": 0.78,
            "semantic_max_temperature": 0.2,
        },
    },
    "aggressive": {
        "label": "Aggressive",
        "description": "Maximizes reuse and savings for low-risk workloads; use only when the tenant accepts higher wrong-context risk.",
        "settings": {
            "semantic_enabled": True,
            "semantic_threshold": 0.8,
            "semantic_shadow_threshold": 0.72,
            "semantic_max_temperature": 0.4,
        },
    },
}


def preset_names() -> list[str]:
    return list(SEMANTIC_HARDENING_PRESETS)


def preset_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "label": spec["label"],
            "description": spec["description"],
            **spec["settings"],
        }
        for name, spec in SEMANTIC_HARDENING_PRESETS.items()
    ]


def apply_semantic_hardening_preset(updates: dict[str, Any]) -> dict[str, Any]:
    preset = updates.get("semantic_hardening_preset")
    if preset is None:
        return dict(updates)
    if preset not in SEMANTIC_HARDENING_PRESETS:
        raise ValueError(f"Unknown semantic hardening preset: {preset}")
    merged = dict(updates)
    for key, value in SEMANTIC_HARDENING_PRESETS[preset]["settings"].items():
        if merged.get(key) is None:
            merged[key] = value
    return merged


def infer_semantic_hardening_preset(policy: dict[str, Any]) -> str:
    explicit = policy.get("semantic_hardening_preset")
    if explicit in SEMANTIC_HARDENING_PRESETS:
        return str(explicit)
    for name, spec in SEMANTIC_HARDENING_PRESETS.items():
        settings = spec["settings"]
        if all(_same_value(policy.get(key), value) for key, value in settings.items()):
            return name
    return "custom"


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        try:
            return abs(float(left) - float(right)) < 0.000001
        except (TypeError, ValueError):
            return False
    return left == right

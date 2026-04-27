from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(slots=True)
class PostureAssessment:
    profile: str
    strict_startup: bool
    healthy: bool
    ready: bool
    errors: list[str]
    warnings: list[str]
    expected: dict[str, object]
    observed: dict[str, object]


PILOT_REQUIRED_FLAGS: tuple[str, ...] = (
    "controlplane_identity_enabled",
    "controlplane_identity_seed_enabled",
    "request_event_logging_enabled",
    "request_ledger_enabled",
    "risk_event_logging_enabled",
    "shadow_savings_logging_enabled",
    "scoped_policy_enabled",
    "rollups_enabled",
    "billing_prep_enabled",
    "identity_guard_enabled",
    "identity_strict_mode_enabled",
    "identity_partitioning_enabled",
    "multimodal_hard_alignment_enabled",
    "policy_timing_breakdown_enabled",
)


STRICT_PROFILES = {"pilot", "pilot-local", "cloud", "beta", "production", "prod"}


def assess_startup_posture(settings: Settings) -> PostureAssessment:
    profile = settings.deployment_profile.lower().strip()
    strict_startup = settings.strict_startup_validation or profile in STRICT_PROFILES
    errors: list[str] = []
    warnings: list[str] = []

    policy_store_dsn_present = bool(settings.policy_store_dsn or settings.semantic_store_dsn)
    redis_url_present = bool(settings.redis_url)
    semantic_store_backend = settings.semantic_store_backend.lower().strip()
    exact_cache_backend = settings.exact_cache_backend.lower().strip()

    persistent_flags = {
        "request_event_logging_enabled": settings.request_event_logging_enabled,
        "request_ledger_enabled": settings.request_ledger_enabled,
        "risk_event_logging_enabled": settings.risk_event_logging_enabled,
        "shadow_savings_logging_enabled": settings.shadow_savings_logging_enabled,
        "scoped_policy_enabled": settings.scoped_policy_enabled,
        "rollups_enabled": settings.rollups_enabled,
        "billing_prep_enabled": settings.billing_prep_enabled,
    }

    if settings.controlplane_identity_enabled and not policy_store_dsn_present:
        errors.append("controlplane identity is enabled but no policy store DSN is configured")
    if settings.controlplane_identity_seed_enabled and not settings.controlplane_static_api_key:
        errors.append("identity seed is enabled but METERA_CONTROLPLANE_STATIC_API_KEY is missing")
    if any(persistent_flags.values()) and not policy_store_dsn_present:
        enabled_names = sorted(name for name, enabled in persistent_flags.items() if enabled)
        errors.append(
            "persistent control-plane features are enabled without a policy store DSN: " + ", ".join(enabled_names)
        )
    if settings.billing_prep_enabled and not settings.request_ledger_enabled:
        errors.append("billing prep requires request ledger to be enabled")
    if settings.rollups_enabled and not settings.request_ledger_enabled:
        errors.append("rollups require request ledger to be enabled")
    if settings.identity_strict_mode_enabled and not settings.controlplane_identity_enabled:
        errors.append("identity strict mode requires controlplane identity to be enabled")
    if settings.identity_partitioning_enabled and not settings.controlplane_identity_enabled:
        errors.append("identity partitioning requires controlplane identity to be enabled")
    if exact_cache_backend == "redis" and not redis_url_present:
        message = "redis cache backend requested but METERA_REDIS_URL is missing"
        if strict_startup:
            errors.append(message)
        else:
            warnings.append(message)
    if semantic_store_backend == "pgvector" and not settings.semantic_store_dsn:
        message = "pgvector semantic store requested but METERA_SEMANTIC_STORE_DSN is missing"
        if strict_startup:
            errors.append(message)
        else:
            warnings.append(message)

    if profile in STRICT_PROFILES:
        if exact_cache_backend != "redis":
            errors.append(f"{profile} profile requires METERA_EXACT_CACHE_BACKEND=redis")
        if semantic_store_backend != "pgvector":
            errors.append(f"{profile} profile requires METERA_SEMANTIC_STORE_BACKEND=pgvector")
        if not settings.controlplane_static_api_key:
            errors.append(f"{profile} profile requires METERA_CONTROLPLANE_STATIC_API_KEY to be set")
        for flag_name in PILOT_REQUIRED_FLAGS:
            if not bool(getattr(settings, flag_name)):
                errors.append(f"{profile} profile requires METERA_{flag_name.upper()}=true")

    expected = {
        "cache_backend": "redis" if profile in STRICT_PROFILES else exact_cache_backend,
        "semantic_store_backend": "pgvector" if profile in STRICT_PROFILES else semantic_store_backend,
        "policy_store_required": profile in STRICT_PROFILES or any(persistent_flags.values()) or settings.controlplane_identity_enabled,
        "identity_mode": "repository" if profile in STRICT_PROFILES or settings.controlplane_identity_enabled else "disabled_or_static",
        "strict_features_required": profile in STRICT_PROFILES,
    }
    observed = {
        "environment": settings.environment,
        "deployment_profile": settings.deployment_profile,
        "cache_backend": exact_cache_backend,
        "redis_url_present": redis_url_present,
        "semantic_store_backend": semantic_store_backend,
        "semantic_store_dsn_present": bool(settings.semantic_store_dsn),
        "policy_store_dsn_present": policy_store_dsn_present,
        "controlplane_identity_enabled": settings.controlplane_identity_enabled,
        "controlplane_identity_seed_enabled": settings.controlplane_identity_seed_enabled,
        "static_api_key_present": bool(settings.controlplane_static_api_key),
        "request_ledger_enabled": settings.request_ledger_enabled,
        "rollups_enabled": settings.rollups_enabled,
        "billing_prep_enabled": settings.billing_prep_enabled,
    }
    healthy = not errors
    return PostureAssessment(
        profile=profile,
        strict_startup=strict_startup,
        healthy=healthy,
        ready=healthy,
        errors=errors,
        warnings=warnings,
        expected=expected,
        observed=observed,
    )


def evaluate_runtime_readiness(app_state) -> tuple[bool, list[str]]:
    issues: list[str] = []
    posture_errors = list(getattr(app_state, "posture_errors", []))
    if posture_errors:
        issues.extend(posture_errors)
    if getattr(app_state, "cache_fallback_active", False):
        issues.append("exact cache is running on fallback backend")
    if getattr(app_state, "semantic_store_fallback_active", False):
        issues.append("semantic store is running on fallback backend")
    if bool(getattr(app_state, "controlplane_identity_enabled", False)) and getattr(app_state, "identity_mode", None) != "repository":
        issues.append("controlplane identity is enabled but runtime identity mode is not repository")
    return (len(issues) == 0, issues)

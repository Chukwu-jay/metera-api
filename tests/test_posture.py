from app.core.config import Settings
from app.core.posture import assess_startup_posture


def test_pilot_profile_requires_explicit_identity_and_persistence_posture() -> None:
    settings = Settings(
        deployment_profile="pilot-local",
        environment="pilot-local",
        exact_cache_backend="redis",
        redis_url="redis://redis:6379/0",
        semantic_store_backend="pgvector",
        semantic_store_dsn="postgresql://postgres:postgres@pgvector:5432/metera",
        policy_store_dsn="postgresql://postgres:postgres@pgvector:5432/metera",
        controlplane_identity_enabled=True,
        controlplane_identity_seed_enabled=False,
        controlplane_static_api_key=None,
        request_event_logging_enabled=True,
        request_ledger_enabled=True,
        risk_event_logging_enabled=True,
        shadow_savings_logging_enabled=True,
        scoped_policy_enabled=True,
        rollups_enabled=True,
        billing_prep_enabled=True,
        identity_guard_enabled=True,
        identity_strict_mode_enabled=True,
        identity_partitioning_enabled=True,
        multimodal_hard_alignment_enabled=True,
        policy_timing_breakdown_enabled=True,
    )

    assessment = assess_startup_posture(settings)

    assert assessment.strict_startup is True
    assert assessment.healthy is False
    assert any("METERA_CONTROLPLANE_IDENTITY_SEED_ENABLED=true" in error for error in assessment.errors)
    assert any("METERA_CONTROLPLANE_STATIC_API_KEY" in error for error in assessment.errors)


def test_dev_profile_warns_for_redis_without_url_but_does_not_fail() -> None:
    settings = Settings(
        deployment_profile="dev",
        environment="dev",
        exact_cache_backend="redis",
        redis_url=None,
        semantic_store_backend="memory",
    )

    assessment = assess_startup_posture(settings)

    assert assessment.strict_startup is False
    assert assessment.healthy is True
    assert assessment.errors == []
    assert any("METERA_REDIS_URL is missing" in warning for warning in assessment.warnings)

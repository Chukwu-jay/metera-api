from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.cache.exact_cache import ExactCache
from app.controlplane.repositories.billing import PostgresBillingRepository
from app.controlplane.repositories.commercial_events import PostgresCommercialEventRepository
from app.controlplane.repositories.policies import PostgresPolicyRepository
from app.controlplane.repositories.request_events import PostgresRequestEventRepository
from app.controlplane.repositories.request_ledger import PostgresRequestLedgerRepository
from app.controlplane.repositories.risk_events import PostgresRiskEventRepository
from app.controlplane.repositories.rollups import PostgresRollupRepository
from app.controlplane.repositories.shadow_savings import PostgresShadowSavingsRepository
from app.controlplane.services.identity_service import IdentityBootstrapConfig, IdentityService
from app.core.app_services import AppServices
from app.core.config import get_settings
from app.core.policy_state import InMemoryPolicyStore, PostgresPolicyStore
from app.core.posture import assess_startup_posture, evaluate_runtime_readiness
from app.embeddings.local_sentence_transformer import LocalSentenceTransformerEmbedder
from app.observability.metrics import increment
from app.security.secrets import DetectorConfigError, active_detector_names, load_custom_secret_patterns, load_custom_secret_patterns_from_yaml
from app.services.proxy_service import ProxyService
from app.storage.memory import InMemoryKVStore
from app.storage.redis import RedisKVStore, create_redis_client
from app.storage.shadow_analytics import PostgresShadowAnalyticsStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.runtime_settings = settings

    startup_posture = assess_startup_posture(settings)
    app.state.deployment_profile = startup_posture.profile
    app.state.posture_strict_startup = startup_posture.strict_startup
    app.state.posture_errors = list(startup_posture.errors)
    app.state.posture_warnings = list(startup_posture.warnings)
    app.state.posture_expected = dict(startup_posture.expected)
    app.state.posture_observed = dict(startup_posture.observed)
    if startup_posture.errors:
        raise RuntimeError("Metera startup posture validation failed: " + "; ".join(startup_posture.errors))

    json_config = getattr(settings, "dlp_custom_detectors_json", None)
    yaml_path = getattr(settings, "dlp_custom_detectors_yaml_path", None)
    try:
        json_patterns = load_custom_secret_patterns(json_config)
        yaml_patterns = load_custom_secret_patterns_from_yaml(yaml_path)
    except DetectorConfigError as exc:
        raise RuntimeError(f"Metera detector configuration error: {exc}") from exc

    custom_patterns = json_patterns + yaml_patterns
    app.state.active_custom_detectors = active_detector_names(custom_patterns)
    app.state.custom_detector_json_enabled = bool(json_config)
    app.state.custom_detector_yaml_path = yaml_path
    app.state.scrub_mode = "off" if not settings.dlp_enabled else settings.dlp_scrub_level.lower()
    app.state.cache_backend_requested = settings.exact_cache_backend.lower()
    app.state.cache_backend_active = "memory"
    app.state.cache_fallback_active = False
    app.state.cache_warning = None
    app.state.last_redis_fallback_utc = None
    app.state.semantic_store_requested = ProxyService._semantic_store_backend_name(settings)
    app.state.semantic_store_active = "memory"
    app.state.semantic_store_fallback_active = False
    app.state.semantic_store_warning = None
    app.state.last_semantic_store_fallback_utc = None
    app.state.semantic_store = ProxyService._memory_semantic_store
    app.state.policy_store = InMemoryPolicyStore()
    app.state.shadow_analytics_store = None

    semantic_embedder = LocalSentenceTransformerEmbedder(getattr(settings, "semantic_model_name", "sentence-transformers/all-MiniLM-L6-v2"))
    await semantic_embedder.warmup()
    app.state.semantic_embedder = semantic_embedder
    app.state.semantic_model_name = semantic_embedder.model_name
    app.state.semantic_backend = semantic_embedder.backend
    app.state.semantic_fallback_active = semantic_embedder.is_fallback
    app.state.semantic_enabled = getattr(settings, "semantic_enabled", True)
    app.state.semantic_max_temperature = getattr(settings, "semantic_max_temperature", 0.2)

    requested_store, active_store, fallback_active, warning, semantic_store = await ProxyService.initialize_semantic_store(settings)
    app.state.semantic_store_requested = requested_store
    app.state.semantic_store_active = active_store
    app.state.semantic_store_fallback_active = fallback_active
    app.state.semantic_store_warning = warning
    app.state.semantic_store = semantic_store
    if fallback_active:
        app.state.last_semantic_store_fallback_utc = datetime.now(UTC).isoformat()
        increment("semantic_store_backend_fallbacks")
    if active_store == "pgvector":
        increment("semantic_store_backend_pgvector")
    else:
        increment("semantic_store_backend_memory")

    policy_store_dsn = getattr(settings, "policy_store_dsn", None) or getattr(settings, "semantic_store_dsn", None)
    if policy_store_dsn:
        try:
            policy_store = PostgresPolicyStore(policy_store_dsn)
            await policy_store.warmup()
            await policy_store.ensure_default_policy_row(force_production_defaults=False)
            app.state.policy_store = policy_store
            shadow_analytics_store = PostgresShadowAnalyticsStore(policy_store_dsn)
            await shadow_analytics_store.warmup()
            await shadow_analytics_store.purge_expired(retention_days=14)
            app.state.shadow_analytics_store = shadow_analytics_store
            increment("policy_store_backend_postgres")
        except Exception:
            app.state.policy_store = InMemoryPolicyStore()
            app.state.shadow_analytics_store = None
            increment("policy_store_backend_memory")
    else:
        increment("policy_store_backend_memory")

    use_redis = settings.exact_cache_backend.lower() == "redis" and bool(settings.redis_url)
    if use_redis:
        try:
            redis_client = create_redis_client(settings.redis_url)
            await redis_client.ping()
            app.state.redis = redis_client
            app.state.kv_store = RedisKVStore(redis_client)
            app.state.cache_backend_active = "redis"
            increment("cache_backend_redis")
        except Exception as exc:
            app.state.redis = None
            app.state.kv_store = InMemoryKVStore()
            app.state.cache_backend_active = "memory"
            app.state.cache_fallback_active = True
            app.state.last_redis_fallback_utc = datetime.now(UTC).isoformat()
            app.state.cache_warning = f"Redis unavailable, fell back to memory: {exc.__class__.__name__}"
            increment("cache_backend_memory")
            increment("cache_backend_fallbacks")
    else:
        app.state.redis = None
        app.state.kv_store = InMemoryKVStore()
        if settings.exact_cache_backend.lower() == "redis" and not settings.redis_url:
            app.state.cache_fallback_active = True
            app.state.last_redis_fallback_utc = datetime.now(UTC).isoformat()
            app.state.cache_warning = "Redis backend requested but METERA_REDIS_URL is not configured; using memory cache"
            increment("cache_backend_fallbacks")
        increment("cache_backend_memory")

    app.state.exact_cache = ExactCache(app.state.kv_store)

    services = AppServices(
        exact_cache=app.state.exact_cache,
        shadow_analytics_store=app.state.shadow_analytics_store,
        semantic_embedder=app.state.semantic_embedder,
        semantic_store=app.state.semantic_store,
    )
    app.state.services = services

    identity_result = await IdentityService.bootstrap(
        dsn=policy_store_dsn,
        config=IdentityBootstrapConfig(
            enabled=bool(getattr(settings, "controlplane_identity_enabled", False)),
            seed_enabled=bool(getattr(settings, "controlplane_identity_seed_enabled", False)),
            static_api_key=getattr(settings, "controlplane_static_api_key", None),
            tenant_id=getattr(settings, "controlplane_static_tenant_id", "dev-tenant"),
            tenant_slug=getattr(settings, "controlplane_static_tenant_slug", "dev-tenant"),
            workspace_id=getattr(settings, "controlplane_static_workspace_id", "workspace_default"),
            workspace_slug=getattr(settings, "controlplane_static_workspace_slug", "default-workspace"),
            environment_id=getattr(settings, "controlplane_static_environment_id", None),
            environment_name=getattr(settings, "controlplane_static_environment_name", None),
            api_key_id=getattr(settings, "controlplane_static_api_key_id", "mk_dev_default"),
            api_key_prefix=getattr(settings, "controlplane_static_api_key_prefix", "mk_dev"),
            api_key_display_name=getattr(settings, "controlplane_static_api_key_display_name", "Development Key"),
        ),
    )
    app.state.controlplane_identity_enabled = bool(getattr(settings, "controlplane_identity_enabled", False))
    app.state.identity_mode = identity_result.mode
    app.state.identity_repository = identity_result.repository
    app.state.identity_resolver = identity_result.resolver
    services.identity_repository = identity_result.repository
    services.identity_resolver = identity_result.resolver

    if policy_store_dsn and bool(getattr(settings, "scoped_policy_enabled", False)):
        policy_repository = PostgresPolicyRepository(policy_store_dsn)
        await policy_repository.warmup()
        await policy_repository.ensure_global_policy(
            defaults={
                "dlp_enabled": bool(getattr(settings, "dlp_enabled", True)),
                "dlp_scrub_level": getattr(settings, "dlp_scrub_level", "technical"),
                "semantic_enabled": bool(getattr(settings, "semantic_enabled", True)),
                "semantic_threshold": float(getattr(settings, "semantic_threshold", 0.9)),
                "semantic_shadow_threshold": float(getattr(settings, "semantic_shadow_threshold", 0.8)),
                "semantic_max_temperature": float(getattr(settings, "semantic_max_temperature", 0.2)),
                "identity_guard_enabled": bool(getattr(settings, "identity_guard_enabled", False)),
                "identity_strict_mode_enabled": bool(getattr(settings, "identity_strict_mode_enabled", False)),
                "identity_partitioning_enabled": bool(getattr(settings, "identity_partitioning_enabled", False)),
                "multimodal_hard_alignment_enabled": bool(getattr(settings, "multimodal_hard_alignment_enabled", False)),
                "policy_timing_breakdown_enabled": bool(getattr(settings, "policy_timing_breakdown_enabled", False)),
                "strict_namespace_prefixes": [item.strip() for item in getattr(settings, "semantic_disabled_namespace_prefixes", "").split(",") if item.strip()],
                "high_risk_namespace_prefixes": [item.strip() for item in getattr(settings, "semantic_high_risk_namespace_prefixes", "").split(",") if item.strip()],
            }
        )
        app.state.policy_repository = policy_repository
        services.policy_repository = policy_repository

    if policy_store_dsn and bool(getattr(settings, "request_event_logging_enabled", False)):
        request_event_repository = PostgresRequestEventRepository(policy_store_dsn)
        await request_event_repository.warmup()
        app.state.request_event_repository = request_event_repository
        services.request_event_repository = request_event_repository

    if policy_store_dsn and bool(getattr(settings, "request_ledger_enabled", False)):
        request_ledger_repository = PostgresRequestLedgerRepository(policy_store_dsn)
        await request_ledger_repository.warmup()
        app.state.request_ledger_repository = request_ledger_repository
        services.request_ledger_repository = request_ledger_repository

    if policy_store_dsn and bool(getattr(settings, "risk_event_logging_enabled", False)):
        risk_event_repository = PostgresRiskEventRepository(policy_store_dsn)
        await risk_event_repository.warmup()
        app.state.risk_event_repository = risk_event_repository
        services.risk_event_repository = risk_event_repository

    if policy_store_dsn and bool(getattr(settings, "shadow_savings_logging_enabled", False)):
        shadow_savings_repository = PostgresShadowSavingsRepository(policy_store_dsn)
        await shadow_savings_repository.warmup()
        app.state.shadow_savings_repository = shadow_savings_repository
        services.shadow_savings_repository = shadow_savings_repository

    if policy_store_dsn and bool(getattr(settings, "rollups_enabled", False)):
        rollup_repository = PostgresRollupRepository(policy_store_dsn)
        await rollup_repository.warmup()
        app.state.rollup_repository = rollup_repository
        services.rollup_repository = rollup_repository

    if policy_store_dsn and bool(getattr(settings, "billing_prep_enabled", False)):
        billing_repository = PostgresBillingRepository(
            policy_store_dsn,
            patronage_required_threshold_usd=float(getattr(settings, "billing_patronage_threshold_usd", 50.0) or 50.0),
        )
        await billing_repository.warmup()
        commercial_event_repository = PostgresCommercialEventRepository(policy_store_dsn)
        await commercial_event_repository.warmup()
        app.state.billing_repository = billing_repository
        app.state.commercial_event_repository = commercial_event_repository
        services.billing_repository = billing_repository
        services.commercial_event_repository = commercial_event_repository

    yield

    redis = getattr(app.state, "redis", None)
    if redis is not None:
        await redis.aclose()

    for attr in [
        "semantic_store",
        "policy_store",
        "shadow_analytics_store",
        "identity_repository",
        "policy_repository",
        "request_event_repository",
        "request_ledger_repository",
        "risk_event_repository",
        "shadow_savings_repository",
        "rollup_repository",
        "billing_repository",
        "commercial_event_repository",
    ]:
        resource = getattr(app.state, attr, None)
        if resource is not None and hasattr(resource, "close"):
            await resource.close()

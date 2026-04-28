from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Metera"
    environment: str = "dev"
    upstream_base_url: str = "https://api.openai.com"
    upstream_api_key: str | None = None
    upstream_timeout_seconds: float = 60.0
    upstream_max_retries: int = 1
    redis_url: str | None = None
    exact_cache_backend: str = "memory"
    dlp_enabled: bool = True
    dlp_analyzer_mode: str = "auto"
    dlp_scrub_level: str = "technical"
    dlp_detect_email: bool | None = None
    dlp_detect_phone: bool | None = None
    dlp_detect_ip: bool | None = None
    dlp_detect_secrets: bool | None = None
    dlp_custom_detectors_json: str | None = None
    dlp_custom_detectors_yaml_path: str | None = None
    semantic_enabled: bool = True
    semantic_store_backend: str = "memory"
    semantic_store_dsn: str | None = None
    semantic_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_threshold: float = 0.9
    semantic_shadow_threshold: float = 0.8
    semantic_max_temperature: float = 0.2
    default_exact_ttl_seconds: int = 3600
    default_semantic_ttl_seconds: int = 86400
    namespace_header: str = "x-metera-namespace"
    provider_auth_header: str = "authorization"
    admin_api_key: str | None = None
    policy_store_dsn: str | None = None
    deployment_profile: str = "dev"
    strict_startup_validation: bool = False
    dual_mode_enabled: bool = False
    semantic_store_backend: str = "memory"
    semantic_disabled_namespace_prefixes: str = ""
    semantic_high_risk_namespace_prefixes: str = ""
    controlplane_identity_enabled: bool = False
    controlplane_identity_seed_enabled: bool = False
    controlplane_static_api_key: str | None = None
    controlplane_static_tenant_id: str = "tenant_dev"
    controlplane_static_tenant_slug: str = "dev-tenant"
    controlplane_static_workspace_id: str = "workspace_default"
    controlplane_static_workspace_slug: str = "workspace-default"
    controlplane_static_environment_id: str | None = None
    controlplane_static_environment_name: str | None = None
    controlplane_static_api_key_id: str = "mk_dev_default"
    controlplane_static_api_key_prefix: str = "mk_dev"
    controlplane_static_api_key_display_name: str = "Development Key"
    request_event_logging_enabled: bool = False
    request_ledger_enabled: bool = False
    risk_event_logging_enabled: bool = False
    shadow_savings_logging_enabled: bool = False
    scoped_policy_enabled: bool = False
    rollups_enabled: bool = False
    billing_prep_enabled: bool = False
    billing_patronage_threshold_usd: float = 50.0
    identity_guard_enabled: bool = False
    identity_strict_mode_enabled: bool = False
    identity_partitioning_enabled: bool = False
    multimodal_hard_alignment_enabled: bool = False
    policy_timing_breakdown_enabled: bool = False
    tenant_query_param_fallback_enabled: bool = False

    model_config = SettingsConfigDict(env_prefix="METERA_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

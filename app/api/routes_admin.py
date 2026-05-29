from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.cache.exact_cache import ExactCache
from app.core.config import Settings, get_settings
from app.core.dependencies import get_exact_cache, require_admin
from app.core.policy_state import get_policy_state, update_policy_state
from app.core.semantic_policy_presets import apply_semantic_hardening_preset, infer_semantic_hardening_preset, preset_catalog
from app.models.api import (
    CacheInvalidationRequest,
    CacheInvalidationResponse,
    DetectorDryRunRequest,
    DetectorDryRunResponse,
    PolicySettingsResponse,
    PolicyUpdateRequest,
)
from app.security.namespace import resolve_namespace, validate_namespace
from app.services.proxy_service import ProxyService, build_dlp_policy_from_settings, run_detector_dry_run

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/policy", response_model=PolicySettingsResponse)
async def get_policy(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> PolicySettingsResponse:
    overrides = await get_policy_state(request.app)
    resolved = _resolve_policy(settings, overrides)
    return PolicySettingsResponse(
        **resolved,
        overrides_active={key: value is not None for key, value in overrides.items()},
    )


@router.post("/policy", response_model=PolicySettingsResponse)
async def update_policy(
    payload: PolicyUpdateRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> PolicySettingsResponse:
    updates = apply_semantic_hardening_preset(payload.model_dump())
    overrides = await update_policy_state(request.app, updates)
    resolved = _resolve_policy(settings, overrides)
    return PolicySettingsResponse(
        **resolved,
        overrides_active={key: value is not None for key, value in overrides.items()},
    )


@router.post("/detectors/dry-run", response_model=DetectorDryRunResponse)
def detector_dry_run(
    request: DetectorDryRunRequest,
    settings: Settings = Depends(get_settings),
) -> DetectorDryRunResponse:
    policy = build_dlp_policy_from_settings(settings)
    return run_detector_dry_run(text=request.text, policy=policy)


@router.post("/cache/invalidate", response_model=CacheInvalidationResponse)
async def invalidate_cache(
    request: CacheInvalidationRequest,
    namespace_header: str | None = Header(default=None, alias="x-metera-namespace"),
    settings: Settings = Depends(get_settings),
    exact_cache: ExactCache = Depends(get_exact_cache),
) -> CacheInvalidationResponse:
    header_namespace = resolve_namespace(namespace_header, settings.namespace_header)
    target_namespace = request.namespace or header_namespace
    validate_namespace(target_namespace, configured_header_name=settings.namespace_header)
    if target_namespace != header_namespace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin invalidation cannot target a different namespace than the authenticated header context",
        )
    service = ProxyService(settings=settings, exact_cache=exact_cache)
    exact_deleted, semantic_deleted = await service.invalidate_namespace(target_namespace)
    return CacheInvalidationResponse(
        namespace=target_namespace,
        exact_cache_deleted=exact_deleted,
        semantic_cache_deleted=semantic_deleted,
    )


def _resolve_policy(settings: Settings, overrides: dict) -> dict:
    resolved = {
        "dlp_enabled": overrides.get("dlp_enabled") if overrides.get("dlp_enabled") is not None else getattr(settings, "dlp_enabled", True),
        "dlp_scrub_level": overrides.get("dlp_scrub_level") or getattr(settings, "dlp_scrub_level", "technical"),
        "semantic_enabled": overrides.get("semantic_enabled") if overrides.get("semantic_enabled") is not None else getattr(settings, "semantic_enabled", True),
        "semantic_hardening_preset": overrides.get("semantic_hardening_preset"),
        "semantic_threshold": overrides.get("semantic_threshold") if overrides.get("semantic_threshold") is not None else getattr(settings, "semantic_threshold", 0.9),
        "semantic_shadow_threshold": overrides.get("semantic_shadow_threshold") if overrides.get("semantic_shadow_threshold") is not None else getattr(settings, "semantic_shadow_threshold", 0.8),
        "semantic_max_temperature": overrides.get("semantic_max_temperature") if overrides.get("semantic_max_temperature") is not None else getattr(settings, "semantic_max_temperature", 0.2),
    }
    resolved["semantic_hardening_preset"] = infer_semantic_hardening_preset(resolved)
    resolved["semantic_hardening_presets"] = preset_catalog()
    return resolved

from fastapi import Depends, Header, Request

from app.cache.exact_cache import ExactCache
from app.cache.semantic_cache import SemanticCache
from app.core.app_services import get_app_services
from app.core.auth import require_admin_api_key
from app.core.config import Settings, get_settings
from app.core.policy_state import get_policy_state
from app.services.proxy_service import ProxyService


def get_exact_cache(request: Request) -> ExactCache:
    return request.app.state.exact_cache


async def get_proxy_service(
    request: Request,
    settings: Settings = Depends(get_settings),
    exact_cache: ExactCache = Depends(get_exact_cache),
) -> ProxyService:
    policy_overrides = await get_policy_state(request.app)
    semantic_cache = SemanticCache(
        embedder=request.app.state.semantic_embedder,
        store=request.app.state.semantic_store,
        similarity_threshold=policy_overrides.get("semantic_threshold") if policy_overrides.get("semantic_threshold") is not None else settings.semantic_threshold,
        ttl_seconds=settings.default_semantic_ttl_seconds,
    )
    services = get_app_services(request.app)
    return ProxyService(
        settings=settings,
        exact_cache=exact_cache,
        semantic_cache=semantic_cache,
        shadow_analytics_store=getattr(request.app.state, "shadow_analytics_store", None),
        policy_overrides=policy_overrides,
        request_event_repository=services.request_event_repository,
        request_ledger_repository=services.request_ledger_repository,
        risk_event_repository=services.risk_event_repository,
        shadow_savings_repository=services.shadow_savings_repository,
        billing_repository=services.billing_repository,
        commercial_event_repository=services.commercial_event_repository,
    )


async def require_admin(
    settings: Settings = Depends(get_settings),
    x_metera_admin_key: str | None = Header(default=None, alias="x-metera-admin-key"),
    authorization: str | None = Header(default=None),
) -> None:
    await require_admin_api_key(settings.admin_api_key, x_metera_admin_key, authorization)

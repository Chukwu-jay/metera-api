from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.tenant_authorization import capabilities_for_role, derive_tenant_role, normalize_tenant_capabilities


@dataclass(slots=True)
class TenantAccessScope:
    tenant_id: str
    source: str
    role: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)


def resolve_tenant_access_scope(request: Request, requested_tenant_id: str | None = None) -> TenantAccessScope:
    proxy_context = getattr(request.state, "proxy_context", None)
    context_tenant_id = getattr(proxy_context, "tenant_id", None) if proxy_context is not None else None

    if context_tenant_id:
        if requested_tenant_id and requested_tenant_id != context_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requested tenant does not match authenticated tenant scope",
            )
        context_role = getattr(proxy_context, "tenant_role", None) if proxy_context is not None else None
        context_capabilities = tuple(getattr(proxy_context, "tenant_capabilities", ()) or ()) if proxy_context is not None else ()
        derived_role = derive_tenant_role(tenant_role=context_role, tenant_capabilities=context_capabilities)
        capabilities = normalize_tenant_capabilities(role=derived_role, tenant_capabilities=context_capabilities)
        return TenantAccessScope(tenant_id=context_tenant_id, source="proxy_context", role=derived_role, capabilities=capabilities)

    settings = getattr(request.app.state, "runtime_settings", None) or get_settings()
    fallback_enabled = getattr(settings, "effective_tenant_query_param_fallback_enabled", None)
    if fallback_enabled is None:
        fallback_enabled = bool(getattr(settings, "tenant_query_param_fallback_enabled", False))
    if requested_tenant_id:
        if not fallback_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant query parameter fallback is disabled; authenticated tenant scope is required",
            )
        fallback_role = "tenant_reader"
        return TenantAccessScope(
            tenant_id=requested_tenant_id,
            source="query_param_fallback",
            role=fallback_role,
            capabilities=normalize_tenant_capabilities(role=fallback_role, tenant_capabilities=()),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Tenant scope is required",
    )

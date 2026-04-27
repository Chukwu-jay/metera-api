from __future__ import annotations

from fastapi import HTTPException, status

ROLE_CAPABILITIES: dict[str, set[str]] = {
    "tenant_admin": {"billing:read", "billing:history:read", "billing:scope:read", "billing:adjustments:read"},
    "tenant_reader": {"billing:read", "billing:scope:read"},
}


def capabilities_for_role(role: str | None) -> set[str]:
    if role is None:
        return set()
    return set(ROLE_CAPABILITIES.get(role, set()))


def normalize_tenant_capabilities(
    *,
    role: str | None,
    tenant_capabilities: tuple[str, ...] | list[str] | set[str] | None,
) -> tuple[str, ...]:
    explicit_capabilities = {str(item).strip() for item in (tenant_capabilities or ()) if str(item).strip()}
    effective_capabilities = capabilities_for_role(role) | explicit_capabilities
    return tuple(sorted(effective_capabilities))


def derive_tenant_role(*, tenant_role: str | None, tenant_capabilities: tuple[str, ...] | list[str] | set[str] | None) -> str:
    if tenant_role in ROLE_CAPABILITIES:
        return str(tenant_role)
    capability_set = {str(item) for item in (tenant_capabilities or ()) if str(item).strip()}
    if capability_set:
        if capability_set.issuperset(ROLE_CAPABILITIES["tenant_admin"]):
            return "tenant_admin"
        if capability_set.issuperset(ROLE_CAPABILITIES["tenant_reader"]):
            return "tenant_reader"
    if tenant_role:
        return str(tenant_role)
    return "tenant_admin"


def require_tenant_capability(scope, capability: str) -> None:
    allowed = set(scope.capabilities) if scope.capabilities else set(normalize_tenant_capabilities(role=scope.role, tenant_capabilities=()))
    if capability not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant role '{scope.role}' is not allowed to perform '{capability}'",
        )

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.app_services import get_app_services
from app.core.config import Settings, get_settings
from app.core.dependencies import require_admin
from app.models.api import (
    EffectivePolicyInspectResponse,
    NamespacePolicyOverrideRequest,
    NamespacePolicyOverrideResponse,
    NamespacePolicyOverrideSummary,
    PolicyAssignmentRequest,
    PolicyAssignmentResponse,
    PolicyAssignmentSummary,
    PolicyChangeLogSummary,
    PolicySettingsResponse,
    PolicyUpdateRequest,
    PolicyVersionSummary,
    ScopedPolicyVersionCreateRequest,
    ScopedPolicyVersionResponse,
)

router = APIRouter(prefix="/admin", tags=["admin-policy"], dependencies=[Depends(require_admin)])


@router.get("/policy", response_model=PolicySettingsResponse)
async def get_policy(request: Request, settings: Settings = Depends(get_settings)) -> PolicySettingsResponse:
    from app.core.policy_state import get_policy_state

    overrides = await get_policy_state(request.app)
    resolved = _resolve_policy(settings, overrides)
    services = get_app_services(request.app)
    policy_repository = services.policy_repository
    if policy_repository is not None:
        resolver = _get_policy_resolver(request)
        effective = await resolver.inspect(
            settings=settings,
            context=type("PolicyContext", (), {"tenant_id": None, "workspace_id": None, "environment_id": None, "namespace": "default"})(),
        )
        resolved = {
            "dlp_enabled": effective.dlp_enabled,
            "dlp_scrub_level": effective.dlp_scrub_level,
            "semantic_enabled": effective.semantic_enabled,
            "semantic_threshold": effective.semantic_threshold,
            "semantic_shadow_threshold": effective.semantic_shadow_threshold,
            "semantic_max_temperature": effective.semantic_max_temperature,
        }
    return PolicySettingsResponse(**resolved, overrides_active={key: value is not None for key, value in overrides.items()})


@router.post("/policy", response_model=PolicySettingsResponse)
async def update_policy(payload: PolicyUpdateRequest, request: Request, settings: Settings = Depends(get_settings)) -> PolicySettingsResponse:
    from app.core.policy_state import update_policy_state

    updates = payload.model_dump()
    overrides = await update_policy_state(request.app, updates)
    resolved = _resolve_policy(settings, overrides)
    return PolicySettingsResponse(**resolved, overrides_active={key: value is not None for key, value in overrides.items()})


@router.get("/control/policy/versions", response_model=list[PolicyVersionSummary])
async def list_policy_versions(request: Request, scope_type: str | None = None, scope_ref_id: str | None = None) -> list[PolicyVersionSummary]:
    repository = _require_policy_repository(request)
    rows = await repository.list_policy_versions(scope_type=scope_type, scope_ref_id=scope_ref_id)
    return [
        PolicyVersionSummary(
            id=row["id"],
            scope_type=row["scope_type"],
            scope_ref_id=row.get("scope_ref_id"),
            version_number=int(row["version_number"]),
            semantic_threshold=float(row["semantic_threshold"]),
            semantic_shadow_threshold=float(row["semantic_shadow_threshold"]),
            semantic_max_temperature=float(row["semantic_max_temperature"]),
            created_by=row.get("created_by"),
            change_reason=row.get("change_reason"),
        )
        for row in rows
    ]


@router.post("/control/policy/versions", response_model=ScopedPolicyVersionResponse)
async def create_policy_version(payload: ScopedPolicyVersionCreateRequest, request: Request) -> ScopedPolicyVersionResponse:
    repository = _require_policy_repository(request)
    policy_version_id = await repository.create_policy_version(
        scope_type=payload.scope_type,
        scope_ref_id=payload.scope_ref_id,
        policy=payload.model_dump(exclude={"scope_type", "scope_ref_id", "change_reason"}),
        created_by="admin_api",
        change_reason=payload.change_reason,
    )
    return ScopedPolicyVersionResponse(policy_version_id=policy_version_id)


@router.get("/control/policy/assignments", response_model=list[PolicyAssignmentSummary])
async def list_policy_assignments(request: Request) -> list[PolicyAssignmentSummary]:
    repository = _require_policy_repository(request)
    rows = await repository.list_policy_assignments()
    return [
        PolicyAssignmentSummary(
            id=row["id"],
            scope_type=row["scope_type"],
            policy_version_id=row["policy_version_id"],
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            environment_id=row.get("environment_id"),
            status=row["status"],
        )
        for row in rows
    ]


@router.post("/control/policy/assignments", response_model=PolicyAssignmentResponse)
async def assign_policy(payload: PolicyAssignmentRequest, request: Request) -> PolicyAssignmentResponse:
    repository = _require_policy_repository(request)
    assignment_id = await repository.assign_policy(
        scope_type=payload.scope_type,
        policy_version_id=payload.policy_version_id,
        tenant_id=payload.tenant_id,
        workspace_id=payload.workspace_id,
        environment_id=payload.environment_id,
        actor_id="admin_api",
        change_reason=payload.change_reason,
    )
    return PolicyAssignmentResponse(assignment_id=assignment_id)


@router.get("/control/policy/namespace-overrides", response_model=list[NamespacePolicyOverrideSummary])
async def list_namespace_overrides(request: Request, workspace_id: str | None = None) -> list[NamespacePolicyOverrideSummary]:
    repository = _require_policy_repository(request)
    rows = await repository.list_namespace_overrides(workspace_id=workspace_id)
    return [
        NamespacePolicyOverrideSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            environment_id=row.get("environment_id"),
            namespace=row["namespace"],
            policy_version_id=row["policy_version_id"],
            status=row["status"],
        )
        for row in rows
    ]


@router.post("/control/policy/namespace-overrides", response_model=NamespacePolicyOverrideResponse)
async def set_namespace_override(payload: NamespacePolicyOverrideRequest, request: Request) -> NamespacePolicyOverrideResponse:
    repository = _require_policy_repository(request)
    override_id = await repository.set_namespace_override(
        tenant_id=payload.tenant_id,
        workspace_id=payload.workspace_id,
        environment_id=payload.environment_id,
        namespace=payload.namespace,
        policy_version_id=payload.policy_version_id,
        actor_id="admin_api",
        change_reason=payload.change_reason,
    )
    return NamespacePolicyOverrideResponse(override_id=override_id)


@router.get("/control/policy/change-log", response_model=list[PolicyChangeLogSummary])
async def list_policy_change_log(request: Request, limit: int = 100) -> list[PolicyChangeLogSummary]:
    repository = _require_policy_repository(request)
    rows = await repository.list_policy_change_log(limit=limit)
    return [
        PolicyChangeLogSummary(
            id=row["id"],
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            namespace=row.get("namespace"),
            previous_policy_version_id=row.get("previous_policy_version_id"),
            new_policy_version_id=row["new_policy_version_id"],
            change_actor_type=row["change_actor_type"],
            change_actor_id=row.get("change_actor_id"),
            change_reason=row.get("change_reason"),
            source=row["source"],
        )
        for row in rows
    ]


@router.get("/control/policy/effective", response_model=EffectivePolicyInspectResponse)
async def inspect_effective_policy(
    request: Request,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    environment_id: str | None = None,
    namespace: str = "default",
    settings: Settings = Depends(get_settings),
) -> EffectivePolicyInspectResponse:
    context = type(
        "PolicyContext",
        (),
        {
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "environment_id": environment_id,
            "namespace": namespace,
        },
    )()
    resolver = _get_policy_resolver(request)
    effective = await resolver.inspect(settings=settings, context=context)
    return EffectivePolicyInspectResponse(
        policy_version_id=effective.policy_version_id,
        policy_mode=effective.policy_mode,
        source_scope=effective.source_scope,
        source_ref_id=effective.source_ref_id,
        dlp_enabled=effective.dlp_enabled,
        dlp_scrub_level=effective.dlp_scrub_level,
        semantic_enabled=effective.semantic_enabled,
        semantic_threshold=effective.semantic_threshold,
        semantic_shadow_threshold=effective.semantic_shadow_threshold,
        semantic_max_temperature=effective.semantic_max_temperature,
        strict_namespace_prefixes=effective.strict_namespace_prefixes,
        high_risk_namespace_prefixes=effective.high_risk_namespace_prefixes,
    )


def _resolve_policy(settings: Settings, overrides: dict) -> dict:
    return {
        "dlp_enabled": overrides.get("dlp_enabled") if overrides.get("dlp_enabled") is not None else settings.dlp_enabled,
        "dlp_scrub_level": overrides.get("dlp_scrub_level") or settings.dlp_scrub_level,
        "semantic_enabled": overrides.get("semantic_enabled") if overrides.get("semantic_enabled") is not None else settings.semantic_enabled,
        "semantic_threshold": overrides.get("semantic_threshold") if overrides.get("semantic_threshold") is not None else settings.semantic_threshold,
        "semantic_shadow_threshold": overrides.get("semantic_shadow_threshold") if overrides.get("semantic_shadow_threshold") is not None else settings.semantic_shadow_threshold,
        "semantic_max_temperature": overrides.get("semantic_max_temperature") if overrides.get("semantic_max_temperature") is not None else settings.semantic_max_temperature,
    }


def _require_policy_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.policy_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Policy repository is not available")
    return repository


def _get_policy_resolver(request: Request):
    from app.controlplane.services.policy_resolver import PolicyResolver

    services = get_app_services(request.app)
    return PolicyResolver(repository=services.policy_repository)

# Admin Bootstrap Identity Routes — 2026-04-25

This is a **paste-ready route implementation** for `app/api/routes_identity_admin.py`.

It includes:
- the 3 primitive bootstrap routes
- the convenience bootstrap route
- correct model imports
- explicit admin-only protection via the router dependency
- explicit repository error mapping to HTTP responses

---

## Paste-ready file body

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.controlplane.repositories.api_keys import (
    IdentityConflictError,
    IdentityNotFoundError,
    IdentityValidationError,
)
from app.core.dependencies import require_admin
from app.models.api import (
    ApiKeyIssueRequest,
    ApiKeyIssueResponse,
    ApiKeyRevocationResponse,
    ApiKeySummary,
    BootstrapUsageResponse,
    IdentityStatusResponse,
    TenantCreateRequest,
    TenantEnvironmentBootstrapRequest,
    TenantEnvironmentBootstrapResponse,
    TenantSummary,
    WorkspaceCreateRequest,
    WorkspaceSummary,
)

router = APIRouter(prefix="/admin", tags=["admin-identity"], dependencies=[Depends(require_admin)])


@router.get("/identity/status", response_model=IdentityStatusResponse)
async def identity_status(request: Request) -> IdentityStatusResponse:
    services = getattr(request.app.state, "services", None)
    identity_repository = getattr(services, "identity_repository", None) if services is not None else getattr(request.app.state, "identity_repository", None)
    identity_resolver = getattr(services, "identity_resolver", None) if services is not None else getattr(request.app.state, "identity_resolver", None)
    return IdentityStatusResponse(
        identity_enabled=bool(getattr(request.app.state, "controlplane_identity_enabled", False)),
        identity_mode=str(getattr(request.app.state, "identity_mode", "disabled") or "disabled"),
        repository_available=identity_repository is not None,
        resolver_configured=identity_resolver is not None,
    )


@router.get("/control/tenants", response_model=list[TenantSummary])
async def list_tenants(request: Request) -> list[TenantSummary]:
    repository = _require_identity_repository(request)
    rows = await repository.list_tenants()
    return [TenantSummary(id=row["id"], slug=row["slug"], name=row["name"], status=row["status"]) for row in rows]


@router.post("/control/tenants", response_model=TenantSummary, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreateRequest, request: Request) -> TenantSummary:
    repository = _require_identity_repository(request)
    try:
        row = await repository.create_tenant(
            slug=payload.slug,
            name=payload.name,
            metadata=payload.metadata,
        )
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TenantSummary(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        status=row["status"],
    )


@router.get("/control/workspaces", response_model=list[WorkspaceSummary])
async def list_workspaces(request: Request, tenant_id: str | None = None) -> list[WorkspaceSummary]:
    repository = _require_identity_repository(request)
    rows = await repository.list_workspaces(tenant_id=tenant_id)
    return [
        WorkspaceSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            slug=row["slug"],
            name=row["name"],
            status=row["status"],
            default_environment_id=row.get("default_environment_id"),
        )
        for row in rows
    ]


@router.post("/control/workspaces", response_model=WorkspaceSummary, status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreateRequest, request: Request) -> WorkspaceSummary:
    repository = _require_identity_repository(request)
    try:
        row = await repository.create_workspace(
            tenant_id=payload.tenant_id,
            slug=payload.slug,
            name=payload.name,
            metadata=payload.metadata,
        )
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return WorkspaceSummary(
        id=row["id"],
        tenant_id=row["tenant_id"],
        slug=row["slug"],
        name=row["name"],
        status=row["status"],
        default_environment_id=row.get("default_environment_id"),
    )


@router.get("/control/api-keys", response_model=list[ApiKeySummary])
async def list_api_keys(request: Request, workspace_id: str | None = None) -> list[ApiKeySummary]:
    repository = _require_identity_repository(request)
    rows = await repository.list_api_keys(workspace_id=workspace_id)
    return [
        ApiKeySummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            environment_id=row.get("environment_id"),
            key_prefix=row["key_prefix"],
            display_name=row["display_name"],
            status=row["status"],
            revoked_at=row.get("revoked_at").isoformat() if row.get("revoked_at") else None,
        )
        for row in rows
    ]


@router.post("/control/api-keys", response_model=ApiKeyIssueResponse, status_code=status.HTTP_201_CREATED)
async def issue_api_key(payload: ApiKeyIssueRequest, request: Request) -> ApiKeyIssueResponse:
    repository = _require_identity_repository(request)
    try:
        row = await repository.issue_api_key(
            tenant_id=payload.tenant_id,
            workspace_id=payload.workspace_id,
            display_name=payload.display_name,
            tenant_role=payload.tenant_role,
            tenant_capabilities=payload.tenant_capabilities,
            environment_id=payload.environment_id,
            metadata=payload.metadata,
            actor_id="admin_api",
        )
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ApiKeyIssueResponse(
        id=row["id"],
        tenant_id=row["tenant_id"],
        workspace_id=row["workspace_id"],
        environment_id=row.get("environment_id"),
        key_prefix=row["key_prefix"],
        display_name=row["display_name"],
        status=row["status"],
        plaintext_api_key=row["plaintext_api_key"],
        tenant_role=row["tenant_role"],
        tenant_capabilities=list(row["tenant_capabilities"]),
    )


@router.post(
    "/control/bootstrap/tenant-environment",
    response_model=TenantEnvironmentBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bootstrap_tenant_environment(
    payload: TenantEnvironmentBootstrapRequest,
    request: Request,
) -> TenantEnvironmentBootstrapResponse:
    repository = _require_identity_repository(request)

    combined_metadata = {
        "source": "beta_onboarding",
        "tenant": payload.tenant.metadata,
        "workspace": payload.workspace.metadata,
        "api_key": payload.api_key.metadata,
    }

    try:
        result = await repository.bootstrap_tenant_environment(
            tenant_slug=payload.tenant.slug,
            tenant_name=payload.tenant.name,
            workspace_slug=payload.workspace.slug,
            workspace_name=payload.workspace.name,
            api_key_display_name=payload.api_key.display_name,
            tenant_role=payload.api_key.tenant_role,
            tenant_capabilities=payload.api_key.tenant_capabilities,
            metadata=combined_metadata,
            actor_id="admin_api",
        )
    except IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IdentityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    tenant = result["tenant"]
    workspace = result["workspace"]
    api_key = result["api_key"]
    recommended_namespace = f"{tenant['slug']}-{workspace['slug']}"

    return TenantEnvironmentBootstrapResponse(
        tenant=TenantSummary(
            id=tenant["id"],
            slug=tenant["slug"],
            name=tenant["name"],
            status=tenant["status"],
        ),
        workspace=WorkspaceSummary(
            id=workspace["id"],
            tenant_id=workspace["tenant_id"],
            slug=workspace["slug"],
            name=workspace["name"],
            status=workspace["status"],
            default_environment_id=workspace.get("default_environment_id"),
        ),
        api_key=ApiKeyIssueResponse(
            id=api_key["id"],
            tenant_id=api_key["tenant_id"],
            workspace_id=api_key["workspace_id"],
            environment_id=api_key.get("environment_id"),
            key_prefix=api_key["key_prefix"],
            display_name=api_key["display_name"],
            status=api_key["status"],
            plaintext_api_key=api_key["plaintext_api_key"],
            tenant_role=api_key["tenant_role"],
            tenant_capabilities=list(api_key["tenant_capabilities"]),
        ),
        bootstrap=BootstrapUsageResponse(
            namespace_header="x-metera-namespace",
            recommended_namespace=recommended_namespace,
            chat_completions_url="/v1/chat/completions",
        ),
    )


@router.post("/control/api-keys/{api_key_id}/revoke", response_model=ApiKeyRevocationResponse)
async def revoke_api_key(api_key_id: str, request: Request) -> ApiKeyRevocationResponse:
    repository = _require_identity_repository(request)
    revoked = await repository.revoke_api_key(api_key_id=api_key_id, actor_id="admin_api")
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return ApiKeyRevocationResponse(api_key_id=api_key_id, revoked=True)


def _require_identity_repository(request: Request):
    services = getattr(request.app.state, "services", None)
    repository = getattr(services, "identity_repository", None) if services is not None else getattr(request.app.state, "identity_repository", None)
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Identity repository is not available")
    return repository
```

---

## Why the authorization wiring is correct

All routes in this module are protected by:

```python
router = APIRouter(prefix="/admin", tags=["admin-identity"], dependencies=[Depends(require_admin)])
```

That means every route shown above is admin-only through the existing `require_admin` dependency.

So yes: the new primitive routes and the convenience bootstrap route inherit the same admin gate as the existing identity routes.

---

## Route-to-model wiring summary

### Primitive routes
- `POST /admin/control/tenants`
  - request: `TenantCreateRequest`
  - response: `TenantSummary`

- `POST /admin/control/workspaces`
  - request: `WorkspaceCreateRequest`
  - response: `WorkspaceSummary`

- `POST /admin/control/api-keys`
  - request: `ApiKeyIssueRequest`
  - response: `ApiKeyIssueResponse`

### Convenience route
- `POST /admin/control/bootstrap/tenant-environment`
  - request: `TenantEnvironmentBootstrapRequest`
  - response: `TenantEnvironmentBootstrapResponse`

---

## Important implementation notes

### 1. This assumes repository methods exist
This route file assumes the repository has:
- `create_tenant(...)`
- `create_workspace(...)`
- `issue_api_key(...)`
- `bootstrap_tenant_environment(...)`

### 2. The convenience route is intentionally thin
It does not invent onboarding logic in the route layer.
It delegates to repository/bootstrap logic and only shapes the response.

### 3. Plaintext key exposure happens only on creation routes
- primitive key issuance returns plaintext once
- convenience bootstrap also returns plaintext once
- list routes remain non-secret

### 4. No extra decorator is needed per route
Because the router already carries the admin dependency, adding route-level `Depends(require_admin)` again would be redundant.
That said, if you want belt-and-suspenders clarity, you *could* add it per-route, but it is not necessary here.

---

## Recommended next build order

If implementing from these artifacts, the order is:
1. paste models into `app/models/api.py`
2. add repository methods to `app/controlplane/repositories/api_keys.py`
3. replace `app/api/routes_identity_admin.py` with this block
4. run route/repository tests
5. verify a created key works against `/v1/chat/completions`

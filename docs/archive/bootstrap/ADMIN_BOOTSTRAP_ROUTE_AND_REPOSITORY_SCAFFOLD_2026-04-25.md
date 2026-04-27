# Admin Bootstrap Route + Repository Scaffold — 2026-04-25

This is implementation-grade scaffolding for the minimal bootstrap surface.

It is not meant to be final polished code.
It is meant to make the next build pass nearly mechanical.

---

## 1. Repository additions

### Target file
- `app/controlplane/repositories/api_keys.py`

### New imports to add

```python
import secrets
import uuid

import asyncpg

from app.core.tenant_authorization import derive_tenant_role, normalize_tenant_capabilities
```

If you prefer not to import `asyncpg` just for error handling, use a broader `Exception` for the first pass and tighten later.
But using `asyncpg.UniqueViolationError` is cleaner.

---

### Suggested exception types

Add near the top of `api_keys.py`:

```python
class IdentityConflictError(ValueError):
    pass


class IdentityNotFoundError(ValueError):
    pass


class IdentityValidationError(ValueError):
    pass
```

This is enough for clear route mapping without building a full exception taxonomy.

---

### Suggested helper methods

Add near the bottom of `api_keys.py`:

```python
def _generate_tenant_id() -> str:
    return f"tenant_{uuid.uuid4().hex}"


def _generate_workspace_id() -> str:
    return f"ws_{uuid.uuid4().hex}"


def _generate_api_key_id() -> str:
    return f"mk_{uuid.uuid4().hex}"


def _generate_plaintext_api_key() -> str:
    return f"metera_live_{secrets.token_urlsafe(24)}"


def _derive_key_prefix(plaintext_api_key: str) -> str:
    suffix = plaintext_api_key.removeprefix("metera_live_")[:8]
    return f"mk_live_{suffix}"


def _normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return dict(metadata or {})
```
```

If you want shorter IDs later, change them later. For now: boring > clever.

---

### `create_tenant()` scaffold

```python
async def create_tenant(
    self,
    *,
    slug: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pool = await self._get_pool()
    await self.ensure_schema()

    tenant_id = _generate_tenant_id()
    metadata_json = json.dumps(_normalize_metadata(metadata))

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO tenants (id, slug, name, status, metadata)
            VALUES ($1, $2, $3, 'active', $4::jsonb)
            RETURNING id, slug, name, status, metadata, created_at, updated_at
            """,
            tenant_id,
            slug,
            name,
            metadata_json,
        )
    except asyncpg.UniqueViolationError as exc:
        raise IdentityConflictError(f"Tenant slug '{slug}' already exists") from exc

    return dict(row)
```

---

### `create_workspace()` scaffold

```python
async def create_workspace(
    self,
    *,
    tenant_id: str,
    slug: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pool = await self._get_pool()
    await self.ensure_schema()

    tenant_row = await pool.fetchrow(
        "SELECT id FROM tenants WHERE id = $1 LIMIT 1",
        tenant_id,
    )
    if tenant_row is None:
        raise IdentityNotFoundError("Tenant not found")

    workspace_id = _generate_workspace_id()
    metadata_json = json.dumps(_normalize_metadata(metadata))

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO workspaces (id, tenant_id, slug, name, status, default_environment_id, metadata)
            VALUES ($1, $2, $3, $4, 'active', NULL, $5::jsonb)
            RETURNING id, tenant_id, slug, name, status, default_environment_id, metadata, created_at, updated_at
            """,
            workspace_id,
            tenant_id,
            slug,
            name,
            metadata_json,
        )
    except asyncpg.UniqueViolationError as exc:
        raise IdentityConflictError(f"Workspace slug '{slug}' already exists for tenant '{tenant_id}'") from exc

    return dict(row)
```

---

### `issue_api_key()` scaffold

```python
async def issue_api_key(
    self,
    *,
    tenant_id: str,
    workspace_id: str,
    display_name: str,
    tenant_role: str = "tenant_admin",
    tenant_capabilities: tuple[str, ...] | list[str] | set[str] | None = None,
    environment_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_id: str = "admin_api",
) -> dict[str, Any]:
    pool = await self._get_pool()
    await self.ensure_schema()

    workspace_row = await pool.fetchrow(
        """
        SELECT id, tenant_id
        FROM workspaces
        WHERE id = $1
        LIMIT 1
        """,
        workspace_id,
    )
    if workspace_row is None:
        raise IdentityNotFoundError("Workspace not found")
    if str(workspace_row["tenant_id"]) != tenant_id:
        raise IdentityValidationError("Workspace does not belong to tenant")

    if environment_id is not None:
        environment_row = await pool.fetchrow(
            """
            SELECT id, workspace_id
            FROM environments
            WHERE id = $1
            LIMIT 1
            """,
            environment_id,
        )
        if environment_row is None:
            raise IdentityNotFoundError("Environment not found")
        if str(environment_row["workspace_id"]) != workspace_id:
            raise IdentityValidationError("Environment does not belong to workspace")

    effective_role = derive_tenant_role(
        tenant_role=tenant_role,
        tenant_capabilities=tenant_capabilities,
    )
    effective_capabilities = normalize_tenant_capabilities(
        role=effective_role,
        tenant_capabilities=tenant_capabilities,
    )

    plaintext_api_key = _generate_plaintext_api_key()
    key_id = _generate_api_key_id()
    key_prefix = _derive_key_prefix(plaintext_api_key)
    key_hash = sha256(plaintext_api_key.encode("utf-8")).hexdigest()

    stored_metadata = _normalize_metadata(metadata)
    stored_metadata["tenant_role"] = effective_role
    stored_metadata["tenant_capabilities"] = list(effective_capabilities)

    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO api_keys (
                        id, tenant_id, workspace_id, environment_id, key_prefix, key_hash, display_name, status, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8::jsonb)
                    RETURNING id, tenant_id, workspace_id, environment_id, key_prefix, display_name, status, metadata, created_at, updated_at, revoked_at
                    """,
                    key_id,
                    tenant_id,
                    workspace_id,
                    environment_id,
                    key_prefix,
                    key_hash,
                    display_name,
                    json.dumps(stored_metadata),
                )
            except asyncpg.UniqueViolationError as exc:
                raise IdentityConflictError("Generated API key prefix collided; retry issuance") from exc

            await conn.execute(
                """
                INSERT INTO api_key_lifecycle_log (
                    api_key_id, tenant_id, workspace_id, event_type, actor_type, actor_id, payload
                )
                VALUES ($1, $2, $3, 'created', 'platform_admin', $4, $5::jsonb)
                """,
                key_id,
                tenant_id,
                workspace_id,
                actor_id,
                json.dumps({"key_prefix": key_prefix}),
            )

    result = dict(row)
    result["plaintext_api_key"] = plaintext_api_key
    result["tenant_role"] = effective_role
    result["tenant_capabilities"] = list(effective_capabilities)
    return result
```

---

### Optional `bootstrap_tenant_environment()` scaffold

Recommendation: do this after the primitive routes work.

```python
async def bootstrap_tenant_environment(
    self,
    *,
    tenant_slug: str,
    tenant_name: str,
    workspace_slug: str,
    workspace_name: str,
    api_key_display_name: str,
    tenant_role: str = "tenant_admin",
    tenant_capabilities: tuple[str, ...] | list[str] | set[str] | None = None,
    metadata: dict[str, Any] | None = None,
    actor_id: str = "admin_api",
) -> dict[str, Any]:
    tenant = await self.create_tenant(
        slug=tenant_slug,
        name=tenant_name,
        metadata=metadata,
    )
    workspace = await self.create_workspace(
        tenant_id=tenant["id"],
        slug=workspace_slug,
        name=workspace_name,
        metadata=metadata,
    )
    api_key = await self.issue_api_key(
        tenant_id=tenant["id"],
        workspace_id=workspace["id"],
        display_name=api_key_display_name,
        tenant_role=tenant_role,
        tenant_capabilities=tenant_capabilities,
        metadata=metadata,
        actor_id=actor_id,
    )
    return {
        "tenant": tenant,
        "workspace": workspace,
        "api_key": api_key,
    }
```

Later you can make it transactional. For the first pass, primitive routes matter more.

---

## 2. Route-layer scaffolding

### Target file
- `app/api/routes_identity_admin.py`

### New imports to add

```python
from app.controlplane.repositories.api_keys import (
    IdentityConflictError,
    IdentityNotFoundError,
    IdentityValidationError,
)
from app.models.api import (
    ApiKeyIssueRequest,
    ApiKeyIssueResponse,
    TenantCreateRequest,
    TenantEnvironmentBootstrapRequest,
    TenantEnvironmentBootstrapResponse,
    WorkspaceCreateRequest,
)
```

If you do not add the convenience route yet, omit the bootstrap request/response imports.

---

### `POST /admin/control/tenants` scaffold

```python
@router.post("/control/tenants", response_model=TenantSummary)
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
```

---

### `POST /admin/control/workspaces` scaffold

```python
@router.post("/control/workspaces", response_model=WorkspaceSummary)
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
```

---

### `POST /admin/control/api-keys` scaffold

```python
@router.post("/control/api-keys", response_model=ApiKeyIssueResponse)
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
```

---

### Optional `POST /admin/control/bootstrap/tenant-environment` scaffold

```python
@router.post("/control/bootstrap/tenant-environment", response_model=TenantEnvironmentBootstrapResponse)
async def bootstrap_tenant_environment(payload: TenantEnvironmentBootstrapRequest, request: Request) -> TenantEnvironmentBootstrapResponse:
    repository = _require_identity_repository(request)
    try:
        result = await repository.bootstrap_tenant_environment(
            tenant_slug=payload.tenant.slug,
            tenant_name=payload.tenant.name,
            workspace_slug=payload.workspace.slug,
            workspace_name=payload.workspace.name,
            api_key_display_name=payload.api_key.display_name,
            tenant_role=payload.api_key.tenant_role,
            tenant_capabilities=payload.api_key.tenant_capabilities,
            metadata={"source": "beta_onboarding"},
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
        bootstrap={
            "namespace_header": "x-metera-namespace",
            "recommended_namespace": recommended_namespace,
            "chat_completions_url": "/v1/chat/completions",
        },
    )
```

If you want stronger typing for the `bootstrap` block, add a dedicated response model.

---

## 3. Practical notes for the actual implementation

### A. Keep environment optional
Do not force environment creation in this first pass.
The current request path can already resolve keys with `environment_id=None`.

### B. Reuse metadata conventions already in the repo
The pilot seed path already writes:
- `tenant_role`
- `tenant_capabilities`

Do the same for issued keys.

### C. Do not return plaintext keys from list routes
Only creation response gets plaintext.
Existing list routes should stay non-secret.

### D. Do not break static identity seed path
Leave `seed_static_identity()` intact.
This new path should be additive.

---

## 4. Thin request/response model placeholders

These belong in `app/models/api.py` and are here just so the route scaffold is concrete.

```python
class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    metadata: dict = Field(default_factory=dict)


class WorkspaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    metadata: dict = Field(default_factory=dict)


class ApiKeyIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(..., min_length=1, max_length=128)
    workspace_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)
    tenant_role: str = Field(default="tenant_admin", min_length=1, max_length=64)
    tenant_capabilities: list[str] = Field(default_factory=list)
    environment_id: str | None = Field(default=None, max_length=128)
    metadata: dict = Field(default_factory=dict)


class ApiKeyIssueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    workspace_id: str
    environment_id: str | None = None
    key_prefix: str
    display_name: str
    status: str
    plaintext_api_key: str
    tenant_role: str
    tenant_capabilities: list[str]
```

You can add the convenience bootstrap request/response after the primitive flow is working.

---

## 5. Recommended first implementation sequence

If the next agent is coding this, the least-risk order is:

1. add exceptions + helpers in `api_keys.py`
2. add `create_tenant()`
3. add `create_workspace()`
4. add `issue_api_key()`
5. add request/response models in `app/models/api.py`
6. add three admin routes in `routes_identity_admin.py`
7. test primitive flow
8. only then add convenience bootstrap route

That keeps the blast radius small and reviewable.

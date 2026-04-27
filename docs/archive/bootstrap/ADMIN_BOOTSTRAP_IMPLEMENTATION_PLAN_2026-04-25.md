# Admin Bootstrap Implementation Plan — 2026-04-25

## Purpose

Translate `docs/ADMIN_BOOTSTRAP_API_SPEC_2026-04-25.md` into a concrete repo-level build plan.

This plan is intentionally:
- minimal
- lease-first
- aligned with the current codebase
- focused on removing DB-seeding from normal beta onboarding

---

## Executive summary

The good news: **most of the hard persistence model already exists**.

`app/controlplane/repositories/api_keys.py` already owns schema and read-side identity behavior for:
- `tenants`
- `workspaces`
- `environments`
- `api_keys`
- `api_key_lifecycle_log`

That means the implementation is mostly:
1. extend repository with **write methods**
2. add **request/response models**
3. add **admin routes**
4. optionally add **one convenience bootstrap route**
5. add **tests** proving the returned key works against the existing request path

This is not a platform rewrite.

---

## Build order

### Phase 1 — primitive bootstrap writes
Implement:
- create tenant
- create workspace
- issue API key

### Phase 2 — convenience onboarding wrapper
Implement:
- bootstrap tenant environment

### Phase 3 — proof the path end to end
Add test coverage proving:
- created key resolves through identity resolver
- created key can hit `/v1/chat/completions`
- created key can hit tenant billing read surfaces if granted tenant-admin capabilities

---

## File-by-file plan

## 1. Repository layer

### File
- `app/controlplane/repositories/api_keys.py`

### Why this file
This repository already:
- creates the identity schema
- seeds static identity
- resolves bearer tokens
- lists tenants/workspaces/api-keys
- revokes API keys

It is the correct home for the minimal bootstrap writes unless a later refactor splits identity admin writes into a sibling repository.

### Add methods

#### `create_tenant(...)`
Suggested signature:

```python
async def create_tenant(
    self,
    *,
    slug: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Behavior:
- ensure schema
- generate server-side tenant id
- insert active tenant row
- raise a controlled conflict error if slug exists
- return inserted row fields needed by API

Notes:
- use generated IDs, not client-supplied IDs, for the bootstrap API
- normalize metadata to `{}`

#### `create_workspace(...)`
Suggested signature:

```python
async def create_workspace(
    self,
    *,
    tenant_id: str,
    slug: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Behavior:
- verify tenant exists
- enforce uniqueness of `(tenant_id, slug)`
- insert active workspace row
- leave `default_environment_id` null in v1
- return inserted row

#### `issue_api_key(...)`
Suggested signature:

```python
async def issue_api_key(
    self,
    *,
    tenant_id: str,
    workspace_id: str,
    display_name: str,
    tenant_role: str = "tenant_admin",
    tenant_capabilities: tuple[str, ...] | list[str] = (),
    environment_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_id: str = "admin_api",
) -> dict[str, Any]:
```

Behavior:
- verify workspace exists and belongs to tenant
- optionally verify environment belongs to workspace if provided
- generate plaintext token
- derive key prefix
- hash token
- store key row
- store lifecycle log row with event `created`
- persist normalized role/capabilities in metadata
- return both stored row and plaintext token

Return shape should include:
- api_key id
- tenant_id
- workspace_id
- environment_id
- key_prefix
- display_name
- status
- plaintext_api_key
- tenant_role
- tenant_capabilities

#### Optional helper: `bootstrap_tenant_environment(...)`
Suggested signature:

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
    tenant_capabilities: tuple[str, ...] | list[str] = (),
    metadata: dict[str, Any] | None = None,
    actor_id: str = "admin_api",
) -> dict[str, Any]:
```

Behavior:
- wrap tenant + workspace + key creation in one transaction if practical
- fail on conflict in v1
- return combined response payload

### Internal helpers to add

Suggested private helpers inside `api_keys.py`:
- `_generate_tenant_id()`
- `_generate_workspace_id()`
- `_generate_api_key_id()`
- `_generate_plaintext_api_key()`
- `_derive_key_prefix()`
- `_normalize_metadata()`
- `_ensure_workspace_belongs_to_tenant()`
- `_ensure_environment_belongs_to_workspace()`

### Error strategy
Do not leak raw asyncpg exceptions into routes.

Prefer controlled repository-level exceptions such as:
- `IdentityConflictError`
- `IdentityNotFoundError`
- `IdentityValidationError`

If you want to keep it very small, `ValueError` is acceptable for v1, but typed exceptions will age better.

---

## 2. Request/response models

### File
- `app/models/api.py`

### Add request models

#### `TenantCreateRequest`
```python
class TenantCreateRequest(BaseModel):
    slug: str
    name: str
    metadata: dict = Field(default_factory=dict)
```

#### `WorkspaceCreateRequest`
```python
class WorkspaceCreateRequest(BaseModel):
    tenant_id: str
    slug: str
    name: str
    metadata: dict = Field(default_factory=dict)
```

#### `ApiKeyIssueRequest`
```python
class ApiKeyIssueRequest(BaseModel):
    tenant_id: str
    workspace_id: str
    display_name: str
    tenant_role: str = "tenant_admin"
    tenant_capabilities: list[str] = Field(default_factory=list)
    environment_id: str | None = None
    metadata: dict = Field(default_factory=dict)
```

#### `TenantEnvironmentBootstrapRequest`
```python
class TenantEnvironmentBootstrapRequest(BaseModel):
    tenant: TenantBootstrapPayload
    workspace: WorkspaceBootstrapPayload
    api_key: ApiKeyBootstrapPayload
```

You can either make nested payload types or flatten the request.
Nested is cleaner for future onboarding reuse.

### Add response models

#### Reuse where possible
- `TenantSummary`
- `WorkspaceSummary`

#### Add `ApiKeyIssueResponse`
Must include plaintext token, so this must be new.

```python
class ApiKeyIssueResponse(BaseModel):
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

#### Add `TenantEnvironmentBootstrapResponse`
Combined payload containing:
- tenant summary
- workspace summary
- issued key response
- bootstrap usage block

Include:
- `namespace_header`
- `recommended_namespace`
- `chat_completions_url`

### Validation guidance
Keep validations pragmatic for v1:
- strip whitespace
- non-empty slug/name/display_name
- cap lengths reasonably
- do not overengineer slug normalization in the first pass unless there is already a shared helper

---

## 3. Admin route layer

### File
- `app/api/routes_identity_admin.py`

### Why this file
It already hosts the identity admin surface:
- identity status
- tenant list
- workspace list
- api-key list
- revoke key

Bootstrap writes belong here.

### Add routes

#### `POST /admin/control/tenants`
Uses:
- `TenantCreateRequest`
- repository `create_tenant()`
- response: `TenantSummary`

#### `POST /admin/control/workspaces`
Uses:
- `WorkspaceCreateRequest`
- repository `create_workspace()`
- response: `WorkspaceSummary`

#### `POST /admin/control/api-keys`
Uses:
- `ApiKeyIssueRequest`
- repository `issue_api_key()`
- response: `ApiKeyIssueResponse`

#### Optional `POST /admin/control/bootstrap/tenant-environment`
Uses:
- `TenantEnvironmentBootstrapRequest`
- repository convenience method or route-layer orchestration
- response: `TenantEnvironmentBootstrapResponse`

### Route behavior
Map errors explicitly:
- conflict -> `409`
- tenant/workspace/environment missing -> `404`
- validation mismatch (e.g. workspace not under tenant) -> `400`

### Important route rule
The route must never log or later re-expose the plaintext token after creation response.
Creation response is the one allowed reveal moment.

---

## 4. Authorization / capability normalization

### Relevant existing area
- tenant-role/capability normalization logic already exists elsewhere in the codebase used by tenant billing access evaluation

### Implementation guidance
When issuing keys:
- if client supplies no capabilities, derive from `tenant_role`
- if client supplies capabilities, normalize them
- persist the effective values in API key metadata

Why:
`resolve_key()` already reads role/capabilities from `api_keys.metadata` and feeds them into the proxy context.
That means the bootstrap routes should produce metadata in the exact shape the runtime already understands.

### Required metadata shape
At minimum:

```json
{
  "tenant_role": "tenant_admin",
  "tenant_capabilities": [
    "billing:read",
    "billing:history:read",
    "billing:adjustments:read",
    "billing:scope:read"
  ],
  "source": "beta_onboarding"
}
```

This matches the existing pilot seed posture and avoids inventing a new convention.

---

## 5. Main app wiring

### File
- `app/main.py`

### Expected change
Probably none.

Reason:
`routes_identity_admin.py` is already included in `app/main.py`.
Adding routes inside that module should be enough.

---

## 6. App services / lifecycle

### Files
- `app/core/app_services.py`
- `app/core/lifecycle.py`

### Expected change
Probably minimal or none.

Reason:
`identity_repository` is already initialized and attached to app state/services via `IdentityService.bootstrap(...)`.

### One thing to verify during implementation
Make sure the repository is available whenever:
- admin identity routes are enabled
- `METERA_CONTROLPLANE_IDENTITY_ENABLED=true`
- a valid policy/identity DSN exists

If not, the route should fail clearly with `503`, which the current helper already does.

---

## 7. Tests

### Add tests in the API/control-plane area
If there is an existing test layout, follow it.
If not, create focused tests around the route layer and repository behavior.

### Minimum required tests

#### Repository tests
- creating tenant succeeds
- duplicate tenant slug conflicts
- creating workspace under valid tenant succeeds
- workspace under missing tenant fails
- duplicate workspace slug under same tenant conflicts
- issuing key succeeds and returns plaintext token
- issuing key stores hashed material only
- issuing key writes lifecycle log row
- issuing key for workspace not under tenant fails

#### Route tests
- `POST /admin/control/tenants` with admin key succeeds
- same request without admin key is rejected
- `POST /admin/control/workspaces` succeeds for valid tenant
- `POST /admin/control/api-keys` returns plaintext token once
- conflict and not-found conditions map to correct HTTP statuses

#### End-to-end smoke test
The most important one:
1. create tenant
2. create workspace
3. issue API key
4. call `/v1/chat/completions` with returned bearer token
5. assert request passes identity resolution and reaches normal proxy path

Optional stronger variant:
6. call `/control/tenant/billing/scope` or `/control/tenant/billing/overview` with the same token if identity-enabled tenant route access is wired in the test environment

---

## 8. Docs to update after implementation

Once the routes exist, update:
- `docs/RAILWAY_API_TEST_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_BETA_GAP_ANALYSIS_2026-04-25.md`
- any onboarding/runbook docs that currently say DB seeding is required

Specifically, remove or narrow the claim that cloud proof requires DB-side identity bootstrap.

---

## Recommended first shipping cut

If the goal is speed with correctness, ship in this exact order:

### Cut 1
- repository `create_tenant`
- repository `create_workspace`
- repository `issue_api_key`
- request/response models
- three primitive admin routes
- tests for all three

### Cut 2
- convenience route `/admin/control/bootstrap/tenant-environment`
- combined response payload with recommended namespace
- one end-to-end onboarding test

This keeps the first merge tight and reviewable.

---

## Concrete example of intended runtime outcome

After implementation, an operator should be able to do this sequence against Railway:

1. `POST /admin/control/tenants`
2. `POST /admin/control/workspaces`
3. `POST /admin/control/api-keys`
4. copy returned plaintext key
5. send:

```http
POST /v1/chat/completions
Authorization: Bearer metera_live_xxx
x-metera-namespace: acme-default
Content-Type: application/json
```

and get a normal request-path response.

That is the real success test.

---

## Hard constraints to preserve

While implementing, do **not** accidentally break these:
- existing static identity bootstrap path
- existing repository-backed key resolution
- existing API key revocation behavior
- existing pilot proof path

This feature should add bootstrap capability, not replace the current validated auth spine.

---

## Final recommendation

Build the primitive routes first, not the convenience wrapper first.

Why:
- easier to test
- easier to review
- cleaner failure semantics
- gives you reusable internals for the signup/onboarding flow later

Then add the one-call bootstrap route as the thin orchestration layer on top.

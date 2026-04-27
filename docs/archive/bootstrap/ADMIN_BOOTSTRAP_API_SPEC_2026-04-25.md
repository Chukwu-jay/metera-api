# Admin Bootstrap API Spec — 2026-04-25

## Purpose

Define the **smallest possible admin API surface** needed to create a working tenant environment on a live Metera deployment **without privileged DB access**.

This is intentionally:
- **lease-first**
- minimal
- Beta-oriented
- built to unblock onboarding and Railway proof flows
- designed so it can later become the backend of the signup / onboarding page

This is **not** a full identity platform spec.
It is the thinnest credible control-plane bootstrap slice.

---

## Executive decision

Implement exactly **three bootstrap write operations**:

1. **create tenant**
2. **create workspace**
3. **issue API key**

Optionally add a fourth convenience endpoint:
4. **bootstrap environment lease**

But the real minimum is the first three.

Why:
- this mirrors the current proven identity model
- it matches the existing repository-backed key resolution path
- it removes the DB-seeding dependency from cloud onboarding
- it avoids overbuilding plans/environments/organizations before they are needed

---

## Lease-first meaning

In this spec, “lease-first” means:
- create only the minimum durable records required to let a tenant use the proxy now
- prefer a simple active tenant + active workspace + one active API key
- avoid deep provisioning trees unless the runtime actually requires them
- make the environment feel provisioned from the customer's perspective even if internally it is a lightweight bootstrap lease

So the first usable tenant environment is:
- one tenant
- one workspace
- zero or one default environment record
- one issued API key
- optionally one namespace recommendation

This is enough to send traffic through `/v1/chat/completions` immediately.

---

## Goals

### Must achieve
- create a usable tenant without DB access
- create a usable workspace bound to that tenant
- mint an API key that resolves through the existing identity path
- return enough information for immediate proxy usage
- keep auth simple and admin-gated

### Must not do
- redesign the request path
- introduce signup complexity before it is needed
- require a full billing bootstrap just to create a working environment
- require environment records if they are not essential for the first request path

---

## Non-goals

This spec does **not** include:
- end-user signup UX
- email verification
- self-serve org management
- invitation flows
- billing-plan selection UX
- usage caps purchasing flow
- public unauthenticated registration
- complex environment lifecycle management

Those can come later.

---

## Fit with current code

This spec is intentionally aligned with the code that already exists:

### Already present
- repository-backed API key resolution
- tenant/workspace/api-key records in Postgres
- admin auth via `x-metera-admin-key`
- proxy bearer-token identity resolution for `/v1/chat/completions`

### Already missing
- admin write routes for tenant/workspace/key creation

### Therefore
The right move is to add small admin write routes on top of the existing identity repository model.
Not to introduce a parallel onboarding subsystem.

---

## Minimal domain model for bootstrap

## Tenant
Represents the customer account boundary.

Minimum required fields:
- `id`
- `slug`
- `name`
- `status=active`
- `metadata`

## Workspace
Represents the first usable operational scope for that tenant.

Minimum required fields:
- `id`
- `tenant_id`
- `slug`
- `name`
- `status=active`
- `default_environment_id` optional
- `metadata`

## API key
Represents the first usable bearer credential.

Minimum required fields:
- `id`
- `tenant_id`
- `workspace_id`
- `environment_id` optional
- `key_prefix`
- `display_name`
- `status=active`
- hashed key material only at rest
- lifecycle log entry
- metadata including bootstrap role/capabilities

## Environment record
Optional for the first cut.

Recommendation:
- allow `environment_id = null` in v1 bootstrap
- expose a synthetic environment label like `default` in response if needed for UX
- only create physical environment rows if a hard runtime dependency appears

Reason:
The current proxy path does not require a non-null environment ID to resolve identity for requests.

---

## API surface

All routes are admin-only and live under `/admin/control`.
All write routes require:
- header: `x-metera-admin-key`
- content type: `application/json`

### 1. Create tenant

**POST** `/admin/control/tenants`

Purpose:
- create a new active tenant record

Request:

```json
{
  "slug": "acme",
  "name": "Acme",
  "metadata": {
    "source": "beta_onboarding"
  }
}
```

Response:

```json
{
  "id": "tenant_01...",
  "slug": "acme",
  "name": "Acme",
  "status": "active"
}
```

Rules:
- `slug` must be unique
- if slug already exists, return `409`
- server generates durable `id`
- status defaults to `active`

---

### 2. Create workspace

**POST** `/admin/control/workspaces`

Purpose:
- create the first usable workspace for a tenant

Request:

```json
{
  "tenant_id": "tenant_01...",
  "slug": "default",
  "name": "Default Workspace",
  "metadata": {
    "source": "beta_onboarding"
  }
}
```

Response:

```json
{
  "id": "ws_01...",
  "tenant_id": "tenant_01...",
  "slug": "default",
  "name": "Default Workspace",
  "status": "active",
  "default_environment_id": null
}
```

Rules:
- tenant must exist
- workspace slug must be unique within tenant
- status defaults to `active`
- `default_environment_id` may remain `null` in v1

---

### 3. Issue API key

**POST** `/admin/control/api-keys`

Purpose:
- mint the first working bearer token for the tenant environment

Request:

```json
{
  "tenant_id": "tenant_01...",
  "workspace_id": "ws_01...",
  "display_name": "Beta Default Key",
  "tenant_role": "tenant_admin",
  "tenant_capabilities": [
    "billing:read",
    "billing:history:read",
    "billing:adjustments:read",
    "billing:scope:read"
  ],
  "metadata": {
    "source": "beta_onboarding"
  }
}
```

Response:

```json
{
  "id": "mk_01...",
  "tenant_id": "tenant_01...",
  "workspace_id": "ws_01...",
  "environment_id": null,
  "key_prefix": "mk_live_ab12",
  "display_name": "Beta Default Key",
  "status": "active",
  "plaintext_api_key": "metera_live_xxxxxxxxxxxxxxxxx",
  "tenant_role": "tenant_admin",
  "tenant_capabilities": [
    "billing:read",
    "billing:history:read",
    "billing:adjustments:read",
    "billing:scope:read"
  ]
}
```

Rules:
- plaintext key is returned **once only** on creation
- only hashed key material is stored
- create corresponding lifecycle log event
- workspace must belong to tenant
- if `tenant_capabilities` omitted, server derives defaults from `tenant_role`
- if both provided, normalize and persist the effective capability set

Recommendation for v1:
- default `tenant_role = tenant_admin`
- keep capability set minimal but sufficient for tenant billing visibility

---

## Optional convenience route

### 4. Bootstrap tenant environment

**POST** `/admin/control/bootstrap/tenant-environment`

Purpose:
- collapse tenant + workspace + API key creation into one operator call
- this is the best fit for the eventual signup/onboarding backend

Request:

```json
{
  "tenant": {
    "slug": "acme",
    "name": "Acme"
  },
  "workspace": {
    "slug": "default",
    "name": "Default Workspace"
  },
  "api_key": {
    "display_name": "Beta Default Key",
    "tenant_role": "tenant_admin"
  }
}
```

Response:

```json
{
  "tenant": {
    "id": "tenant_01...",
    "slug": "acme",
    "name": "Acme",
    "status": "active"
  },
  "workspace": {
    "id": "ws_01...",
    "tenant_id": "tenant_01...",
    "slug": "default",
    "name": "Default Workspace",
    "status": "active",
    "default_environment_id": null
  },
  "api_key": {
    "id": "mk_01...",
    "key_prefix": "mk_live_ab12",
    "display_name": "Beta Default Key",
    "status": "active",
    "plaintext_api_key": "metera_live_xxxxxxxxxxxxxxxxx"
  },
  "bootstrap": {
    "namespace_header": "x-metera-namespace",
    "recommended_namespace": "acme-default",
    "chat_completions_url": "/v1/chat/completions"
  }
}
```

Why this route matters:
- it is the easiest operator path
- it is the easiest future signup backend path
- it preserves the internal record separation while presenting one onboarding action

Recommendation:
- implement this route **in addition to** the three primitives, not instead of them

---

## Required response ergonomics

The bootstrap flow should return enough material for immediate usage.

Minimum response payload for the convenience route should include:
- tenant id/slug
- workspace id/slug
- plaintext API key once
- key prefix
- namespace header name
- recommended namespace
- example auth style
- endpoint path

This avoids forcing the operator to reconstruct how to use the account.

---

## Suggested request/response models

Add the following models in `app/models/api.py`:

### Requests
- `TenantCreateRequest`
- `WorkspaceCreateRequest`
- `ApiKeyIssueRequest`
- `TenantEnvironmentBootstrapRequest`

### Responses
- `TenantCreateResponse` (can reuse `TenantSummary` if fields align)
- `WorkspaceCreateResponse` (can reuse `WorkspaceSummary` if fields align)
- `ApiKeyIssueResponse` (new; must include plaintext key)
- `TenantEnvironmentBootstrapResponse`

Important:
`ApiKeySummary` is not enough for creation response because it intentionally does not include plaintext key.

---

## Status model

For v1 bootstrap, statuses should be boring and explicit:
- tenant: `active`
- workspace: `active`
- api key: `active`

Do not introduce lease-expiration semantics in the data model yet unless there is a hard product need.

Lease-first here is about **minimal scope**, not necessarily expiring records.

If temporary leases are needed later, add them through metadata or a separate bootstrap lease entity, not the first cut.

---

## Authorization model

All bootstrap write routes are admin-only for v1.

Use the existing admin mechanism:
- `x-metera-admin-key`

Do not make these routes public yet.
Do not overload tenant tokens to create more tenant identity.
Do not add partial public signup logic in the same change.

This keeps the trust boundary simple.

---

## Idempotency and conflict behavior

Because onboarding flows retry in the real world, the API should behave predictably.

### Primitive endpoints
- `POST /tenants`
  - `409` if slug exists
- `POST /workspaces`
  - `409` if workspace slug exists within tenant
- `POST /api-keys`
  - always creates a new key unless explicitly asked otherwise

### Convenience endpoint
For `/bootstrap/tenant-environment`, choose one of two modes:

#### Recommended v1 mode: explicit fail-on-conflict
- if tenant slug exists -> `409`
- if workspace slug exists -> `409`
- nothing silently reused

Reason:
this is simpler and safer for the first cut.

Optional later improvement:
- support `idempotency_key` or `allow_existing=true`

---

## Namespace recommendation

The bootstrap API should not hard-bind namespace policy yet, but it should return a recommended namespace.

Recommended derivation:
- `<tenant-slug>-<workspace-slug>`

Example:
- `acme-default`

Why:
- good enough for first request routing clarity
- avoids forcing a namespace config UI before needed
- gives the onboarding flow something concrete to show

---

## Minimal onboarding success contract

A bootstrap operation is successful only if the created key can immediately be used to call:
- `POST /v1/chat/completions`

and, if tenant billing read capabilities were issued, the same token can also access:
- `GET /control/tenant/billing/scope`
- `GET /control/tenant/billing/overview`

That is the real operator definition of done.

---

## Implementation notes

## Repository layer

Prefer adding repository methods rather than route-local SQL.

Needed capabilities likely include:
- create tenant
- create workspace
- create API key with hashed plaintext
- append key lifecycle log entry
- validate workspace belongs to tenant

If the current `PostgresApiKeyRepository` does not yet own tenant/workspace writes cleanly, either:
- extend it narrowly, or
- add a small identity admin repository beside it

Recommendation:
- keep this in the identity/control-plane layer
- do not scatter bootstrap persistence into routes

## Key generation

Server should generate:
- secure plaintext token
- stable key prefix derived for display/logging
- hashed key for storage

Plaintext token must only be returned at creation time.

## Capability normalization

Reuse existing tenant-role/capability normalization logic where possible.
Do not invent a second permission mapping table just for onboarding.

---

## Recommended endpoint order for build

### Phase 1 — true minimum
1. `POST /admin/control/tenants`
2. `POST /admin/control/workspaces`
3. `POST /admin/control/api-keys`

### Phase 2 — operator convenience
4. `POST /admin/control/bootstrap/tenant-environment`

### Phase 3 — follow-on productization
- rotate key
- deactivate key
- optional environment creation
- onboarding/session tracking

---

## Example operator flow

### Step 1
Create tenant:
- slug: `acme`
- name: `Acme`

### Step 2
Create workspace:
- tenant: `acme`
- slug: `default`
- name: `Default Workspace`

### Step 3
Issue API key:
- display name: `Beta Default Key`
- role: `tenant_admin`

### Step 4
Return onboarding payload:
- bearer token
- namespace header name
- recommended namespace: `acme-default`
- endpoint: `/v1/chat/completions`

At that point the tenant environment is live enough for Beta.

---

## Why this is the right cut

This spec deliberately avoids three common mistakes:

### Mistake 1 — overbuilding environments
You do not need a deep environment tree just to get first traffic flowing.

### Mistake 2 — coupling onboarding to billing setup
A tenant should be able to get a working environment before the full commercial workflow is configured.

### Mistake 3 — forcing DB-side seeding forever
The whole point of this spec is to remove privileged DB access from normal beta onboarding.

---

## Final recommendation

Build the bootstrap control plane in this order:

1. primitive admin create routes for tenant/workspace/api key
2. one convenience bootstrap route that wraps them
3. validate that the returned key works immediately against the live proxy

That is the simplest path from today's engineering-mediated beta to tomorrow's signup-backed onboarding flow.

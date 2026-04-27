# Admin Bootstrap Apply Checklist — 2026-04-25

Use this to apply the generated bootstrap artifacts into the repo **without creating duplicate classes/imports or half-wired routes**.

This is the practical merge order.

---

## Goal

Safely apply three implementation blocks into the codebase:
1. Pydantic models
2. identity admin routes
3. API key repository methods

And end with a coherent feature slice for:
- create tenant
- create workspace
- issue API key
- bootstrap tenant environment

---

## Source artifacts

Use these docs as the source of truth:

- Models:
  - `docs/ADMIN_BOOTSTRAP_PYDANTIC_MODELS_2026-04-25.md`
- Routes:
  - `docs/ADMIN_BOOTSTRAP_IDENTITY_ROUTES_2026-04-25.md`
- Repository:
  - `docs/ADMIN_BOOTSTRAP_API_KEYS_REPOSITORY_2026-04-25.md`

Supporting context:
- `docs/ADMIN_BOOTSTRAP_API_SPEC_2026-04-25.md`
- `docs/ADMIN_BOOTSTRAP_IMPLEMENTATION_PLAN_2026-04-25.md`
- `docs/ADMIN_BOOTSTRAP_ROUTE_AND_REPOSITORY_SCAFFOLD_2026-04-25.md`

---

## Order of application

Apply in this exact order:

### Step 1 — update `app/models/api.py`
Why first:
- route file depends on the new request/response models
- easiest low-risk change

### Step 2 — update `app/controlplane/repositories/api_keys.py`
Why second:
- route file depends on repository exceptions + new write methods
- repository is the real behavior boundary

### Step 3 — update `app/api/routes_identity_admin.py`
Why third:
- by this point, both models and repository methods exist
- route imports should resolve immediately

### Step 4 — run tests / smoke validation
Why last:
- catches integration mistakes cleanly

---

## Step 1 — Apply models safely

### Target file
- `app/models/api.py`

### What to add
From:
- `docs/ADMIN_BOOTSTRAP_PYDANTIC_MODELS_2026-04-25.md`

Add:
- `TenantCreateRequest`
- `WorkspaceCreateRequest`
- `ApiKeyIssueRequest`
- `ApiKeyIssueResponse`
- `TenantBootstrapPayload`
- `WorkspaceBootstrapPayload`
- `ApiKeyBootstrapPayload`
- `TenantEnvironmentBootstrapRequest`
- `BootstrapUsageResponse`
- `TenantEnvironmentBootstrapResponse`

### Where to place them
Recommended placement:
- after existing identity admin response models:
  - `IdentityStatusResponse`
  - `TenantSummary`
  - `WorkspaceSummary`
  - `ApiKeySummary`
  - `ApiKeyRevocationResponse`

### What to check before saving
- [ ] Do **not** duplicate imports already present at top of file
- [ ] `Any` is already imported from `typing`
- [ ] `field_validator` is already imported from `pydantic`
- [ ] `TenantSummary` and `WorkspaceSummary` remain defined before `TenantEnvironmentBootstrapResponse`
- [ ] No duplicate class names already exist in the file

### Expected result
`app/models/api.py` should parse with the new models available for route imports.

---

## Step 2 — Apply repository safely

### Target file
- `app/controlplane/repositories/api_keys.py`

### What to add
From:
- `docs/ADMIN_BOOTSTRAP_API_KEYS_REPOSITORY_2026-04-25.md`

You need:
- new imports
- new exception classes
- new helper methods
- new repository methods:
  - `create_tenant`
  - `create_workspace`
  - `issue_api_key`
  - `bootstrap_tenant_environment`

### Important warning
The repository artifact is written as a **coherent replacement block**.
That means you should **not** paste it blindly on top of the existing file and leave the old class/helpers in place.

### Safe application strategy
Preferred:
1. open current `api_keys.py`
2. merge the new imports at top
3. add the exception classes once
4. add the new methods into the existing `PostgresApiKeyRepository`
5. add the helper functions once at file bottom
6. keep existing methods that are unchanged

Alternative:
- replace the full file carefully with the provided coherent block
- but only if you verify you are not dropping any newer local edits

### Imports to ensure exist
- [ ] `json`
- [ ] `secrets`
- [ ] `uuid`
- [ ] `datetime`
- [ ] `sha256`
- [ ] `Any`
- [ ] `create_asyncpg_pool`
- [ ] `derive_tenant_role`
- [ ] `normalize_tenant_capabilities`
- [ ] `ResolvedKeyContext`

### What to check before saving
- [ ] There is only **one** `PostgresApiKeyRepository` class in the file
- [ ] There is only **one** `_decode_json_object(...)`
- [ ] There is only **one** `_normalize_metadata(...)`
- [ ] There is only **one** copy of each new helper (`_generate_tenant_id`, etc.)
- [ ] New methods are indented inside the class, not nested accidentally under another method
- [ ] Exception classes are top-level, not inside the class

### Functional checks to reason through
- [ ] `create_tenant()` enforces unique slug
- [ ] `create_workspace()` verifies tenant exists
- [ ] `issue_api_key()` verifies workspace belongs to tenant
- [ ] `issue_api_key()` stores hash, not plaintext
- [ ] `issue_api_key()` returns plaintext once in response payload
- [ ] `bootstrap_tenant_environment()` creates tenant -> workspace -> key in order
- [ ] bootstrap fails on tenant slug conflict

---

## Step 3 — Apply routes safely

### Target file
- `app/api/routes_identity_admin.py`

### What to add
From:
- `docs/ADMIN_BOOTSTRAP_IDENTITY_ROUTES_2026-04-25.md`

You need:
- model imports
- repository exception imports
- 3 primitive routes
- convenience bootstrap route

### Important warning
This artifact is also written as a **full route module body**.
So do not paste it below the existing route file without removing the old duplicated definitions.

### Safe application strategy
Preferred:
- replace the contents of `routes_identity_admin.py` with the provided file body

Why this is safer here:
- it is a small route file
- replacing it is lower risk than hand-merging line by line

### What to verify after replacing
- [ ] `APIRouter(... dependencies=[Depends(require_admin)])` is still present
- [ ] `identity_status` route still exists
- [ ] existing list routes still exist
- [ ] revoke route still exists
- [ ] new create routes exist
- [ ] bootstrap route exists
- [ ] `_require_identity_repository()` still exists once

### Model wiring checks
- [ ] `create_tenant` uses `TenantCreateRequest -> TenantSummary`
- [ ] `create_workspace` uses `WorkspaceCreateRequest -> WorkspaceSummary`
- [ ] `issue_api_key` uses `ApiKeyIssueRequest -> ApiKeyIssueResponse`
- [ ] `bootstrap_tenant_environment` uses `TenantEnvironmentBootstrapRequest -> TenantEnvironmentBootstrapResponse`

### Authorization checks
- [ ] router-level `Depends(require_admin)` exists
- [ ] no new route was accidentally created outside that router
- [ ] all bootstrap writes remain admin-only

---

## Step 4 — Sanity compile pass

Before running deeper tests, do a quick sanity pass:

- [ ] imports resolve in `app/models/api.py`
- [ ] imports resolve in `routes_identity_admin.py`
- [ ] imports resolve in `api_keys.py`
- [ ] no duplicate class names
- [ ] no duplicate function names
- [ ] no unresolved model names
- [ ] no unresolved repository exception names

If using Python tooling locally, this is the moment to run a fast import/compile check.

---

## Step 5 — Minimum behavior validation

After code is applied, validate this exact flow:

### Admin flow
- [ ] `POST /admin/control/tenants` creates tenant
- [ ] `POST /admin/control/workspaces` creates workspace
- [ ] `POST /admin/control/api-keys` returns plaintext key once
- [ ] `POST /admin/control/bootstrap/tenant-environment` creates full minimal environment

### Existing read flow still works
- [ ] `GET /admin/control/tenants`
- [ ] `GET /admin/control/workspaces`
- [ ] `GET /admin/control/api-keys`
- [ ] `POST /admin/control/api-keys/{id}/revoke`

### Runtime identity flow
- [ ] returned bearer token resolves through existing identity path
- [ ] token can be used against `/v1/chat/completions`

### Optional stronger validation
If identity-enabled tenant reads are active:
- [ ] token can hit `/control/tenant/billing/scope`
- [ ] token can hit `/control/tenant/billing/overview`

---

## Common failure modes to avoid

### 1. Duplicate class definitions
Most likely when pasting the repository or routes block under the old one.

### 2. Missing model imports
Most likely if routes are applied before models.

### 3. Missing capability helper imports in repository
`issue_api_key()` depends on:
- `derive_tenant_role`
- `normalize_tenant_capabilities`

### 4. Route file applied before repository methods exist
This causes import/runtime failures for the new repository calls.

### 5. Plaintext key accidentally exposed in list endpoints
Only create/bootstrap responses should return plaintext.
List routes must remain non-secret.

### 6. Bootstrap route added outside admin router
That would weaken authorization incorrectly.
Keep it inside the existing admin router.

---

## Definition of successful application

Application is complete only when all are true:
- [ ] code compiles/imports cleanly
- [ ] new models exist in `app/models/api.py`
- [ ] repository has all 4 new methods
- [ ] route file exposes all 4 new write routes
- [ ] all new routes are admin-protected
- [ ] returned API key works against live identity resolution
- [ ] no privileged DB seeding is required to create a minimal tenant environment

---

## Recommended operator sequence after merge

Once the code is merged and deployed, the first real proof should be:

1. create tenant
2. create workspace
3. issue API key
4. send live request through `/v1/chat/completions`
5. confirm identity resolution + normal proxy path
6. then use that bootstrap path to support Railway beta onboarding

That is the point where the system stops depending on direct DB seeding for tenant bootstrap.

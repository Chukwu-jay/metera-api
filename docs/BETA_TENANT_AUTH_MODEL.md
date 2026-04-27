# BETA_TENANT_AUTH_MODEL

Status: implemented for Beta tenant-facing billing/reporting surfaces
Owner module: `MOD_BETA_RELIABILITY.md`
Last updated: 2026-04-24

## Purpose
This document is the code-backed auth/authorization contract for tenant-facing Beta billing surfaces.
It exists so onboarding does not depend on dev-auth caveats or chat archaeology.

## Tenant-facing surfaces covered
All routes under `app/api/routes_tenant_billing.py` / `/control/tenant/*`:
- `GET /control/tenant/billing/scope`
- `GET /control/tenant/billing/overview`
- `GET /control/tenant/billing/subscriptions`
- `GET /control/tenant/billing/periods`
- `GET /control/tenant/billing/periods/{billing_period_id}/report`
- `GET /control/tenant/billing/reports`
- `GET /control/tenant/billing/history`
- `GET /control/tenant/billing/usage-charges`
- `GET /control/tenant/billing/adjustments`

## Auth model
### Production/Beta path
Use repository-backed tenant API keys via the standard bearer token header:
- `Authorization: Bearer <tenant-api-key>`

Resolution path:
1. `routes_tenant_billing._resolve_scope()` extracts the bearer token.
2. `IdentityService.resolve(...)` resolves tenant/workspace/api-key identity from the repository-backed resolver.
3. A `ProxyContext` is constructed from resolved identity.
4. `resolve_tenant_access_scope(...)` enforces that the authenticated tenant owns the request scope.
5. `require_tenant_capability(...)` enforces route-level authorization.

Source files:
- `app/api/routes_tenant_billing.py`
- `app/core/tenant_access.py`
- `app/core/tenant_authorization.py`
- `app/controlplane/repositories/api_keys.py`

## Authorization model
### Roles
Implemented roles:
- `tenant_reader`
  - `billing:read`
  - `billing:scope:read`
- `tenant_admin`
  - `billing:read`
  - `billing:scope:read`
  - `billing:history:read`
  - `billing:adjustments:read`

### Route capability mapping
- `billing:scope:read`
  - `/billing/scope`
- `billing:read`
  - `/billing/overview`
  - `/billing/subscriptions`
  - `/billing/periods`
  - `/billing/periods/{billing_period_id}/report`
  - `/billing/reports`
  - `/billing/usage-charges`
- `billing:history:read`
  - `/billing/history`
- `billing:adjustments:read`
  - `/billing/adjustments`

## Security posture
### Tenant scope
Authenticated tenant scope wins.
If a request includes `tenant_id`, it must match the authenticated tenant or the route returns `403`.

### Least-privilege fallback for incomplete metadata
Repository-backed API keys now default to `tenant_reader` if `tenant_role` metadata is absent.
Role derivation also falls back to `tenant_reader` when neither a recognized role nor sufficient capabilities are present.
This avoids silent privilege escalation to tenant admin on partially-seeded keys.

Code-backed changes:
- `app/controlplane/repositories/api_keys.py`
- `app/core/tenant_authorization.py`

## Transitional/dev-only fallback
A query-parameter tenant fallback still exists for local/dev/test convenience.
It is not the Beta onboarding path.

Behavior:
- enabled by default only in `dev`, `local`, `test`
- disabled by default in `prod`
- when used, access is constrained to `tenant_reader`

Config:
- `METERA_TENANT_QUERY_PARAM_FALLBACK_ENABLED`

## Beta onboarding requirement
For external Beta tenants, require all of the following:
1. repository-backed identity enabled
2. tenant API key provisioned in the control-plane repository
3. explicit `tenant_role` and/or `tenant_capabilities` metadata on the key
4. bearer-token authentication for tenant-facing billing/reporting routes
5. query-param fallback disabled in Beta/prod environments

## Operational note
The static resolver remains a compatibility/dev path. Do not use it as the primary auth model for external Beta tenants.

## Done condition for B1
B1 is considered complete for the current Beta billing/reporting surfaces because:
- every tenant-facing route has a defined capability requirement
- authenticated tenant scope is enforced consistently
- query-param fallback is explicitly transitional
- incomplete repository metadata no longer silently becomes tenant admin

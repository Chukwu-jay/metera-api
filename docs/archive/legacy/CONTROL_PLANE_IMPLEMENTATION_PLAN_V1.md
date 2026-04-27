# CONTROL_PLANE_IMPLEMENTATION_PLAN_V1

## Purpose

Translate the control-plane architecture and schema into a concrete implementation sequence for the current Metera codebase.

This document answers:
- what to build first
- what existing code to evolve
- what not to rewrite unnecessarily
- how to move from the current single-tenant/global-policy shape into a SaaS-ready control plane

This plan assumes:
- Phase 4.5 is complete
- the proxy/policy core is worth preserving
- the next priority is SaaS structure, not more safety-blocker remediation

---

# 1) Current repo reality

Metera already has useful building blocks:

## Existing strengths
- working proxy/data-plane core
- exact + semantic cache pipeline
- request profiling and compatibility validation
- admin routes scaffold (`app/api/routes_admin.py`)
- policy-state scaffold (`app/core/policy_state.py`)
- dashboard scaffold (`dashboard/app.py`)
- shadow analytics and metrics exposure
- proven validation artifacts for browser lane, nightmare suite, and mixed-corpus economics

## Current architectural limitations
- policy state is still effectively global, not tenant/workspace scoped
- no true tenant/workspace/api-key identity spine
- no append-only per-request SaaS ledger tied to tenant identity
- dashboard is ops-oriented, not a product-grade control surface
- no plan/trial/billing lifecycle
- admin auth is not yet a multi-tenant management model

## Engineering implication
We should **evolve** the current system, not replace it.

The proxy core is the right foundation.
The missing pieces are identity, scoped policy, ledger, and management surfaces.

---

# 2) Implementation strategy

## Guiding rule
Build the **minimum viable SaaS spine** underneath the current working proxy before expanding UI or billing complexity.

## Order of operations
1. identity foundation
2. request-context resolution
3. scoped policy service
4. append-only ledger
5. rollups + analytics
6. dashboard/control-plane surfaces
7. billing/trial enforcement

This order is deliberate.
Billing and dashboard work are downstream of attribution truth.

---

# 3) Phase A — Identity foundation

## Goal
Every request can be attributed to:
- tenant
- workspace
- API key
- environment
- namespace

## Deliverables
### Database
Create initial tables:
- `tenants`
- `workspaces`
- `environments`
- `api_keys`
- `api_key_lifecycle_log`

### Runtime
Add key resolution/auth path that maps an inbound bearer token to:
- `tenant_id`
- `workspace_id`
- `environment_id`
- `api_key_id`

### Request context
Extend the runtime request context model so it carries SaaS identity, not just namespace/request id.

## Existing code to evolve
Likely touch:
- `app/models/domain.py` or equivalent proxy context model
- `app/core/dependencies.py`
- auth middleware / provider auth extraction path
- namespace resolution logic

## New modules recommended
- `app/controlplane/models/tenant.py`
- `app/controlplane/models/workspace.py`
- `app/controlplane/models/api_key.py`
- `app/controlplane/auth/key_resolver.py`
- `app/controlplane/repositories/api_keys.py`

## Important implementation note
Do not query Postgres expensively on every request forever.

For v1:
- allow DB-backed lookup initially
- then add in-memory/TTL cache for key metadata as soon as the flow is correct

## Exit criteria
- requests can be tied to a real workspace-scoped API key
- request context contains tenant/workspace/key identity
- logs/telemetry can include these IDs

---

# 4) Phase B — Scoped policy service

## Goal
Replace global-only policy overrides with tenant/workspace/namespace-scoped policy.

## Deliverables
### Database
Create:
- `policy_versions`
- `policy_assignments`
- `namespace_policy_overrides`
- `policy_change_log`

### Runtime
Implement effective policy resolution using:
1. global default
2. plan default
3. tenant policy
4. workspace policy
5. namespace override
6. request-level safe override
7. runtime safety precedence

### Admin surface
Upgrade admin/policy APIs from one global state to scoped policy operations.

## Existing code to evolve
Current global scaffold:
- `app/core/policy_state.py`
- `app/api/routes_admin.py`

These should be treated as prototypes and migrated into a real control-plane policy service.

## New modules recommended
- `app/controlplane/models/policy.py`
- `app/controlplane/repositories/policies.py`
- `app/controlplane/services/policy_resolver.py`
- `app/controlplane/services/policy_snapshot_cache.py`
- `app/api/routes_controlplane_policy.py`

## Runtime integration point
`ProxyService` should stop reading a single global override bag and instead receive a resolved effective policy object per request.

That is a major seam.
Do it carefully.

## Important engineering caution
Do **not** couple effective policy resolution to admin-route logic.
Make policy resolution a first-class service, not a helper bolted to `/admin/policy`.

## Exit criteria
- workspace-scoped policy exists
- namespace override exists
- requests record effective policy version
- current behavior remains functionally unchanged for default cases

---

# 5) Phase C — Request ledger

## Goal
Create the financial/operational source of truth.

## Deliverables
### Database
Create:
- `request_ledger`
- `shadow_savings_ledger`
- `risk_events`

### Runtime writes
For each request, persist:
- request identity
- tenant/workspace/key context
- namespace
- model
- cache outcome
- policy version
- savings / upstream cost
- timing data
- modality/identity flags

### Shadow/risk logging
Move shadow analytics and regression events toward the normalized ledger/event model.

## Existing code to evolve
Relevant current areas:
- `app/services/proxy_service.py`
- current metrics/shadow analytics plumbing
- any existing stats summary logic

## New modules recommended
- `app/controlplane/models/ledger.py`
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/risk_events.py`
- `app/controlplane/repositories/shadow_savings.py`
- `app/controlplane/services/metering.py`

## Write-path recommendation
For v1:
- synchronous write is acceptable if lightweight and reliable
- but design interfaces so this can become async/background later

If latency impact is noticeable:
- move full ledger persistence to background task or queue-backed ingestion
- keep minimal counters inline

## Exit criteria
- each request becomes a durable ledger fact
- savings and spend can be computed per tenant/workspace/namespace
- shadow opportunity is durable and queryable

---

# 6) Phase D — Rollups and analytics

## Goal
Turn raw ledger events into product-grade summaries.

## Deliverables
### Database
Create:
- `daily_usage_rollups`
- `daily_namespace_rollups`

### Jobs
Implement scheduled aggregation jobs that derive:
- daily tenant usage
- daily workspace usage
- daily namespace usage
- realized vs shadow savings
- alert/mismatch rates

### Recommendation logic
Add simple rule-based namespace recommendations:
- remain soft
- review
- promote to strict

## Existing code to evolve
- `dashboard/app.py`
- stats summary endpoints
- any current shadow analytics readers

## New modules recommended
- `app/controlplane/jobs/rollup_usage.py`
- `app/controlplane/jobs/rollup_namespace.py`
- `app/controlplane/services/risk_recommendations.py`
- `app/api/routes_controlplane_analytics.py`

## Important note
Do not build the recommendation engine as ML.
Use deterministic rules first.

## Exit criteria
- namespace-level dashboards can be powered by rollups, not raw scans
- safety and savings can be displayed together per namespace

---

# 7) Phase E — Dashboard and management surfaces

## Goal
Promote the current dashboard from ops view to control-plane product surface.

## Deliverables
### Dashboard views
Build views for:
- tenant overview
- workspace overview
- savings / spend / shadow opportunity
- namespace risk analytics
- policy assignments
- API key lifecycle

### Admin APIs
Add scoped CRUD/query APIs for:
- tenants
- workspaces
- api keys
- policy assignments
- namespace overrides
- analytics summaries

## Existing code to evolve
- `dashboard/app.py`
- existing admin routes

## New modules recommended
- `app/api/routes_controlplane_tenants.py`
- `app/api/routes_controlplane_workspaces.py`
- `app/api/routes_controlplane_keys.py`
- `app/api/routes_controlplane_analytics.py`
- `app/api/routes_controlplane_policy.py`

## UI/UX stance
Do not let the dashboard become the source of truth.
It should read from the control-plane services and rollups.

## Exit criteria
- a tenant can be onboarded and inspected through the product surface
- policy and savings state are no longer hidden in internal-only ops endpoints

---

# 8) Phase F — Billing and trial controls

## Goal
Add commercial primitives after attribution and ledger correctness exist.

## Deliverables
### Database
Create:
- `plans`
- `subscriptions`
- `billing_periods`
- `usage_charges`
- `invoices`

### Product behavior
Implement:
- plan assignment
- trial state
- soft-cap warnings
- billing period closeout
- invoice/export generation

### Enforcement order
Recommended sequence:
1. dashboard warning
2. response metadata warning
3. admin alert
4. hard cap later if required

## New modules recommended
- `app/controlplane/models/billing.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/services/billing.py`
- `app/controlplane/jobs/close_billing_period.py`

## Important caution
Do not ship a harsh hard cutoff before client UX is ready.
Soft-cap first.

## Exit criteria
- tenants can be trialed and assigned a plan
- usage can be summarized into a billing period
- soft-cap notifications are visible

---

# 9) Cross-cutting refactors

These are not standalone phases but important structural changes.

## 9.1 Create a control-plane package boundary
Recommended new package root:
- `app/controlplane/`

Subpackages:
- `models/`
- `repositories/`
- `services/`
- `jobs/`
- `auth/`

This avoids smearing SaaS code across the current proxy modules.

## 9.2 Separate runtime policy objects from persistence models
Do not pass ORM/database rows directly into proxy logic.

Create explicit runtime types for:
- effective policy
- resolved key context
- metering event

## 9.3 Make request context richer
The proxy context should become the stable contract between auth, policy resolution, and metering.

Minimum target fields:
- tenant_id
- workspace_id
- environment_id
- api_key_id
- namespace
- request_id
- effective_policy_version_id
- effective_policy_mode

## 9.4 Keep metrics and ledger distinct
Prometheus/stats counters are for operational observability.
Ledger tables are for financial truth.
Do not blur them.

---

# 10) Suggested file/module roadmap

## Step 1: Identity
Add:
- `app/controlplane/models/tenant.py`
- `app/controlplane/models/workspace.py`
- `app/controlplane/models/api_key.py`
- `app/controlplane/repositories/tenants.py`
- `app/controlplane/repositories/workspaces.py`
- `app/controlplane/repositories/api_keys.py`
- `app/controlplane/auth/key_resolver.py`

Refactor:
- request context model
- auth dependency path

## Step 2: Policy
Add:
- `app/controlplane/models/policy.py`
- `app/controlplane/repositories/policies.py`
- `app/controlplane/services/policy_resolver.py`
- `app/controlplane/services/policy_snapshot_cache.py`

Refactor:
- `app/core/policy_state.py`
- `app/api/routes_admin.py`
- `app/services/proxy_service.py`

## Step 3: Ledger
Add:
- `app/controlplane/models/ledger.py`
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/risk_events.py`
- `app/controlplane/repositories/shadow_savings.py`
- `app/controlplane/services/metering.py`

Refactor:
- proxy response accounting path
- shadow analytics logging path

## Step 4: Analytics
Add:
- `app/controlplane/jobs/rollup_usage.py`
- `app/controlplane/jobs/rollup_namespace.py`
- `app/controlplane/services/risk_recommendations.py`
- `app/api/routes_controlplane_analytics.py`

Refactor:
- `dashboard/app.py`

## Step 5: Billing
Add:
- `app/controlplane/models/billing.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/services/billing.py`
- `app/controlplane/jobs/close_billing_period.py`

---

# 11) Suggested migration roadmap

## Migration batch 1 — identity
- create tenants/workspaces/environments/api_keys/api_key_lifecycle_log
- seed one internal tenant/workspace for current dev traffic if needed

## Migration batch 2 — policy
- create policy_versions/policy_assignments/namespace_policy_overrides/policy_change_log
- seed default global policy from current settings

## Migration batch 3 — ledger
- create request_ledger/shadow_savings_ledger/risk_events
- start dual-writing while validating correctness

## Migration batch 4 — rollups
- create daily_usage_rollups/daily_namespace_rollups
- run backfill from ledger if necessary

## Migration batch 5 — billing
- create plans/subscriptions/billing_periods/usage_charges/invoices

## Dual-write recommendation
For ledger introduction, use a short dual-write period:
- keep current stats/metrics behavior
- add new ledger persistence
- compare rollups before making the ledger authoritative for business reporting

That reduces migration risk.

---

# 12) API evolution plan

## Current state
The repo has early global admin routes.

## Target state
Introduce scoped control-plane APIs:
- `/control/tenants`
- `/control/workspaces`
- `/control/keys`
- `/control/policies`
- `/control/analytics`
- `/control/billing`

Do not break the current admin routes all at once.
Instead:
- keep them for internal/dev operations
- add new scoped control-plane routes for product evolution
- deprecate old global routes later

---

# 13) Risk management / pushback points

## 13.1 Don’t rewrite the proxy core
The proxy is already validated.
The next work should wrap it with identity/policy/ledger structure, not replace it.

## 13.2 Don’t build billing before ledger correctness
If we skip straight to pricing UX, we’ll create accounting debt immediately.

## 13.3 Don’t overcomplicate auth in v1
Start with workspace-scoped API keys.
Full RBAC can wait.

## 13.4 Don’t put all analytics into the request path
Rollups and recommendations belong in jobs/background services.

## 13.5 Don’t introduce a hard control-plane dependency on every request
Use cached snapshots and resolved context.

---

# 14) Milestone-based delivery plan

## Milestone 1 — Request attribution spine
Success means:
- inbound requests resolve to tenant/workspace/key
- request context is enriched
- no customer-facing control plane yet required

## Milestone 2 — Scoped policy
Success means:
- workspace and namespace policy can differ cleanly
- effective policy version is attached to requests

## Milestone 3 — Financial ledger
Success means:
- each request becomes a durable business fact
- savings/spend can be queried per tenant/workspace

## Milestone 4 — Namespace analytics
Success means:
- dashboard can show savings + prevented-risk posture together

## Milestone 5 — Tenant-facing control plane
Success means:
- customer onboarding and configuration become productized

## Milestone 6 — Billing/trial controls
Success means:
- product can enforce plans without architectural rework

---

# 15) Immediate next coding recommendation

If starting implementation now, the best first slice is:

## Slice 1
- add identity tables
- add key resolver
- extend request context
- attach tenant/workspace/key IDs to request handling and telemetry

Why this first:
- it is foundational
- it is narrow enough to implement safely
- it unlocks every later phase
- it does not require a full UI first

After that:

## Slice 2
- add policy versions + assignments
- implement effective policy resolution
- stop relying on one global override bag

---

# 16) Final engineering stance

The correct next move for Metera is not more theory.
It is controlled implementation of the SaaS spine in this order:

1. identity
2. scoped policy
3. ledger
4. analytics
5. dashboard/product surfaces
6. billing

That sequence preserves:
- speed
- architectural integrity
- safety correctness
- economic explainability
- future scalability

If executed in this order, Metera can become a real policy-and-economics control platform without losing the strengths already proven in the gateway core.

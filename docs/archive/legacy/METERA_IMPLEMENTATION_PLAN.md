# Metera Implementation Plan

## Purpose

This document is the executable implementation plan for Metera from the current validated gateway state to a real SaaS control platform.

It is grounded in:
- the current repo structure and codebase
- the validated Phase 4.5 safety closure
- the control-plane architecture, schema, and operational docs

This is not a greenfield plan.
It assumes a lot of important work is already correct and should be preserved.

---

# 1) Current state summary

## What exists today
Metera already has a strong and validated gateway core:
- FastAPI proxy runtime
- exact cache
- semantic cache
- request normalization and compatibility checks
- DLP / secret scrubbing controls
- namespace-aware request handling
- modality / identity / agentic request profiling
- strict-vs-soft semantic enforcement behavior
- Postgres-backed global policy override storage
- Postgres-backed shadow analytics tables
- read-only dashboard and metrics surface
- strong validation artifacts for browser lane, mixed corpus economics, and nightmare safety cases

## What the repo shape says today
Current application structure is roughly:
- `app/api/*` -> chat, admin, metrics, stats routes
- `app/services/proxy_service.py` -> main inline request path and semantic policy decisions
- `app/core/policy_state.py` -> current global policy override store
- `app/storage/shadow_analytics.py` -> Postgres-backed shadow evidence tables
- `dashboard/app.py` -> read-only operator dashboard
- `tests/*` -> substantial functional coverage for current gateway behavior

## What does not exist yet
Metera is not yet a true SaaS control plane.
Missing product-critical foundations:
- tenant model
- workspace model
- environment model
- workspace-scoped API keys
- request attribution spine
- scoped policy versions and assignments
- append-only request ledger
- rollup jobs and namespace-level product analytics
- billing / trial lifecycle primitives
- tenant-facing onboarding and management APIs

## Practical conclusion
The gateway core is not the problem.
The missing work is the SaaS spine around it.

---

# 2) Engineering stance

## Preserve, don’t rewrite
We are not rebuilding Metera from scratch.
We are wrapping a validated data plane with the correct identity, policy, metering, and product surfaces.

## Control-plane rule
The data plane must not depend on per-request remote control-plane lookups.
That means:
- no hot-path admin DB joins per request
- no control-plane API roundtrip on every request
- use resolved request context, local metadata cache, and policy snapshots

## Source-of-truth rule
The dashboard is not the architecture.
The source of truth must become:
- identity records
- immutable policy versions
- append-only request ledger
- derived rollups

## Correct sequencing rule
The implementation order is fixed for good reason:
1. identity
2. request attribution
3. scoped policy
4. ledger
5. rollups / analytics
6. control-plane APIs and dashboard
7. billing / plans / trials

If we violate that order, we create accounting debt and rework.

## Controlled release rule
All business-logic rollout must be compatibility-preserving.
That means:
- new control-plane behavior ships behind flags
- existing gateway behavior remains the default until promoted
- seeded internal/dev identity is allowed for rollout safety
- repository-backed identity/policy can fail back to static compatibility mode during early rollout
- no flag-day migration for request handling

---

# 3) Success criteria for the whole project

Metera v1 is successful only if all four of these are true.

## 3.1 Safety success
- browser / agentic protected lanes remain effectively semantic-reuse disabled in live serving
- visual requests hard-align whenever multimodal hard alignment is enabled
- flagged incompatible semantic candidates are never served in soft mode
- identity-sensitive requests do not leak across user boundaries

## 3.2 Economic success
- low-risk text lanes preserve strong realized savings
- realized savings, upstream spend, and shadow opportunity are all queryable per tenant/workspace/namespace
- economics are explainable from ledger truth, not estimated dashboard counters alone

## 3.3 Product success
- customers can be onboarded as tenants and workspaces
- API keys are scoped and revocable
- policy is explainable per request
- namespace risk posture is visible alongside savings

## 3.4 Engineering success
- no major rewrite of proxy core required
- request latency impact from control-plane additions stays operationally negligible
- the repo gains clear package boundaries for control-plane logic
- future billing and enterprise governance can be added without re-architecting the request path

---

# 4) Current validated benchmarks to preserve

These are the baseline guardrails. New work must not regress them.

## Safety and runtime benchmarks
- browser gold-standard task completion: 100%
- browser semantic hits: 0
- browser stale semantic reuse: 0
- modified visual miss rate in nightmare v2: 100%
- critical visual failures in nightmare v2: 0
- cross-user leaks in race scenario: 0
- UUID first-seen upstream miss rate: 100%
- UUID false negatives: 0

## Economics benchmark
- mixed 500-prompt corpus realized savings: 84.6%

## Performance benchmark
- policy / identity logic overhead remains negligible relative to total request latency
- control-plane additions must not materially degrade inline request performance

These are the minimum preservation benchmarks during implementation.

---

# 5) Current architecture gap analysis

## Existing runtime contract
Today the runtime request context is too thin:
- `namespace`
- `bearer_token`
- `request_id`
- `semantic_cache_mode`

This is not enough for SaaS attribution.

## Existing policy model
Today policy is effectively:
- global defaults from settings
- optional global override row in `admin_policy_overrides`

That is useful for operator tuning, but not product-grade policy governance.

## Existing persistence model
Today the main persisted SaaS-facing data is:
- global policy override row(s)
- shadow analytics rows
- semantic cache storage

What is missing is a finance-grade business record of requests.

## Existing dashboard stance
Today the dashboard is read-only and ops-oriented.
That is correct for current maturity, but it is not a control plane yet.

---

# 6) Target architecture to build toward

Metera should become a split-plane system with clean boundaries.

## Data plane
Owns:
- request ingress
- exact cache
- semantic cache
- profiling
- compatibility validation
- policy enforcement
- upstream fallback
- telemetry emission

## Control plane
Owns:
- tenants
- workspaces
- environments
- API keys
- policy versions and assignments
- request ledger
- rollups and analytics
- trials / plans / billing state
- admin and tenant APIs

## Deployment stance
Logical separation now.
Physical separation later if scale justifies it.
Initial co-deployment is fine.

---

# 7) Overall implementation roadmap

## Milestone 1 — Identity and request attribution spine

### Objective
Introduce real SaaS identity without destabilizing the proxy core.

### Deliverables
- create `tenants`
- create `workspaces`
- create `environments`
- create `api_keys`
- create `api_key_lifecycle_log`
- add workspace-scoped API key resolution
- extend runtime request context with SaaS identity
- attach resolved identity to request handling and telemetry

### Required code changes
Add new package boundary:
- `app/controlplane/models/`
- `app/controlplane/repositories/`
- `app/controlplane/auth/`
- `app/controlplane/services/`

Likely first modules:
- `app/controlplane/models/tenant.py`
- `app/controlplane/models/workspace.py`
- `app/controlplane/models/api_key.py`
- `app/controlplane/auth/key_resolver.py`
- `app/controlplane/repositories/api_keys.py`

Likely refactors:
- `app/models/domain.py`
- `app/core/dependencies.py`
- request auth extraction path
- `app/api/routes_chat.py`
- request logging / telemetry surfaces

### Success benchmarks
- every non-admin request resolves to a real `tenant_id`, `workspace_id`, and `api_key_id`
- request context carries identity in-process
- invalid or revoked key handling is correct
- no regression in current chat route behavior
- no measurable material latency regression in request handling

### Exit criteria
We can answer: who sent this request, for which workspace, under which key?

---

## Milestone 2 — Scoped policy service

### Objective
Replace global-only overrides with explainable scoped policy.

### Deliverables
- create `policy_versions`
- create `policy_assignments`
- create `namespace_policy_overrides`
- create `policy_change_log`
- implement policy resolution precedence
- introduce resolved effective policy object for runtime use
- attach policy version to each request context

### Required code changes
Add:
- `app/controlplane/models/policy.py`
- `app/controlplane/repositories/policies.py`
- `app/controlplane/services/policy_resolver.py`
- `app/controlplane/services/policy_snapshot_cache.py`

Refactor:
- `app/core/policy_state.py`
- `app/core/dependencies.py`
- `app/services/proxy_service.py`
- `app/api/routes_admin.py`

### Success benchmarks
- workspace-level policy can differ from tenant default
- namespace-level override can differ from workspace default
- resolved policy is explainable and versioned
- proxy no longer depends on one mutable global override bag
- default behavior remains functionally equivalent for current single-tenant/dev usage

### Exit criteria
We can answer: what policy applied to this request, where did it come from, and why?

---

## Milestone 3 — Request ledger and metering spine

### Objective
Make each request a durable business fact.

### Deliverables
- create `request_ledger`
- create `shadow_savings_ledger`
- create `risk_events`
- persist request outcome, identity, policy, spend, savings, and timings
- keep current Prometheus-style metrics, but separate them from business truth

### Required code changes
Add:
- `app/controlplane/models/ledger.py`
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/risk_events.py`
- `app/controlplane/repositories/shadow_savings.py`
- `app/controlplane/services/metering.py`

Refactor:
- `app/services/proxy_service.py`
- shadow analytics logging path
- cost accounting path

### Success benchmarks
- each request produces a durable ledger record
- realized savings and upstream spend are queryable by tenant/workspace/namespace/model
- policy version is materialized on the request record
- shadow opportunity is queryable without re-deriving from raw request logs
- metrics endpoint remains operational but is no longer treated as finance truth

### Exit criteria
We can answer: what happened on this request, what did it cost, what did it save, and under what policy?

---

## Milestone 4 — Rollups and namespace analytics

### Objective
Turn raw ledger facts into customer-usable summaries.

### Deliverables
- create `daily_usage_rollups`
- create `daily_namespace_rollups`
- build scheduled rollup jobs
- build rule-based risk recommendations
- expose savings + prevented-risk posture per namespace

### Required code changes
Add:
- `app/controlplane/jobs/rollup_usage.py`
- `app/controlplane/jobs/rollup_namespace.py`
- `app/controlplane/services/risk_recommendations.py`
- `app/api/routes_controlplane_analytics.py`

Refactor:
- `dashboard/app.py`
- existing stats summary logic

### Success benchmarks
- namespace-level alert rates are queryable without scanning raw request rows live
- tenant/workspace dashboards can show realized vs shadow savings
- rule-based namespace hardening recommendations work deterministically
- analytics do not run in the hot path

### Exit criteria
We can answer: which namespaces are safe, risky, saving money, or candidates for hardening?

---

## Milestone 5 — Tenant-facing control-plane APIs and dashboard

### Objective
Turn internal ops surfaces into an actual product control plane.

### Deliverables
- add scoped control-plane APIs for tenants, workspaces, keys, policies, analytics
- upgrade dashboard from read-only ops surface to product control surface
- preserve legacy admin routes for internal use until safely deprecated

### Required code changes
Add:
- `app/api/routes_controlplane_tenants.py`
- `app/api/routes_controlplane_workspaces.py`
- `app/api/routes_controlplane_keys.py`
- `app/api/routes_controlplane_policy.py`
- `app/api/routes_controlplane_analytics.py`

Refactor:
- `dashboard/app.py`
- current admin route strategy

### Success benchmarks
- a new tenant and workspace can be created through product APIs
- API keys can be issued, listed, revoked, and audited
- policy can be viewed and changed through scoped APIs
- dashboard surfaces savings, risk, keys, and policy state by tenant/workspace

### Exit criteria
We can onboard and operate a real customer without hand-editing internals.

---

## Milestone 6 — Trials, plans, and billing controls

### Objective
Layer commercial primitives on top of trustworthy metering.

### Deliverables
- create `plans`
- create `subscriptions`
- create `billing_periods`
- create `usage_charges`
- create `invoices`
- implement trial assignment and soft-cap warnings
- reserve hard enforcement for later once UX is proven

### Required code changes
Add:
- `app/controlplane/models/billing.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/services/billing.py`
- `app/controlplane/jobs/close_billing_period.py`
- control-plane billing endpoints

### Success benchmarks
- tenant can be trialed and assigned a plan
- billing period summaries reconcile with ledger truth
- soft-cap warnings appear in UI/API before any hard stops
- billing logic does not mutate ledger truth

### Exit criteria
We can operate a commercial plan without inventing usage after the fact.

---

# 8) Benchmarks by milestone

## Milestone 1 benchmarks
- 100% of authenticated requests map to tenant/workspace/key identity
- request context object carries those IDs end-to-end
- no regression in current tests for chat, security, admin auth, namespace behavior

## Milestone 2 benchmarks
- each request records effective policy version
- workspace and namespace overrides resolve correctly in tests
- no request path depends on direct admin-route logic for policy resolution

## Milestone 3 benchmarks
- 100% of non-streaming requests are ledgered
- ledger totals reconcile with live metrics within expected dual-write tolerance during transition
- realized savings and spend are available by tenant/workspace/namespace

## Milestone 4 benchmarks
- rollups can power dashboard summaries without raw table scans
- namespace alert-rate calculation is deterministic and test-covered
- recommendation logic remains rule-based and explainable

## Milestone 5 benchmarks
- tenant onboarding path works through product APIs
- key lifecycle events are audited
- policy and analytics views are scoped, not global-only

## Milestone 6 benchmarks
- billing-period closeout is reproducible from rollups / ledger
- soft-cap notifications work before hard-cap enforcement exists
- invoices/exports can be generated from summarized usage

---

# 9) Architectural decisions already locked

## Decision 1
Do not rewrite `ProxyService` as a new system.
Refactor seams around it.

## Decision 2
Do not make the dashboard the write path for core business state.
Use control-plane services and repositories.

## Decision 3
Do not leave policy as a loose JSON blob.
Core fields must be typed and versioned.

## Decision 4
Do not build billing before the request ledger exists and is trusted.

## Decision 5
Do not put analytics, billing, or heavy joins in the hot request path.

## Decision 6
Do not treat namespace as a tenant boundary.
It is a classification and policy-routing concept.

## Decision 7
Do not make the browser extension the platform foundation.
The gateway and control plane are the product foundation.

---

# 10) Proposed package and module evolution

## New package root
Create:
- `app/controlplane/`

## Suggested internal structure
- `app/controlplane/models/`
- `app/controlplane/repositories/`
- `app/controlplane/services/`
- `app/controlplane/jobs/`
- `app/controlplane/auth/`

## Runtime contract evolution
`ProxyContext` should evolve from:
- namespace
- bearer_token
- request_id
- semantic_cache_mode

To at least:
- tenant_id
- tenant_slug
- workspace_id
- workspace_slug
- environment_id
- api_key_id
- namespace
- request_id
- effective_policy_version_id
- effective_policy_mode
- semantic_cache_mode

That context becomes the boundary object between auth, policy, metering, and runtime execution.

---

# 11) Implementation risks and pushback points

## Risk 1 — skipping identity and jumping to dashboard work
Bad idea.
Without identity, all later analytics and billing are contaminated.

## Risk 2 — reusing current global policy store as the long-term model
Bad idea.
`admin_policy_overrides` is a prototype convenience, not a SaaS policy architecture.

## Risk 3 — forcing physical microservice splits too early
Bad idea.
Logical separation now is enough.
Operational sprawl would slow delivery.

## Risk 4 — treating metrics as accounting truth
Bad idea.
Prometheus counters are not a finance-grade ledger.

## Risk 5 — putting DB-heavy resolution in the request path
Bad idea.
We must cache key metadata and policy snapshots.

## Risk 6 — billing before ledger correctness
Bad idea.
That creates instant commercial and trust debt.

---

# 12) Immediate execution plan

## Phase 0 — repo preparation
Before coding the full SaaS spine:
- create the `app/controlplane/` package boundary
- decide on persistence approach for new tables and migrations
- keep current behavior working in local/dev mode with a seeded internal tenant/workspace

## First coding slice
Implement Milestone 1 first slice:
1. add control-plane identity models and repositories
2. add workspace-scoped API key hashing/resolution
3. extend `ProxyContext`
4. thread resolved identity through chat request handling
5. expose identity in telemetry / logging only where appropriate
6. preserve current namespace semantics

## Second coding slice
Immediately after:
1. add policy version tables
2. add policy assignments
3. implement policy resolver service
4. replace direct global policy bag reads with resolved effective policy objects

This is the narrowest correct start.

---

# 13) Definition of done for Metera v1

Metera v1 is done when all of the following are true:
- protected lanes remain correctness-first and validated
- low-risk text lanes still preserve strong savings
- every request is attributable to tenant/workspace/key/namespace/policy
- scoped policy exists and is explainable
- request outcomes are ledgered durably
- rollups power namespace risk and savings views
- tenants can be onboarded and managed through product APIs
- trials/plans can be applied without architectural rework

If any of those are missing, the system is still a strong gateway prototype, not a finished SaaS control platform.

---

# 14) Final stance

The correct path is not more safety-blocker work and not browser-extension-first work.
The correct path is to productize the validated gateway by building the SaaS spine around it in this order:

1. identity
2. scoped policy
3. ledger
4. analytics rollups
5. control-plane APIs and dashboard
6. billing and trials

That is the shortest path that preserves correctness, keeps the proxy fast, and results in a real business platform instead of a promising prototype.

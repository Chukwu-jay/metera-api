# CONTROL_PLANE_ARCHITECTURE_V1

## Purpose

Define the v1 SaaS control-plane architecture for Metera after Phase 4.5 closure.

This document locks:
- service boundaries
- core identity model
- policy resolution model
- metering / savings ledger design
- analytics scope
- rollout sequence
- what we will deliberately **not** overbuild yet

It reflects a merged position:
- keep a strong logical separation between data plane and control plane
- avoid premature distributed-systems complexity in the first rollout
- preserve agility while building the real product spine correctly

---

# 1) Core architecture decision

Metera will use a **split-plane architecture logically**, but may be **co-deployed initially**.

## Logical separation

### Data plane
The data plane is the inline proxy path that handles every model request.

It owns:
- request ingress
- exact cache
- semantic cache
- request profiling
- compatibility validation
- safety enforcement
- upstream fallback
- per-request telemetry emission

### Control plane
The control plane is the SaaS management and accounting system.

It owns:
- tenants / workspaces / API keys
- policy state and policy versioning
- usage metering
- realized savings and shadow savings accounting
- namespace risk analytics
- dashboard and admin API
- trial / billing / plan state

## Deployment stance for v1

These planes should be **separate in code and data model now**, but they do **not** need to be physically split into independently scaled services on day one.

Recommended initial stance:
- allow co-deployment in the same infrastructure stack
- preserve clean module boundaries and explicit interfaces
- avoid per-request network hops to a remote control-plane API

Reason:
This keeps iteration fast without collapsing product architecture into one global mutable app.

---

# 2) Architectural principles

## 2.1 The proxy must stay fast and deterministic
The data plane must not perform expensive control-plane lookups on every request.

Per-request dependency on central management APIs is forbidden.

Allowed:
- in-memory policy snapshots
- local auth metadata cache
- TTL-based config refresh
- async telemetry delivery

Not allowed:
- per-request admin DB queries
- analytical joins in the hot path
- per-request control-plane network dependency

## 2.2 The identity spine is non-negotiable
Every request must be attributable to:
- tenant
- workspace
- API key
- namespace
- effective policy version

Without this:
- savings attribution is not trustworthy
- safety isolation is not trustworthy
- billing is not trustworthy
- policy governance is not trustworthy

## 2.3 Usage facts are ledger events, not dashboard counters
Financial and usage truth must come from append-only metering events and rollups derived from them.

Do not build business truth from mutable dashboard state.

## 2.4 Safety and economics must be visible together
Metera’s moat is not just reuse rate.

Metera must continuously answer:
1. what did we save?
2. what did we spend?
3. what did we avoid serving because safety policy blocked it?
4. what more could be saved under a different policy?

## 2.5 Governance features are also sales features
Namespace risk analytics are not just an internal governance tool.
They are also how Metera proves that it prevents costly failures while preserving savings.

---

# 3) v1 system model

## 3.1 Identity hierarchy

Canonical hierarchy:

`tenant -> workspace -> api_key -> namespace`

### Tenant
A customer account / organization.

### Workspace
A logical environment or application boundary within a tenant.
Examples:
- production assistant traffic
- support bot traffic
- browser automation traffic
- internal experimentation workspace

### API key
A credential scoped to a workspace and environment.

### Namespace
A traffic-classification label inside a workspace.
Examples:
- `faq-general`
- `faq-billing`
- `browser-sales-crm`
- `support-technical`

Important rule:
**namespace is not a tenant boundary**.
It is a classification and policy-routing concept.

---

# 4) Control-plane responsibilities

The control plane owns six product-critical domains.

## 4.1 Tenant registry
Owns:
- tenant creation and lifecycle
- workspace creation and lifecycle
- environment metadata
- API key issuance and revocation
- plan and trial linkage

## 4.2 Policy service
Owns:
- policy defaults
- tenant-level policy
- workspace-level policy
- namespace-level policy overrides
- policy versioning
- rollout flags
- effective policy resolution metadata

## 4.3 Metering / savings ledger
Owns:
- per-request financial facts
- realized live savings
- upstream spend
- shadow opportunity
- cache outcome counts
- model / namespace / workspace rollups

## 4.4 Namespace risk analytics
Owns:
- shadow alert rates
- mismatch categories
- high-risk namespace identification
- hardening recommendations
- customer-facing “unsafe reuse prevented” evidence

## 4.5 Billing and plan enforcement
Owns:
- trials
- plan limits
- soft-cap warnings
- overage policies
- billing-period usage aggregation

## 4.6 Admin / dashboard API
Owns:
- management endpoints
- tenant views
- policy views
- savings views
- risk views
- key lifecycle views
- audit logs

---

# 5) Data-plane responsibilities

The data plane remains the runtime decision engine.

It owns:
- request authentication using locally cached key metadata
- namespace resolution
- request profiling
- exact cache evaluation
- semantic lookup
- compatibility validation
- policy enforcement
- upstream fallback
- telemetry emission

It does **not** own:
- tenant CRUD
- billing logic
- dashboard logic
- long-horizon analytics
- pricing rules

The data plane should produce facts, not product reports.

---

# 6) Policy model

## 6.1 Policy precedence

Effective policy resolution precedence for v1:

1. global defaults
2. plan defaults
3. tenant defaults
4. workspace defaults
5. namespace overrides
6. request-level safe overrides (e.g. exact-only / semantic opt-out)
7. immutable runtime safety precedence in the proxy

Runtime safety precedence must still win where required.

Examples:
- visual hard alignment when enabled
- strict namespace enforcement
- identity-sensitive strict handling where configured
- agentic / browser hardening

## 6.2 Policy versioning

Every resolved effective policy must be explainable.

Each request should be attributable to:
- `policy_version`
- `policy_source`
- `resolved_reasons`

This is required for:
- debugging
- customer support
- analytics interpretation
- billing disputes
- rollout audits

## 6.3 Typed core policy fields

Do not leave v1 policy as a totally untyped JSON blob.

Typed first-class fields should include at minimum:
- `semantic_enabled`
- `semantic_threshold`
- `semantic_shadow_threshold`
- `semantic_max_temperature`
- `identity_guard_enabled`
- `identity_strict_mode_enabled`
- `identity_partitioning_enabled`
- `multimodal_hard_alignment_enabled`
- `policy_timing_breakdown_enabled`
- `strict_namespace_prefixes`
- `high_risk_namespace_prefixes`

JSON extension fields are acceptable for future flexibility, but the core knobs must be explicit.

---

# 7) Metering and ledger design

## 7.1 Principle

Metering is a first-class product primitive.

Metera’s economic moat depends on a trustworthy ledger that can answer:
- realized savings
- upstream spend
- shadow savings opportunity
- risk-adjusted savings by namespace
- policy-change impact over time

## 7.2 Event model

Use an append-only request ledger.

Minimum per-request recorded facts:
- request_id
- observed_at
- tenant_id
- workspace_id
- api_key_id
- namespace
- model
- cache_outcome
- semantic_bypass_reason
- estimated_upstream_cost_usd
- estimated_realized_savings_usd
- estimated_shadow_savings_usd
- policy_version
- latency metrics
- modality / identity / agentic flags

## 7.3 Event categories

At minimum, support these logical event types:
- `request_observed`
- `cache_exact_hit`
- `cache_semantic_hit`
- `cache_miss`
- `shadow_opportunity_detected`
- `shadow_regression_alert`
- `policy_changed`
- `api_key_created`
- `api_key_revoked`

## 7.4 Rollups

Build derived rollups for:
- daily tenant usage
- daily workspace usage
- daily namespace usage
- daily model usage
- realized vs shadow savings
- mismatch / alert rates

These rollups feed:
- dashboards
- billing summaries
- risk recommendations

---

# 8) Namespace risk analytics

## 8.1 Purpose

Namespace analytics are both:
- an internal governance capability
- a customer-facing proof surface

They should explain not just savings, but prevented unsafe reuse.

## 8.2 Core metrics per namespace

Track at least:
- total requests
- exact hit rate
- semantic hit rate
- miss rate
- realized savings
- shadow opportunity
- shadow regression alert rate
- mismatch categories
- visual / agentic / identity-sensitive request rates
- effective policy mode

## 8.3 Recommendations engine

Keep v1 rule-based.

Example rules:
- if shadow alert rate > 5% over meaningful sample volume -> flag for review
- if billing / identity-sensitive patterns repeatedly mismatch -> recommend strict
- if traffic is predominantly visual or agentic -> recommend hard

Do not build an ML recommendation system yet.

## 8.4 Customer-facing framing

The dashboard should be able to present both:
- savings realized
- unsafe reuse prevented

Engineering wording should stay precise.

Preferred internal phrasing:
- unsafe reuse prevented
- protected-lane hard misses enforced
- high-risk replay avoided

Marketing or sales can simplify the language later, but the underlying metrics must remain technically honest.

---

# 9) Billing and plan enforcement

## 9.1 Billing dependency rule

Billing must consume ledger truth.

Billing must **not** infer usage from raw logs or mutable dashboard counters.

## 9.2 v1 plan enforcement order

Recommended rollout order:
1. usage attribution
2. savings ledger
3. dashboard visibility
4. soft-cap notifications
5. hard caps only after product UX is ready

## 9.3 Soft-cap before hard-cap

Do not start with a harsh hard stop.

First implement:
- dashboard warnings
- admin alerts
- response metadata warnings near threshold

Example:
- notify at 80% of included savings or usage allotment
- notify again at 95%
- hard enforcement later if product behavior is well designed

Reason:
A sudden hard billing cutoff can create poor agent behavior and support pain.

---

# 10) Initial deployment recommendation

## 10.1 v1 deployment shape

Recommended initial components:
- `metera-proxy` — data-plane runtime
- `metera-control` — control-plane API modules
- `metera-dashboard` — UI / operator view
- `metera-jobs` — rollups, analytics, and billing jobs

## 10.2 Co-deployment is acceptable initially

These may share infrastructure initially if that speeds delivery.

Examples of acceptable v1 deployment:
- proxy and control-plane services in one stack
- shared Postgres for control-plane state and metering
- single deployment repo

But maintain:
- separate modules
- separate schemas / service boundaries
- separate responsibility ownership

## 10.3 When to split physically

Split into independently scaled services when one or more become true:
- proxy traffic volume creates different scaling needs than admin/analytics
- operational blast radius becomes unacceptable
- control-plane queries materially affect proxy performance
- background jobs begin to compete with inline request latency

---

# 11) Core schema direction

## 11.1 Identity tables
- `tenants`
- `workspaces`
- `api_keys`
- `environments`

## 11.2 Policy tables
- `policy_versions`
- `policy_assignments`
- `namespace_policy_overrides`
- `policy_change_log`

## 11.3 Metering tables
- `request_ledger`
- `daily_usage_rollups`
- `daily_namespace_rollups`
- `shadow_savings_ledger`
- `risk_events`

## 11.4 Billing tables
- `plans`
- `subscriptions`
- `billing_periods`
- `usage_charges`
- `invoices`

## 11.5 Audit tables
- `admin_audit_log`
- `api_key_lifecycle_log`
- `policy_change_log`

---

# 12) Request-context contract

Every request in the data plane should carry enough resolved identity and policy context to make downstream reasoning and analytics trustworthy.

Minimum internal request context for v1:
- `tenant_id`
- `workspace_id`
- `api_key_id`
- `namespace`
- `policy_version`
- `effective_policy_mode`

Preferred additional fields:
- `plan_id`
- `workspace_environment`
- `resolved_policy_reasons`
- `tenant_slug`

This request context should be attachable to telemetry without additional expensive joins.

---

# 13) Interaction with current repo state

The existing repo already contains early scaffolding for:
- admin routes
- global policy state
- a dashboard
- stats and shadow analytics surfaces

That is useful, but it is not yet SaaS-grade control-plane design.

Current gaps relative to this v1 architecture:
- global policy state instead of tenant/workspace-scoped policy
- no true tenant/workspace/key identity spine
- dashboard is effectively read-only ops UI, not product control plane
- no append-only per-request financial ledger tied to tenant identity
- no true billing / trial model yet

The next iteration should evolve current scaffolding, not discard it.

---

# 14) Recommended implementation order

## Phase A — Identity foundation
Build first:
- tenants
- workspaces
- API keys
- request authentication / resolution
- request context attribution

Goal:
Every request can be attributed to tenant, workspace, key, namespace, and policy version.

## Phase B — Scoped policy service
Build next:
- tenant-level policy
- workspace-level policy
- namespace overrides
- policy versions
- effective policy resolution

Goal:
Replace the current global-only policy model with scoped policy.

## Phase C — Request ledger
Build next:
- append-only request ledger
- savings and spend fields
- shadow-opportunity logging
- daily rollups

Goal:
Establish the financial spine.

## Phase D — Analytics and dashboard
Build next:
- tenant overview
- workspace usage view
- namespace risk page
- savings vs shadow opportunity view
- key lifecycle views

Goal:
Turn the system into a usable SaaS control surface.

## Phase E — Billing and plan controls
Build after ledger trust exists:
- trials
- plans
- soft-cap warnings
- invoice / export flows
- hard enforcement later

---

# 15) Anti-goals

To keep v1 focused, avoid these mistakes:

## 15.1 Do not build full microservices too early
Logical separation now; physical sprawl later.

## 15.2 Do not let the dashboard define the architecture
The ledger and policy model define the architecture.
The dashboard is a surface over them.

## 15.3 Do not make namespace the account boundary
Namespace is classification, not ownership.

## 15.4 Do not let pricing design outrun metering truth
Billing can only be trusted after attribution and ledger correctness are in place.

## 15.5 Do not optimize for extension UX by weakening the safety spine
The extension is a product surface, not the architectural foundation.

---

# 16) Final engineering stance

Metera v1 should be built as a **policy-enforced AI gateway with a finance-grade control plane**.

That means:
- the proxy remains the fast inline enforcement engine
- the control plane owns identity, policy, metering, analytics, and billing
- safety and savings are measured together
- logical split-plane boundaries are established now
- physical separation can wait until scale justifies it

This gives Metera the right balance of:
- speed to market
- correctness
- SaaS readiness
- long-term maintainability
- a defensible economic moat

# CONTROL_PLANE_SCHEMA_V1

## Purpose

Define the initial control-plane schema for Metera v1.

This document translates `CONTROL_PLANE_ARCHITECTURE_V1.md` into concrete entities, relationships, and implementation guidance.

It is intentionally scoped to the first real SaaS spine:
- tenant/workspace/key identity
- policy versioning and scoped assignment
- append-only request ledger
- namespace rollups
- trial / plan / billing scaffolding
- auditability

This is not the final enterprise schema.
It is the minimum schema that can support:
- trustworthy savings attribution
- trustworthy safety attribution
- trustworthy policy explainability
- SaaS onboarding and plan enforcement

---

# 1) Design goals

The schema must support:

1. **Request attribution**
   Every request must be attributable to tenant, workspace, key, namespace, and policy version.

2. **Policy explainability**
   We must be able to explain what effective policy applied and why.

3. **Financial truth**
   Savings/spend must come from append-only ledger facts, not mutable counters.

4. **Operational scalability**
   Hot-path proxy lookups should use cached metadata, but the source of truth still needs a clean relational model.

5. **Incremental rollout**
   The schema should support starting simple while leaving room for later RBAC, enterprise controls, and billing complexity.

---

# 2) Entity relationship overview

## Core relationship graph

```text
Tenant
  ├── Workspace
  │     ├── Environment
  │     ├── ApiKey
  │     ├── PolicyAssignment
  │     ├── NamespacePolicyOverride
  │     ├── RequestLedger
  │     └── DailyNamespaceRollup
  ├── Subscription
  ├── BillingPeriod
  └── AdminAuditLog

PolicyVersion
  ├── PolicyAssignment
  └── RequestLedger

ApiKey
  ├── RequestLedger
  └── ApiKeyLifecycleLog

RequestLedger
  ├── RiskEvent
  └── ShadowSavingsLedger
```

## Canonical identity hierarchy

```text
tenant -> workspace -> api_key -> namespace
```

Important:
- `namespace` is not a top-level table in the ownership hierarchy
- it is a scoped classification label within a workspace

---

# 3) Core identity tables

## 3.1 `tenants`

Represents a customer account / organization.

### Columns
- `id` UUID PK
- `slug` TEXT UNIQUE NOT NULL
- `name` TEXT NOT NULL
- `status` TEXT NOT NULL
  - expected values: `active`, `trialing`, `suspended`, `deleted`
- `plan_id` UUID NULL FK -> `plans.id`
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL
- `deleted_at` TIMESTAMPTZ NULL

### Notes
- `slug` should be human-usable and stable enough for URLs/admin surfaces
- soft-delete is preferable to hard-delete for billing/audit reasons

---

## 3.2 `workspaces`

Represents an application or environment boundary within a tenant.

### Columns
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `slug` TEXT NOT NULL
- `name` TEXT NOT NULL
- `status` TEXT NOT NULL
  - expected values: `active`, `paused`, `archived`
- `default_environment_id` UUID NULL FK -> `environments.id`
- `metadata` JSONB NOT NULL DEFAULT `{}`
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

### Constraints
- UNIQUE (`tenant_id`, `slug`)

### Notes
Examples:
- `prod-support`
- `prod-browser`
- `sandbox`

A workspace is the correct scope for:
- API keys
- policy defaults
- cost attribution
- namespace analytics

---

## 3.3 `environments`

Represents environment metadata under a workspace.

### Columns
- `id` UUID PK
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `name` TEXT NOT NULL
  - expected examples: `prod`, `staging`, `dev`
- `status` TEXT NOT NULL DEFAULT `active`
- `metadata` JSONB NOT NULL DEFAULT `{}`
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

### Constraints
- UNIQUE (`workspace_id`, `name`)

### Notes
This table is intentionally light in v1.
It mainly helps with attribution, future quota scoping, and cleaner key management.

---

## 3.4 `api_keys`

Represents a workspace-scoped credential.

### Columns
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `environment_id` UUID NULL FK -> `environments.id`
- `key_prefix` TEXT NOT NULL UNIQUE
- `key_hash` TEXT NOT NULL
- `display_name` TEXT NOT NULL
- `status` TEXT NOT NULL
  - expected values: `active`, `revoked`, `expired`
- `last_used_at` TIMESTAMPTZ NULL
- `expires_at` TIMESTAMPTZ NULL
- `metadata` JSONB NOT NULL DEFAULT `{}`
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL
- `revoked_at` TIMESTAMPTZ NULL

### Indexes
- INDEX (`workspace_id`, `status`)
- INDEX (`tenant_id`, `status`)

### Notes
- Store only hash + prefix, never full plaintext keys
- `key_prefix` enables fast lookup before hash verification
- later we can add scopes/permissions, but not needed for v1

---

# 4) Policy tables

## 4.1 `policy_versions`

Represents immutable policy definitions.

### Columns
- `id` UUID PK
- `scope_type` TEXT NOT NULL
  - expected values: `global`, `plan`, `tenant`, `workspace`, `namespace`
- `scope_ref_id` UUID NULL
  - nullable because some scopes like `global` may not need a concrete FK
- `version_number` INTEGER NOT NULL
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `semantic_enabled` BOOLEAN NOT NULL
- `semantic_threshold` DOUBLE PRECISION NOT NULL
- `semantic_shadow_threshold` DOUBLE PRECISION NOT NULL
- `semantic_max_temperature` DOUBLE PRECISION NOT NULL
- `identity_guard_enabled` BOOLEAN NOT NULL
- `identity_strict_mode_enabled` BOOLEAN NOT NULL
- `identity_partitioning_enabled` BOOLEAN NOT NULL
- `multimodal_hard_alignment_enabled` BOOLEAN NOT NULL
- `policy_timing_breakdown_enabled` BOOLEAN NOT NULL
- `strict_namespace_prefixes` TEXT[] NOT NULL DEFAULT '{}'
- `high_risk_namespace_prefixes` TEXT[] NOT NULL DEFAULT '{}'
- `extension_fields` JSONB NOT NULL DEFAULT '{}'
- `created_by` TEXT NULL
- `change_reason` TEXT NULL
- `created_at` TIMESTAMPTZ NOT NULL

### Constraints
- UNIQUE (`scope_type`, `scope_ref_id`, `version_number`)

### Notes
This table is immutable by design.
Every policy change should create a new version row.

---

## 4.2 `policy_assignments`

Maps a scope to the currently active policy version.

### Columns
- `id` UUID PK
- `tenant_id` UUID NULL FK -> `tenants.id`
- `workspace_id` UUID NULL FK -> `workspaces.id`
- `environment_id` UUID NULL FK -> `environments.id`
- `scope_type` TEXT NOT NULL
  - expected values: `global`, `plan`, `tenant`, `workspace`
- `policy_version_id` UUID NOT NULL FK -> `policy_versions.id`
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `status` TEXT NOT NULL DEFAULT `active`
- `created_at` TIMESTAMPTZ NOT NULL

### Notes
We separate version storage from active assignment so we can:
- version safely
- schedule policy changes later if needed
- preserve a historical trail

---

## 4.3 `namespace_policy_overrides`

Stores namespace-specific policy overrides within a workspace.

### Columns
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `environment_id` UUID NULL FK -> `environments.id`
- `namespace` TEXT NOT NULL
- `policy_version_id` UUID NOT NULL FK -> `policy_versions.id`
- `status` TEXT NOT NULL DEFAULT `active`
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

### Constraints
- UNIQUE (`workspace_id`, `environment_id`, `namespace`, `status`) WHERE status = 'active'

### Notes
This is how `faq-billing` or `browser-*` style namespace overrides become explicit SaaS control-plane state instead of implicit code-only behavior.

---

## 4.4 `policy_change_log`

Explicit audit trail for human or system-triggered policy changes.

### Columns
- `id` UUID PK
- `tenant_id` UUID NULL
- `workspace_id` UUID NULL
- `namespace` TEXT NULL
- `previous_policy_version_id` UUID NULL FK -> `policy_versions.id`
- `new_policy_version_id` UUID NOT NULL FK -> `policy_versions.id`
- `change_actor_type` TEXT NOT NULL
  - expected values: `platform_admin`, `tenant_admin`, `system`
- `change_actor_id` TEXT NULL
- `change_reason` TEXT NULL
- `source` TEXT NOT NULL
  - expected values: `admin_ui`, `api`, `migration`, `system_recommendation`
- `created_at` TIMESTAMPTZ NOT NULL

---

# 5) Request ledger and analytics tables

## 5.1 `request_ledger`

This is the financial and operational spine.

Append-only.
One row per request.

### Columns
- `id` UUID PK
- `request_id` TEXT NOT NULL UNIQUE
- `observed_at` TIMESTAMPTZ NOT NULL
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `environment_id` UUID NULL FK -> `environments.id`
- `api_key_id` UUID NOT NULL FK -> `api_keys.id`
- `namespace` TEXT NOT NULL
- `model` TEXT NOT NULL
- `provider` TEXT NULL
- `cache_outcome` TEXT NOT NULL
  - expected values: `exact_hit`, `semantic_hit`, `miss`
- `semantic_bypass_reason` TEXT NULL
- `effective_policy_version_id` UUID NULL FK -> `policy_versions.id`
- `effective_policy_mode` TEXT NULL
  - expected values: `hard`, `soft`, `exact_only`
- `has_visual_context` BOOLEAN NOT NULL DEFAULT FALSE
- `has_dom_context` BOOLEAN NOT NULL DEFAULT FALSE
- `is_agentic` BOOLEAN NOT NULL DEFAULT FALSE
- `identity_sensitive` BOOLEAN NOT NULL DEFAULT FALSE
- `prompt_tokens` INTEGER NOT NULL DEFAULT 0
- `completion_tokens` INTEGER NOT NULL DEFAULT 0
- `total_tokens` INTEGER NOT NULL DEFAULT 0
- `estimated_upstream_cost_usd` NUMERIC(18,8) NOT NULL DEFAULT 0
- `estimated_realized_savings_usd` NUMERIC(18,8) NOT NULL DEFAULT 0
- `estimated_shadow_savings_usd` NUMERIC(18,8) NOT NULL DEFAULT 0
- `request_latency_ms` DOUBLE PRECISION NOT NULL DEFAULT 0
- `profile_build_ms` DOUBLE PRECISION NOT NULL DEFAULT 0
- `semantic_lookup_ms` DOUBLE PRECISION NOT NULL DEFAULT 0
- `compatibility_validation_ms` DOUBLE PRECISION NOT NULL DEFAULT 0
- `upstream_ms` DOUBLE PRECISION NOT NULL DEFAULT 0
- `metadata` JSONB NOT NULL DEFAULT '{}'

### Indexes
- INDEX (`tenant_id`, `observed_at`)
- INDEX (`workspace_id`, `observed_at`)
- INDEX (`api_key_id`, `observed_at`)
- INDEX (`namespace`, `observed_at`)
- INDEX (`model`, `observed_at`)
- INDEX (`cache_outcome`, `observed_at`)

### Notes
This row should contain enough materialized attribution context to avoid expensive retrospective joins.

---

## 5.2 `shadow_savings_ledger`

Stores shadow opportunity events that did not qualify for live replay.

### Columns
- `id` UUID PK
- `request_ledger_id` UUID NOT NULL FK -> `request_ledger.id`
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `namespace` TEXT NOT NULL
- `similarity_score` DOUBLE PRECISION NOT NULL
- `live_threshold` DOUBLE PRECISION NOT NULL
- `shadow_threshold` DOUBLE PRECISION NOT NULL
- `calculated_savings_usd` NUMERIC(18,8) NOT NULL DEFAULT 0
- `created_at` TIMESTAMPTZ NOT NULL

### Notes
This makes the “safety tax” concrete and queryable.

---

## 5.3 `risk_events`

Captures high-signal safety or compatibility events.

### Columns
- `id` UUID PK
- `request_ledger_id` UUID NOT NULL FK -> `request_ledger.id`
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `namespace` TEXT NOT NULL
- `event_type` TEXT NOT NULL
  - expected values: `shadow_regression_alert`, `entity_mismatch`, `identity_mismatch`, `visual_hard_miss`, `policy_hard_enforcement`
- `severity` TEXT NOT NULL
  - expected values: `info`, `warning`, `critical`
- `reason` TEXT NULL
- `payload` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL

### Notes
This table exists because not every risk signal should be re-derived from raw request rows.

---

## 5.4 `daily_usage_rollups`

Daily aggregate view per tenant/workspace.

### Columns
- `id` UUID PK
- `rollup_date` DATE NOT NULL
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `request_count` BIGINT NOT NULL DEFAULT 0
- `exact_hit_count` BIGINT NOT NULL DEFAULT 0
- `semantic_hit_count` BIGINT NOT NULL DEFAULT 0
- `miss_count` BIGINT NOT NULL DEFAULT 0
- `upstream_cost_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `realized_savings_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `shadow_savings_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

### Constraints
- UNIQUE (`rollup_date`, `tenant_id`, `workspace_id`)

---

## 5.5 `daily_namespace_rollups`

Daily aggregate view per namespace.

### Columns
- `id` UUID PK
- `rollup_date` DATE NOT NULL
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `namespace` TEXT NOT NULL
- `request_count` BIGINT NOT NULL DEFAULT 0
- `exact_hit_count` BIGINT NOT NULL DEFAULT 0
- `semantic_hit_count` BIGINT NOT NULL DEFAULT 0
- `miss_count` BIGINT NOT NULL DEFAULT 0
- `shadow_alert_count` BIGINT NOT NULL DEFAULT 0
- `visual_request_count` BIGINT NOT NULL DEFAULT 0
- `agentic_request_count` BIGINT NOT NULL DEFAULT 0
- `identity_sensitive_request_count` BIGINT NOT NULL DEFAULT 0
- `upstream_cost_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `realized_savings_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `shadow_savings_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

### Constraints
- UNIQUE (`rollup_date`, `workspace_id`, `namespace`)

### Notes
This is the main source for dashboard risk and savings summaries.

---

# 6) Billing and plan tables

## 6.1 `plans`

Defines commercial plan templates.

### Columns
- `id` UUID PK
- `code` TEXT NOT NULL UNIQUE
- `name` TEXT NOT NULL
- `status` TEXT NOT NULL DEFAULT `active`
- `monthly_base_price_usd` NUMERIC(18,2) NOT NULL DEFAULT 0
- `included_requests` BIGINT NULL
- `included_upstream_cost_usd` NUMERIC(18,2) NULL
- `included_realized_savings_usd` NUMERIC(18,2) NULL
- `soft_cap_threshold_ratio` DOUBLE PRECISION NOT NULL DEFAULT 0.8
- `hard_cap_enabled` BOOLEAN NOT NULL DEFAULT FALSE
- `metadata` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

### Notes
Keep plan modeling simple in v1.
Pricing sophistication can come later.

---

## 6.2 `subscriptions`

Maps tenants to plans.

### Columns
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `plan_id` UUID NOT NULL FK -> `plans.id`
- `status` TEXT NOT NULL
  - expected values: `trialing`, `active`, `past_due`, `canceled`
- `trial_ends_at` TIMESTAMPTZ NULL
- `current_period_start` TIMESTAMPTZ NOT NULL
- `current_period_end` TIMESTAMPTZ NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

---

## 6.3 `billing_periods`

Closed or open usage periods for billing summarization.

### Columns
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `subscription_id` UUID NOT NULL FK -> `subscriptions.id`
- `period_start` TIMESTAMPTZ NOT NULL
- `period_end` TIMESTAMPTZ NOT NULL
- `status` TEXT NOT NULL
  - expected values: `open`, `closing`, `closed`
- `request_count` BIGINT NOT NULL DEFAULT 0
- `upstream_cost_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `realized_savings_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `shadow_savings_usd_total` NUMERIC(18,8) NOT NULL DEFAULT 0
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

---

## 6.4 `usage_charges`

Line-itemized usage outcomes for billing/export.

### Columns
- `id` UUID PK
- `billing_period_id` UUID NOT NULL FK -> `billing_periods.id`
- `charge_type` TEXT NOT NULL
  - expected values: `base_fee`, `request_overage`, `managed_spend`, `savings_share`, `manual_adjustment`
- `description` TEXT NOT NULL
- `amount_usd` NUMERIC(18,8) NOT NULL
- `metadata` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL

---

## 6.5 `invoices`

Invoice/export stub for v1.

### Columns
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `billing_period_id` UUID NOT NULL FK -> `billing_periods.id`
- `external_invoice_ref` TEXT NULL
- `status` TEXT NOT NULL
  - expected values: `draft`, `issued`, `paid`, `void`
- `subtotal_usd` NUMERIC(18,8) NOT NULL DEFAULT 0
- `total_usd` NUMERIC(18,8) NOT NULL DEFAULT 0
- `issued_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

---

# 7) Audit tables

## 7.1 `admin_audit_log`

Tracks admin/control-plane actions.

### Columns
- `id` UUID PK
- `tenant_id` UUID NULL
- `workspace_id` UUID NULL
- `actor_type` TEXT NOT NULL
  - expected values: `platform_admin`, `tenant_admin`, `system`
- `actor_id` TEXT NULL
- `action` TEXT NOT NULL
- `target_type` TEXT NOT NULL
- `target_id` TEXT NULL
- `payload` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL

---

## 7.2 `api_key_lifecycle_log`

Tracks issuance/revocation/rotation events.

### Columns
- `id` UUID PK
- `api_key_id` UUID NOT NULL FK -> `api_keys.id`
- `tenant_id` UUID NOT NULL FK -> `tenants.id`
- `workspace_id` UUID NOT NULL FK -> `workspaces.id`
- `event_type` TEXT NOT NULL
  - expected values: `created`, `rotated`, `revoked`, `expired`
- `actor_type` TEXT NOT NULL
- `actor_id` TEXT NULL
- `payload` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL

---

# 8) Effective policy resolution model

This is not just schema; it’s how the schema is meant to be used.

## Resolution chain
For a request in workspace `W`, namespace `N`:

1. global default policy
2. plan-level policy if defined
3. tenant-level active assignment if defined
4. workspace-level active assignment if defined
5. namespace override if defined
6. request-level safe override (e.g. exact-only)
7. runtime safety precedence in proxy

## What gets materialized into `request_ledger`
At request time, record:
- `effective_policy_version_id`
- `effective_policy_mode`
- `semantic_bypass_reason`
- modality / identity flags

That materialization is critical.
It avoids fragile future joins and makes per-request behavior explainable.

---

# 9) Request-context contract

The proxy should internally resolve and carry at least:
- `tenant_id`
- `workspace_id`
- `environment_id`
- `api_key_id`
- `namespace`
- `effective_policy_version_id`
- `effective_policy_mode`

Preferred additional request context:
- `tenant_slug`
- `workspace_slug`
- `plan_id`
- `resolved_policy_reasons`

This request context is the bridge between control plane and data plane.

---

# 10) Migration / implementation order

## Phase A — Identity tables
Build first:
- `tenants`
- `workspaces`
- `environments`
- `api_keys`
- `api_key_lifecycle_log`

## Phase B — Policy tables
Build next:
- `policy_versions`
- `policy_assignments`
- `namespace_policy_overrides`
- `policy_change_log`

## Phase C — Ledger
Build next:
- `request_ledger`
- `shadow_savings_ledger`
- `risk_events`

## Phase D — Rollups
Build next:
- `daily_usage_rollups`
- `daily_namespace_rollups`

## Phase E — Billing scaffolding
Build next:
- `plans`
- `subscriptions`
- `billing_periods`
- `usage_charges`
- `invoices`

## Phase F — Admin audit completeness
Build / expand:
- `admin_audit_log`

---

# 11) What not to do

## 11.1 Do not model everything as JSONB
JSONB is useful for extension fields and payloads.
It is not a substitute for a real schema.

## 11.2 Do not make mutable counters the source of truth
Dashboard counters are derivatives.
Ledger facts are truth.

## 11.3 Do not delay policy versioning
If you skip versioning, debugging and billing disputes become painful fast.

## 11.4 Do not tie billing directly to raw request logs without rollups
You need both append-only facts and stable billing-period summaries.

## 11.5 Do not put namespace ownership in a top-level global table yet
Namespace is workspace-scoped and should remain so in v1.

---

# 12) Recommended first DDL milestone

If we want the shortest path to real SaaS structure, the first DDL batch should be:

1. `tenants`
2. `workspaces`
3. `environments`
4. `api_keys`
5. `policy_versions`
6. `policy_assignments`
7. `namespace_policy_overrides`
8. `request_ledger`
9. `daily_namespace_rollups`

That set is enough to begin:
- request attribution
- scoped policy resolution
- savings accounting
- namespace analytics

---

# 13) Final stance

This schema is the minimum viable control-plane spine for Metera.

It is intentionally designed to support the real product claims:
- policy-enforced reuse
- measurable savings
- measurable safety posture
- multi-tenant SaaS onboarding
- future billing and governance

If the implementation follows this schema discipline, Metera can scale from a strong gateway prototype into a credible SaaS control platform without needing a major re-architecture.

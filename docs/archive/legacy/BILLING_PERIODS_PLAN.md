# Billing Periods Plan

_Last updated: 2026-04-22_

This document defines the next billing implementation step for Metera.

It is intentionally written before implementation so billing does not grow from ad hoc endpoints into accounting debt.

---

# 1) Why this exists

Metera already has billing-prep scaffolding for:
- `plans`
- `subscriptions`
- `usage_charges`

That is useful, but not enough.

The missing accounting boundary is `billing_periods`.
Without billing periods, there is no clean way to answer:
- which usage belongs to which billable window
- when a billing window is still mutable
- when a summary is considered closed
- how to reconcile charges against request truth

So the next correct step is:
- define billing invariants
- add `billing_periods`
- build summary/export behavior on top of those periods

---

# 2) Billing invariants

These rules should be treated as design constraints.

## 2.1 Billing consumes ledger truth
Billing must derive from request/business facts.

Canonical source priority:
1. `request_ledger`
2. `billing_periods`
3. `usage_charges`
4. rollups only as summary/supporting inputs where appropriate

Dashboard counters and ad hoc stats are never billing truth.

## 2.2 One charge class, one canonical source path
Do not allow the same billable concept to be materialized from multiple source paths without an explicit rule.

Example intended direction:
- per-request overage or managed-spend style charges -> derived from `request_ledger`
- period summary or reporting-only totals -> may use rollups for speed, but must reconcile to ledger
- base subscription fee -> derived from subscription/plan state, not request data
- manual adjustments -> explicit administrative entries

## 2.3 Billing periods own the accounting window
Usage charges should belong to an explicit billing period.
A billing period is the boundary that says:
- usage from `period_start` to `period_end` belongs here
- period status governs mutability

## 2.4 Closeout must be explicit
A period should not become "closed" implicitly.
There should be a deliberate closeout step.

## 2.5 Late-arriving data must have a policy
Metera must define what happens if request rows appear after a period is closed.
Initial v1 recommendation:
- allow `open` and `closing` periods to absorb late data
- once `closed`, do not mutate charge rows silently
- record late-arriving deltas into the next period or an explicit adjustment path later

## 2.6 Idempotency matters
Billing materialization must be repeatable without duplicating charges.

At minimum, protect uniqueness by source identity for each charge class.

---

# 3) Recommended billing-period lifecycle

Use these statuses first:
- `open`
- `closing`
- `closed`

## `open`
The active mutable period.
- request/usage attribution may continue
- summary totals may be recomputed
- charges may still be materialized/rebuilt safely

## `closing`
Operator/system is preparing the period for closeout.
- freeze assumptions begin
- perform reconciliation checks
- verify summary totals
- verify source windows and charge uniqueness

## `closed`
Billing window is finalized for v1 purposes.
- no silent recomputation
- no silent charge mutation
- later corrections should flow through explicit adjustment logic, not invisible rewrites

Future state if needed:
- `finalized`
- `invoiced`
- `void`

But do not overbuild that yet.

---

# 4) Recommended `billing_periods` shape

Minimum fields recommended for implementation:
- `id`
- `tenant_id`
- `subscription_id`
- `period_start`
- `period_end`
- `status`
- `request_count`
- `upstream_cost_usd_total`
- `realized_savings_usd_total`
- `shadow_savings_usd_total`
- `created_at`
- `updated_at`
- `closed_at` (recommended addition)
- `metadata` (recommended extension)

Recommended status constraint:
- `open`
- `closing`
- `closed`

Recommended uniqueness:
- do not allow duplicate active periods for the same subscription + date range

---

# 5) How billing periods should be populated

## Initial v1 approach
### Period creation
Create a billing period from subscription boundaries:
- subscription has `current_period_start`
- subscription has `current_period_end`
- billing period mirrors that window

### Period summarization
Populate period totals from `request_ledger` using:
- `tenant_id`
- subscription period window
- optionally workspace/environment filters later if the plan model evolves

### Totals to compute
For the first version, compute at least:
- request count
- upstream cost total
- realized savings total
- shadow savings total

These should be reproducible from ledger truth.

---

# 6) How `usage_charges` should evolve

Current billing-prep already materializes usage charges from ledger and rollups.
That is acceptable as scaffolding.
It is risky as a long-term billing model unless source rules become explicit.

## Recommended direction
### Charge types
Start with a narrow charge model:
- `base_fee`
- `managed_spend`
- `request_overage`
- `manual_adjustment`

Avoid introducing too many pricing concepts early.

### Canonical source direction
- `base_fee` -> subscription/plan state
- `managed_spend` or usage-derived charge -> request ledger summarized into period logic
- `request_overage` -> request ledger or billing-period summary, but pick one and document it
- `manual_adjustment` -> explicit admin action

### Uniqueness recommendation
Protect charges with a uniqueness strategy around something equivalent to:
- `billing_period_id`
- `charge_type`
- `source_table`
- `source_ref`

So repeated materialization is safe.

---

# 7) Implementation order

## Step 1
Add `billing_periods` table support to `app/controlplane/repositories/billing.py`.

## Step 2
Add repository methods for:
- create/open billing period from subscription
- list billing periods
- fetch active billing period for a subscription
- summarize billing period from ledger
- mark period `closing`
- mark period `closed`

## Step 3
Add admin/internal endpoints for:
- `GET /admin/control/billing/periods`
- `POST /admin/control/billing/periods`
- `POST /admin/control/billing/periods/{id}/summarize`
- `POST /admin/control/billing/periods/{id}/close`

Keep these internal/admin-facing first.
Do not jump straight to customer-facing billing UX.

## Step 4
Wire billing-period summary totals to charge materialization.

## Step 5
Only after the above is stable, add export/invoice stub behavior.

---

# 8) Reconciliation checks to add

Before closing a period, verify:
- period totals reconcile to ledger query totals for the same window
- usage charges reconcile to expected period totals
- no duplicate materialization occurred for the charge classes in use
- subscription and period date ranges are aligned

If these checks are not explicit, billing will drift.

---

# 9) Things not to build yet

Do not build these in the next slice:
- payment provider integration
- hard caps / request blocking based on billing state
- discounts, coupons, credits, taxes, revenue recognition complexity
- customer self-serve invoicing UX
- complicated pricing matrices

The next billing slice should be accounting structure, not monetization theater.

---

# 10) Definition of done for this billing slice

This slice is done when all of these are true:
- `billing_periods` exist in repository and admin/internal surface
- a subscription can have an explicit active period
- period totals can be recomputed from ledger truth
- closeout state is explicit
- charge materialization can attach to a billing period safely
- the source-of-truth rules are documented and followed

If those are not true, Metera still has billing prep, not billing structure.

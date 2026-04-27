# BETA_COMMERCIAL_POLICY_DECISIONS

_Last updated: 2026-04-25_
_Module: `docs/MOD_COMMERCIAL_POLICY.md`
_Status: Beta working policy aligned to current runtime_

## Why this document exists
The enforcement plumbing is already live and proved in Pilot.
What Beta needed was an explicit commercial policy engineers and operators can point to without inferring behavior from code.

This document makes the current intended Beta policy explicit.
If product policy changes later, update this document first and then change runtime.

## Canonical truth
Commercial enforcement is derived from:
1. subscription state
2. billing-period state
3. realized savings accumulated in that billing period

Billing periods and subscriptions are the source of truth.
Commercial events are an observable log layered on top of that truth.

## Beta policy decisions

### 1) The `$50` threshold is recurring per billing period
For Beta, the patronage gate is **not** a one-time conversion flag.
It is evaluated against each billing period independently.

Working rule:
- when a billing period's realized savings reach or exceed `$50.00`, that period has crossed the free-usage threshold for that period
- crossing the threshold moves the period from `open` to `closing`
- a future billing period starts fresh and is evaluated on its own period totals

Rationale:
- this matches the current implementation and Pilot proof path
- it keeps billing truth period-scoped instead of introducing a hidden lifetime conversion flag
- it avoids creating a second source of truth during Beta

### 2) Blocking begins at `closing`, not only at `closed`
For Beta, once a non-active tenant crosses the threshold and the period enters `closing`, serving access may be blocked immediately.

Working rule:
- `open` + threshold not reached -> serving allowed
- `closing` + subscription not `active` -> serving blocked with reason `patronage_required`
- `closed` + subscription not `active` -> serving blocked with reason `service_suspended`

Interpretation:
- `closing` means free usage for that period is exhausted and tenant conversion is now required to continue service
- `closed` means the period has been finalized and the suspension state is no longer provisional

Rationale:
- this is already the code-backed runtime behavior
- it preserves a clear operator distinction between conversion-required and fully closed/suspended
- it avoids silently allowing additional free serving between threshold crossing and explicit closeout

### 3) Active paid tenants continue serving in later periods
For Beta, an `active` subscription is the allowance to keep serving traffic even after the threshold is reached.

Working rule:
- if subscription status is `active`, the tenant is not blocked by the current threshold enforcement path
- subsequent billing periods still accumulate usage and savings as normal billing truth
- there is currently no separate post-conversion threshold model in Beta beyond normal billing-period accounting

Important limit:
- this policy does **not** yet define long-term GA pricing behavior beyond the current active-subscription bypass
- do not invent additional paid-tenant caps or rollover semantics unless product explicitly asks for them

### 4) Read-only billing surfaces remain available while serving is blocked
For Beta, commercial blocking applies to the proxy serving path, not to tenant billing visibility.

Reads that should remain available to an authorized tenant while serving is blocked:
- billing scope
- billing overview
- subscriptions
- billing periods
- per-period report views
- reports list
- billing history
- usage charges
- manual adjustments

Rationale:
- tenants must be able to understand why serving is blocked
- operators need the reporting surface to support conversion and closeout
- current tenant billing routes already behave this way and should stay that way unless auth design changes require review

## Runtime mapping

### Billing-period states
- `open`: current period is accumulating usage and remains below threshold, or has not yet been summarized past threshold
- `closing`: threshold reached for the period; non-active tenants are conversion-gated
- `closed`: period finalized; non-active tenants remain suspended until subscription state becomes active

### Enforcement reasons
- `patronage_required`: threshold reached and period is `closing`
- `service_suspended`: threshold reached and period is `closed`

### Recommended operator action
When a tenant is blocked because subscription status is not `active`, the default recommended action is:
- `activate_subscription`

## Code references backing this policy
- threshold constant and summarize transition:
  - `app/controlplane/repositories/billing.py`
- enforcement truth:
  - `app/controlplane/repositories/billing.py#get_tenant_enforcement_state`
- proxy enforcement surface:
  - `app/services/proxy_service.py#_enforce_billing_access`
- 402 mapping:
  - `app/api/routes_chat.py`
- admin event emission and close flow:
  - `app/api/routes_billing_admin.py`
- tenant readable billing surfaces:
  - `app/api/routes_tenant_billing.py`

## Operator notes
- Do not describe the current Beta model as "closed-only suspension". That is not what runtime does.
- Do not describe the `$50` rule as a one-time conversion gate. That is not what runtime does.
- If product wants grace periods, one-time conversion, or a different paid-period model, that is a deliberate policy change and should be handled as a new decision.

## What would count as a policy change
Any of the following would require updating this document before code changes:
- making the threshold one-time instead of recurring per period
- delaying blocking until `closed`
- adding a grace period after `closing`
- introducing different paid-tenant threshold behavior
- blocking tenant billing/report/history reads

# MOD_COMMERCIAL_POLICY

## Operating stance
Act as a founding/principal engineer.
You should:
- treat billing periods/subscriptions as canonical truth
- avoid changing runtime behavior casually
- document policy explicitly before code changes when possible
- distinguish product policy from current implementation
- stay in this module unless a real cross-module dependency requires escalation

## Scope
This module owns:
- threshold policy
- enforcement semantics
- suspension timing
- paid-tenant next-period behavior
- read availability while serving is blocked

## Non-goals
Do not use this module to:
- rewrite the proxy path
- do broad output polish work
- do general operator clean-up unless needed for policy evidence

## Mission
Make the threshold and enforcement story explicit so Beta work is policy-driven instead of assumption-driven.

## Read this module first, then go to code
Relevant code:
- `app/controlplane/repositories/billing.py`
- `app/controlplane/repositories/commercial_events.py`
- `app/services/proxy_service.py`
- `app/api/routes_chat.py`
- `app/api/routes_billing_admin.py`
- `app/api/routes_tenant_billing.py`

Primary references:
- `docs/BETA_COMMERCIAL_POLICY_DECISIONS.md`
- `docs/PACK_COMMERCIAL_ENFORCEMENT.md`
- `docs/PILOT_OPERATOR_NOTES_2026-04-24.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`

## Code-backed runtime today
- threshold constant: `$50.00`
- source: `app/controlplane/repositories/billing.py`
- current implementation evaluates per billing period, not via a one-time conversion flag
- `summarize_billing_period(...)` moves `open -> closing` when realized savings for that period reach/exceed the threshold
- `get_tenant_enforcement_state(...)` blocks non-active tenants when:
  - threshold reached
  - billing period status is `closing` or `closed`
  - subscription status is not `active`
- enforcement reason mapping:
  - `closing` -> `patronage_required`
  - `closed` -> `service_suspended`
- tenant billing/report/history reads remain available because tenant billing routes do not invoke proxy billing enforcement

## Beta policy decisions now documented
The current Beta working policy is explicitly captured in:
- `docs/BETA_COMMERCIAL_POLICY_DECISIONS.md`

That document makes these decisions explicit:
1. the `$50` gate is recurring per billing period
2. blocking begins at `closing` for non-active subscriptions
3. `active` subscriptions continue serving in later periods under normal billing truth
4. authorized tenant billing/report/history reads remain available while serving is blocked

## Definition of done
This module is done when the intended commercial policy is explicit enough that engineers do not have to infer it from code behavior alone, and the documented policy matches the tested runtime.

## Escalation rule
Escalate out of this module only if:
- policy decisions require auth-surface mapping changes -> hand off to `docs/MOD_BETA_RELIABILITY.md`
- policy evidence is blocked by proof-path cleanliness or operator reproducibility -> hand off to `docs/MOD_OPERATOR_CLEANLINESS.md`
# PACK_COMMERCIAL_ENFORCEMENT

_Last updated: 2026-04-24_
_Read this when working on billing policy, threshold behavior, subscription conversion, or service suspension rules._

## What is already proved
The runtime now proves this path:
- a tenant can cross the `$50` realized-savings threshold
- billing period transitions to `closing`
- commercial events are emitted
- billing period can be explicitly closed
- after close, a non-active subscription can be blocked at the proxy
- live proxy response is `402 Payment Required` with billing/commercial context

## Current implemented behavior
Observed in the 2026-04-24 proof:
- subscription status: `trialing`
- billing period status after close: `closed`
- enforcement reason: `service_suspended`
- proxy response: `402 Payment Required`
- recommended action: `activate_subscription`

Code-backed runtime behavior today:
- threshold logic is currently recurring per billing period, not implemented as a one-time conversion gate
- non-active subscriptions are blockable once the billing period is `closing` or `closed`
- reason currently resolves to `patronage_required` while `closing`
- reason currently resolves to `service_suspended` once `closed`
- `active` subscriptions are not blocked by the current enforcement truth
- tenant billing/report/history reads remain available because tenant billing routes do not call proxy billing enforcement

## Policy questions still requiring explicit product decisions
These are the main open commercial questions:

1. **Is the `$50` gate recurring or initial-conversion only?**
   - per billing period?
   - only until first paid conversion?
   - something else?

2. **Exactly when should service suspension happen?**
   - immediately at `closing`?
   - only after explicit `closed`?
   - after a grace period?

3. **What should happen for subscribed tenants in subsequent periods?**
   - do they continue into normal paid periods automatically?
   - is there a different threshold/control model after conversion?

4. **What should remain readable while service is blocked?**
   - invoice views?
   - report views?
   - tenant billing overview/history?

## Architectural rule
Billing periods / subscriptions are canonical truth.
Commercial events are the observable event surface layered on top.
Do not invert that relationship.

## Relevant code
- `app/services/proxy_service.py`
- `app/api/routes_chat.py`
- `app/api/routes_billing_admin.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/repositories/commercial_events.py`

## Practical next step
Do not debate this abstractly.
Capture the intended policy explicitly in docs, then ensure runtime matches it.

## Bottom line
The enforcement plumbing works. The remaining work is product-policy clarity, not basic technical feasibility.

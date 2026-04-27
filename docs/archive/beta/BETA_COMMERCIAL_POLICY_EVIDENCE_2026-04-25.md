# BETA_COMMERCIAL_POLICY_EVIDENCE — 2026-04-25

## Scope
Commercial-policy module follow-up after reading:
- `docs/BETA_MASTER_MAP.md`
- `docs/MOD_COMMERCIAL_POLICY.md`

This note records the live Docker validation for the `closing` enforcement path and the follow-up fix to keep commercial events aligned with billing truth.

## Problem found
Live Docker proof confirmed the intended Beta enforcement policy:
- a non-active tenant is blocked at `closing`
- enforcement reason is `patronage_required`
- proxy returns real `402 Payment Required`

However, the admin commercial-event path was also emitting `service_suspended` during `closing`.

That created an inconsistency:
- billing truth / proxy enforcement: `closing -> patronage_required`
- commercial events: `closing -> patronage_required` **and** premature `service_suspended`

## Root cause
File:
- `app/api/routes_billing_admin.py`

Function:
- `_emit_service_suspended_event_if_required(...)`

Before the fix, this helper emitted `service_suspended` whenever the tenant was blocked, without requiring the billing period to actually be `closed`.

Because blocked state is true for non-active tenants in both `closing` and `closed`, the event layer could mislabel a still-closing period as suspended.

## Fix applied
Changed `_emit_service_suspended_event_if_required(...)` so that it returns early unless:
- tenant is blocked, **and**
- `billing_period_status == "closed"`

Resulting intended mapping is now explicit and enforced:
- `closing -> patronage_required`
- `closed -> service_suspended`

## Additional test coverage
Updated `tests/test_admin_billing_prep.py` to add a targeted regression test:
- summarize a threshold-crossed trialing tenant into `closing`
- verify `patronage_required` event exists
- verify `service_suspended` is **not** emitted before close

Note:
- while running the broader legacy admin billing prep file, an unrelated existing export-text assertion still fails in that file's test fixture path
- targeted commercial-policy tests passed in Docker

## Docker validation performed
### 1) Targeted tests in Docker
Executed in Docker test container:
- `tests/test_chat_errors.py` targeted billing-enforcement cases
- `tests/test_tenant_billing_routes.py`
- targeted `tests/test_admin_billing_prep.py` policy cases

Relevant passing targeted result:
- `2 passed, 2 deselected`

### 2) Live running-stack proof before fix
A live proof tenant was seeded into the running Docker app.
Observed before the event fix:
- billing period moved to `closing`
- realized savings reached `$55.00`
- subscription remained `trialing`
- proxy chat probe returned `402`
- enforcement reason was `patronage_required`
- but commercial events still included premature `service_suspended`

This confirmed the bug was in the event layer, not the request-path enforcement truth.

### 3) Restart and live proof after fix
After patching `routes_billing_admin.py`, the app container was restarted and the live proof was rerun.

Observed live after restart:
- tenant: `tenant_closingproof_20260425042739`
- billing period: `billing_period_b104cffa94264b1ea477f9c663c2d986`
- billing period status: `closing`
- subscription status: `trialing`
- realized savings: `$55.00`
- proxy response: `402 Payment Required`
- enforcement reason: `patronage_required`
- commercial event type surfaced in response: `patronage_required`
- commercial event status surfaced in response: `closing`

Commercial events for the tenant after restart:
- `patronage_required`

Not observed after restart during `closing`:
- `service_suspended`

## Representative live post-fix enforcement payload
```json
{
  "detail": {
    "message": "Tenant access is blocked pending billing conversion: patronage_required. Billing period billing_period_b104cffa94264b1ea477f9c663c2d986 is closing after reaching $55.00 realized savings (threshold $50.00).",
    "reason": "patronage_required",
    "tenant_id": "tenant_closingproof_20260425042739",
    "subscription_id": "subscription_ea5fdae3277840968927e791000ca24c",
    "subscription_status": "trialing",
    "billing_period_id": "billing_period_b104cffa94264b1ea477f9c663c2d986",
    "billing_period_status": "closing",
    "realized_savings_usd_total": 54.99999999999901,
    "threshold_usd": 50.0,
    "commercial_event_type": "patronage_required",
    "commercial_event_status": "closing",
    "recommended_action": "activate_subscription"
  }
}
```

## Decision impact
This closes the semantic gap between:
- billing-period truth
- proxy enforcement behavior
- commercial event surface

For Beta, the live product behavior is now consistent with the documented commercial policy:
- threshold is recurring per billing period
- serving is blocked for non-active tenants at `closing`
- `closing` is represented as `patronage_required`
- `service_suspended` is reserved for `closed`

## Files changed
- `app/api/routes_billing_admin.py`
- `tests/test_admin_billing_prep.py`
- `docs/BETA_COMMERCIAL_POLICY_DECISIONS.md`
- `docs/MOD_COMMERCIAL_POLICY.md`
- `docs/BETA_COMMERCIAL_POLICY_EVIDENCE_2026-04-25.md`

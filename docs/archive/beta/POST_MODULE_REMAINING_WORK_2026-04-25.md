# Remaining Work Outside the Beta Module Map — 2026-04-25

This file lists the meaningful work that still exists after treating all three Beta modules as complete.

## 1) Product-grade artifact polish
Still useful:
- continue improving invoice/report presentation
- remove remaining internal-looking phrasing from customer-facing outputs
- tighten small-value formatting and edge-case readability

This is now polish work, not module-defining uncertainty.

## 2) Broader tenant-facing product maturity
Still open beyond the current module map:
- expand tenant-facing control-plane surfaces beyond the current billing-first slice where needed
- make the product feel more intentional and less admin-adjacent
- keep frontend/dashboard/read models aligned with backend truth

This maps closely to broader Beta product-surface maturity, not unresolved Pilot closure.

## 3) Reliability hardening for managed external use
Still open:
- more scheduler/rollup operational hardening
- stronger concurrency/retry behavior where needed
- deploy/update/recovery procedures beyond current Pilot/Beta docs
- observability/alerting maturity for multiple external tenants

This is operational scaling work, not proof-path uncertainty.

## 4) Transitional path retirement
Still open:
- further contain or retire compatibility behaviors that were acceptable during controlled release
- reduce ambiguity around fallback paths as Beta hardens toward rollout

## 5) Payment/commercialization implementation
Still open and intentionally later:
- payment integration
- broader production-grade monetization loop
- broader commercialization and support posture

## 6) Rollout readiness
Still outside the current module map:
- production runbooks
- rollback/incident/recovery discipline for wider exposure
- onboarding/support burden reduction for broader adoption
- broad release readiness review

## Practical framing
The module map solved the highest-value Beta clarity work:
- auth/reliability baseline
- commercial-policy clarity
- operator cleanliness and docs-only reproducibility

What remains now is mostly:
- polish
- scaling hardening
- rollout preparation
- new product-surface work

Those are real tasks, but they are not the same kind of foundational ambiguity the Beta modules were created to resolve.

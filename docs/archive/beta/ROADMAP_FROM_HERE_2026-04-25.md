# Roadmap From Here — 2026-04-25

_Audience: principal/founding engineers picking up Metera after Pilot proof closure and Beta module completion._

This document answers one question:

**What should happen next, in what order, now that the Pilot spine is proved and the current Beta module map is effectively complete?**

---

## 1) Current operating reality

Treat these as already established:
- Pilot Phase 1 proof is complete
- the canonical proof path works in Docker
- real post-close `402 Payment Required` enforcement has been observed
- the current Beta modules are treated as complete:
  - auth/reliability baseline
  - commercial-policy clarity
  - operator cleanliness / docs-only reproducibility

That means the next work should **not** be framed as:
- “does the architecture work?”
- “does billing enforcement really exist?”
- “does identity attribution basically work?”
- “which Beta module do we start with?”

Those questions are already closed unless contradictory runtime evidence appears.

---

## 2) What the next phase actually is

The next phase is a transition from:
- **controlled proof + module cleanup**

to:
- **repeatable product operation + stronger external-tenant readiness**

This is not one giant rewrite phase.
It is a sequencing problem.

The work now falls into four buckets:
1. short-term product/output polish
2. beta operational hardening
3. broader tenant product-surface maturity
4. rollout-preparation work

---

## 3) Recommended execution order

## Phase A — Tight short-term polish
Do this first because it is high-leverage, low-risk, and improves credibility quickly.

### A1. Finalize customer-facing invoice/report polish
Goal:
- make invoice/report outputs feel customer-readable, not engineering-first

Tasks:
- improve edge-case/small-value formatting
- remove any remaining internal-looking phrasing
- make summaries more legible for non-engineers
- keep JSON output stable while refining human-readable exports

Definition of done:
- a customer can read the output and understand gross cost, savings, charges, and recovered value without explanation

### A2. Consolidate closure docs where sensible
Goal:
- reduce doc sprawl now that proof/module closure is mostly done

Tasks:
- keep canonical references obvious
- avoid multiple docs saying the same thing in slightly different ways
- preserve historical validation notes without forcing new readers through all of them

Definition of done:
- a new engineer can find the current truth in one short path without archaeology

---

## Phase B — Beta operational hardening
Do this second. This is the most important “serious product” work after proof closure.

### B1. Rollup/scheduler/recovery hardening
Goal:
- support multiple external beta tenants without brittle operator behavior

Tasks:
- improve retry/recovery behavior for derived jobs
- document deploy/update/recovery paths more explicitly
- verify operator recovery steps under realistic restart/update scenarios
- continue bounded shared-pool discipline instead of papering over problems with infra slack

Definition of done:
- routine operator issues do not require ad hoc debugging or chat-history recovery

### B2. Observability and support posture
Goal:
- make real beta issues easier to detect and diagnose quickly

Tasks:
- tighten observability around billing/rollup/proof-critical flows
- improve support/debug visibility without polluting canonical proof artifacts
- ensure scoped evidence/debug patterns remain the norm

Definition of done:
- an engineer can explain and diagnose a tenant issue from retained system evidence without guessing

---

## Phase C — Broader tenant product-surface maturity
Do this third, after operations are less brittle.

### C1. Expand beyond the current billing-first slice
Goal:
- make tenant-facing product surfaces feel intentional rather than admin-adjacent

Tasks:
- identify the next tenant-facing control-plane surfaces needed for a coherent customer experience
- strengthen read models where backend truth is already available
- keep frontend/dashboard behavior aligned with backend/accounting truth

Definition of done:
- the tenant-facing product feels like an actual product surface, not a collection of internal endpoints made visible

### C2. Reduce transitional release artifacts
Goal:
- tighten the gap between controlled-release behavior and real Beta posture

Tasks:
- further contain fallback behavior that was acceptable during controlled release
- reduce ambiguity around transitional paths
- keep source-of-truth boundaries explicit as compatibility state is retired

Definition of done:
- the system is easier to reason about because fewer transitional behaviors still exist

---

## Phase D — Rollout preparation
Do this only after the earlier phases are solid.

### D1. Production operations posture
Goal:
- prepare for broader exposure without brittle operational risk

Tasks:
- production runbooks
- rollback discipline
- incident/recovery discipline
- trustworthy monitoring/alerting

### D2. Commercialization and payment integration
Goal:
- move from internally-proved commercial control to broader production monetization

Tasks:
- payment integration
- production-grade commercial lifecycle handling
- stronger customer/support flows around monetization states

Definition of done:
- broader release is not undercut by obvious operational or commercialization gaps

---

## 4) What should not happen next

Do **not** do these as the default next move:
- reopen solved Pilot architecture questions
- do a broad proxy rewrite
- do a broad auth rewrite without concrete evidence
- overfocus on cosmetic dashboard work before ops hardening
- compensate for application issues by simply increasing infrastructure limits
- create lots of new docs without reducing the old decision surface

---

## 5) Recommended immediate next actions

If picking up work right now, do these next:

1. finish the last pass of invoice/report polish
2. consolidate/trim closure docs where that reduces confusion
3. harden rollup/recovery/deploy/update procedures for beta operations
4. improve observability/support posture around tenant-impacting flows
5. only then expand broader tenant-facing product surfaces

---

## 6) Canonical references from here

Start with:
- `docs/BETA_MASTER_MAP.md`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/BETA_MODULE_COMPLETION_SUMMARY_2026-04-25.md`
- `docs/POST_MODULE_REMAINING_WORK_2026-04-25.md`

Use historical validation docs when needed, not as the default starting point.

---

## 7) Bottom line

Metera is past the “prove the spine” stage.

The next good work is:
- polish what customers/operators directly see
- harden operations for real beta use
- expand product surfaces carefully
- prepare for rollout only after those are solid

That is the roadmap from here.

# Metera Deployment Readiness Plan

_Last updated: 2026-04-27_
_Audience: founding/principal engineers planning or executing release progression._

This document defines the release progression for Metera:
- **Pilot**
- **Beta**
- **Rollout**

Use this as the canonical planning frame for launch readiness, sequencing, and handoff expectations.

The intent is simple:
- preserve the validated gateway core
- add product/commercial hardening in deliberate layers
- avoid pretending pilot-ready and rollout-ready are the same thing
- make sure release posture is understandable to a new senior engineer without chat history

---

# 1) Guiding release assumptions

## 1.1 Founding/principal engineer stance
Metera should be advanced by engineers operating with founding/principal engineer judgment:
- optimize for scalability and correctness
- push back on structurally weak ideas
- preserve accounting and policy truth boundaries
- avoid quick fixes that weaken long-term architecture

## 1.2 Current engineering constraints
These constraints shape the release plan:
- do not destabilize the validated request-serving path
- do not blur ledger truth with analytics/dashboard truth
- do not jump to payment integration before accounting and reporting are credible
- do not rely on transitional tenant query fallback in real Pilot proof
- do not treat “the endpoints exist” as equivalent to “the release phase is complete”

---

# 2) Phase overview

## Phase 1 — Pilot
Goal:
- prove the end-to-end product with a small number of controlled tenants/users
- keep rollout founder-operated / engineer-operated
- validate real traffic, real ledgering, real billing review flows

Target shape:
- internal deployment or design partner environment
- low tenant count
- manual support acceptable
- production-like enough to prove the system honestly

Exit standard:
- the full tenant lifecycle works in a production-like environment with known users and operational supervision

## Phase 2 — Beta
Goal:
- move from controlled proof to repeatable product operation
- reduce manual intervention
- tighten auth/reporting/ops enough that broader but still managed customer use is credible

Target shape:
- invite-only beta
- multiple external tenants
- higher reliability expectations
- customer-facing reporting quality starts to matter materially

Exit standard:
- Metera is operationally stable, commercially legible, and safe enough for broader managed adoption

## Phase 3 — Rollout
Goal:
- support broad production rollout with strong external confidence
- harden commercial and operational edges, not just the gateway core

Target shape:
- generally available production posture
- broader external tenant onboarding
- stronger low-touch or self-serve onboarding potential
- clear production runbooks and enforcement posture

Exit standard:
- Metera is technically, operationally, commercially, and product-wise ready for broader exposure

---

# 3) Current phase assessment

## Pilot
**In progress.**
Pilot is materially closer than before because:
- pilot compose/env posture has been tightened
- repository-backed identity now works
- authenticated request attribution now works
- request-ledger persistence is proved
- rollups are proved
- billing review/report/invoice surfaces are proved
- tenant-facing billing surfaces are proved under authenticated scope
- startup posture validation now fails fast in strict profiles
- `/ready` now exists as the strict deployment acceptance gate

Pilot is still **not complete** because:
- the retained evidence/operator-note package still needs to be tightened
- small-value presentation/polish still needs work

This means Pilot is now past core architecture validation and into evidence/polish closure, with posture/readiness truth now part of the baseline contract.

## Beta
**Partially underway in code, not ready.**
There is already some Beta-relevant work in the repo, but Beta should not be claimed yet.

## Rollout
**Not current priority.**
Rollout work should remain deferred until Pilot and Beta gates are genuinely passed.

---

# 4) Phase 1 — Pilot checklist

## Milestone P1 — Deployable controlled environment
Must be true:
- Docker deployment path is clean and documented
- pilot environment configuration is explicit
- the production-like stack can be stood up repeatably
- rollup rebuild cadence/path is configured and exercised
- `/health` and `/ready` are both verified, with `/ready` treated as the acceptance gate
- basic monitoring/health checks are verified in deployed environment

Current assessment:
- docs and compose posture are much stronger than before
- pilot-like env posture can be launched explicitly
- app image now includes the rollup rebuild script
- local pilot posture was revalidated after H1 hardening with `/ready` returning strict success
- this milestone should now be treated as locally satisfied baseline work; the next proof is cloud reproduction, not relitigation of the local contract

Definition of done:
- a fresh environment can be brought up and exercised without ad hoc debugging every time
- deployment acceptance relies on `/ready`, not `/health` alone

## Milestone P2 — Tenant auth posture safe enough for pilot
Must be true:
- authenticated tenant scope is the normal path
- query-param tenant fallback is disabled or tightly constrained in deployed Pilot config
- tenant scope mismatch protections are verified
- current role/capability model is sufficient for exposed Pilot surfaces

Current assessment:
- repository-backed identity works
- seeded tenant/workspace/api key path works
- authenticated requests now resolve tenant/workspace/api key attribution correctly
- this milestone is close, but not truly done until the Pilot proof runs without relying on fallback behavior anywhere in the path

Definition of done:
- pilot tenants cannot rely on transitional tenant-scoping behavior in real deployment

## Milestone P3 — End-to-end metering and billing review flow works
Must be true:
- request traffic writes cleanly to `request_ledger`
- rollups run successfully on real current ledger truth
- billing periods can be created/summarized/reconciled/previewed/closed
- tenant overview and billing read surfaces work against deployed data
- invoice stub and billing report generation work for pilot review

Current assessment:
- this is the current primary blocker milestone
- the remaining narrow issue is request-ledger persistence after successful authenticated traffic
- once ledger rows exist, this milestone should be re-executed end to end immediately

Definition of done:
- one realistic tenant lifecycle can be run end-to-end on deployed infrastructure with retained evidence

## Milestone P4 — Pilot operator readiness
Must be true:
- known failure modes are documented
- restart/rebuild/triage steps are usable from docs alone
- handoff/current-state docs accurately describe actual Pilot posture
- at least one controlled Pilot scenario has been executed against real deployment

Current assessment:
- operator docs are materially stronger now
- but they should still be updated after the next real end-to-end proof run, especially if request-ledger persistence fixes reveal new failure modes

Definition of done:
- Joshua or a new senior engineer can operate Pilot without hidden tribal knowledge

## Pilot phase gate
Metera is **Pilot-ready** only when:
- P1, P2, P3, and P4 are complete
- no critical correctness or isolation issue remains open in the proved path
- billing review is credible enough for design-partner conversations
- evidence is retained in docs or deployment notes

---

# 5) Phase 2 — Beta checklist

## Milestone B1 — Hardening auth
Goal:
- move past transitional auth behavior and establish a documented tenant-auth model that covers all tenant-facing surfaces so Beta users can be onboarded without dev-auth caveats

Must be true:
- tenant auth no longer depends on transitional behavior in real use
- the normal Beta path does not rely on query-param tenant fallback or other dev-auth shortcuts
- tenant permission model is stronger than the current minimal frame
- scope/capability behavior is predictable, documented, and consistent across tenant-facing surfaces
- authorization checks cover all exposed tenant-facing surfaces
- the intended auth model is written down clearly enough that a new engineer/operator can explain it without chat history

Definition of done:
- beta users can be onboarded without “this is still basically dev auth” caveats
- every exposed tenant-facing surface is covered by the documented auth/authorization model

## Milestone B2 — Reporting polish
Goal:
- deliver product-grade invoice/report artifacts that are materially more polished than the current draft stubs so a customer can interpret savings and billing without engineering translation

Must be true:
- billing reports are presentation-ready for customers
- invoice artifacts are materially more polished than draft stubs
- text/json exports are coherent and customer-comprehensible
- overview/report surfaces feel product-grade rather than internal-prep grade
- billing outputs explain savings, usage charges, and billing state in language a customer can interpret directly
- outputs are polished enough that they do not require an engineer to narrate the meaning of the artifact

Definition of done:
- a beta customer can review usage/savings/billing outputs without engineering translation
- invoice/report artifacts are materially more polished than the current draft stubs

## Milestone B3 — Product-surface maturity beyond raw endpoints
Must be true:
- tenant overview/read models are strong enough to support a coherent product experience
- adjacent tenant-facing APIs beyond the current billing-first slice are expanded where needed
- dashboard/consumer surfaces remain aligned with backend truth

Definition of done:
- the tenant-facing product feels intentional, not like a set of admin-adjacent APIs

## Milestone B4 — Operational hardening for managed external use
Must be true:
- rollup/scheduler behavior is reliable under beta load
- concurrency/retry behavior for derived jobs is improved where needed
- deploy/update/recovery procedures are documented and tested
- observability is sufficient to catch real beta issues quickly

Definition of done:
- multiple external beta tenants can be supported without brittle operator behavior

## Beta phase gate
Metera is **Beta-ready** when:
- B1, B2, B3, and B4 are complete
- tenant auth/reporting/ops are no longer obviously transitional
- managed external adoption is realistic without constant engineering babysitting

---

# 6) Phase 3 — Rollout checklist

## Milestone R1 — Commercialization complete enough for broad release
Must be true:
- payment integration exists
- monetization/billing enforcement path exists
- commercial states and billing artifacts are production-grade
- boundaries between accounting truth, billing control, and customer output are stable

## Milestone R2 — Production operations posture
Must be true:
- production runbooks are complete
- deployment, rollback, incident response, and recovery procedures are documented
- rollups and background jobs are hardened enough for broader production use
- monitoring and alerting are trustworthy

## Milestone R3 — Transitional paths retired or tightly contained
Must be true:
- compatibility paths useful during controlled release are removed or tightly bounded
- query-param tenant fallback is no longer meaningful in production
- legacy global policy compatibility state no longer muddies truth boundaries

## Milestone R4 — Broad customer readiness
Must be true:
- tenant-facing product surfaces support the intended customer journey
- onboarding/support burden is reduced enough for broader adoption
- documentation is strong enough for engineers and operators to understand production posture quickly
- major rollout blockers are closed

## Rollout phase gate
Metera is **Rollout-ready** when:
- R1, R2, R3, and R4 are complete
- broad production exposure would not be undercut by obvious auth/commercial/ops gaps

---

# 7) Recommended sequencing

Recommended work order:
1. finish the remaining **Pilot** blocker first
2. then drive **Beta** milestones in this order:
   - B1 auth hardening
   - B2 reporting quality
   - B4 ops hardening
   - B3 broader tenant product maturity
3. only after that, push **Rollout** milestones

Rationale:
- the gateway core is already strong enough that the next meaningful risks are auth, accounting, reporting, and ops
- payment/enforcement should come after product/commercial surfaces are mature enough to support them cleanly

---

# 8) What not to confuse

Do not confuse these:
- **pilot-ready** != broad customer-ready
- **identity works** != full tenant lifecycle is proved
- **billing/report endpoints exist** != customer-grade commercial product
- **compose boots** != production ops are hardened
- **tenant auth exists** != auth model is final

These distinctions matter and should remain explicit in planning and status updates.

---

# 9) Canonical planning usage

Use this document when discussing:
- deployment readiness
- launch sequencing
- what must happen before Pilot/Beta/Rollout
- milestone planning
- senior-engineer handoff expectations for release posture

Pair it with:
- `docs/HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/PILOT_EXECUTION_BOARD.md`
- `README_PRODUCTION.md`

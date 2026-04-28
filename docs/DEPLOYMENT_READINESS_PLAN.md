# Metera Deployment Readiness Plan

_Last updated: 2026-04-28 (early)_
_Audience: founding/principal engineers planning or executing release progression._

This document defines the release progression for Metera:
- **Pilot**
- **Beta**
- **Rollout**

Use this as the canonical planning frame for launch readiness, sequencing, and handoff expectations.

---

# 1) Current phase assessment

## Pilot local
**Complete enough as a baseline.**
The local Docker Pilot path has already been re-proved and should not be reopened without contradictory evidence.

## H2 cloud proof
**In progress, materially advanced.**
The practical cloud substrate and request path are now real, not hypothetical.

As of 2026-04-27 late, the following are proved in Railway:
- app deploys and survives restart
- `/ready` is the acceptance gate and returns success
- Redis is active
- pgvector is active
- repository-backed identity is active
- admin bootstrap works
- tenant API key scope resolution works
- tenant chat traffic succeeds against the real upstream provider
- plan creation works
- subscription creation works
- billing period creation works
- billing period admin listing works

The current H2 blocker is now narrower:
- the old direct-DB seeding proof harness should not remain the canonical cloud acceptance path
- final cloud enforcement proof should be run through a boring API-first path with explicit non-production threshold posture when needed

## Beta
**Not ready to claim.**
The cloud billing proof path is not yet complete, so Beta should still be considered blocked on H2 completion.

## Rollout
**Not current priority.**

---

# 2) Guiding release assumptions

- preserve the validated request-serving path
- keep `request_ledger` as accounting truth
- keep rollups derived
- do not blur identity truth with derived/reporting truth
- do not treat “the endpoint exists locally” as equivalent to “the cloud proof is complete”
- do not reopen solved local Pilot questions while the remaining blocker is clearly in billing/control-plane completion

---

# 3) Updated phase overview

## Phase 1 — Pilot
Goal:
- prove the end-to-end product with a small number of controlled tenants/users
- keep rollout founder-operated / engineer-operated
- validate real traffic, real ledgering, real billing review flows

Current assessment:
- local pilot baseline is proved
- cloud reproduction is partially proved
- the practical frontier is now control-plane completeness, not baseline runtime viability

## Phase 2 — Beta
Goal:
- move from controlled proof to repeatable product operation
- reduce manual intervention
- tighten auth/reporting/ops enough that broader but still managed customer use is credible

Current assessment:
- still blocked on finishing the cloud billing proof path

## Phase 3 — Rollout
Goal:
- support broad production rollout with strong external confidence

Current assessment:
- defer until H2 is complete and the billing/commercial path is coherent in cloud

---

# 4) H2 cloud proof checklist at planning level

## H2-A — Cloud posture and request path
**Status: complete enough for progression**
Must be true:
- app deploys cleanly
- `/ready` works as the true acceptance gate
- Redis active
- pgvector active
- repository identity active
- upstream request path works with real OpenAI traffic

Current assessment:
- achieved on 2026-04-27

## H2-B — Identity/admin bootstrap
**Status: achieved**
Must be true:
- admin auth works
- bootstrap tenant/workspace/API key works
- tenant scope resolution works from live proxy context

Current assessment:
- achieved on 2026-04-27

## H2-C — Billing control-plane coherence
**Status: current blocker**
Must be true:
- plans/subscriptions/periods create coherently
- tenant overview reflects the real open period
- materialization/report surfaces exist and behave coherently
- summarize/reconcile/closeout/report path works in cloud

Current assessment:
- plan/subscription/period creation works
- admin period listing works
- tenant overview coherence is fixed
- expected materialization/report paths are live
- API-first proof can now collect prompt/hit/token/savings evidence in cloud

Definition of done:
- one realistic cloud tenant lifecycle can be run end-to-end with retained evidence through billing/reporting truth and final `402` enforcement proof

## H2-D — Enforcement proof
**Status: not yet reached in cloud**
Must be true:
- final cloud-side blocked state yields real `402 Payment Required`
- the billing/commercial state causing the block is inspectable and coherent

Current assessment:
- already proved locally
- not yet re-proved in cloud because the billing flow is still blocked upstream of closeout/enforcement

---

# 5) Recommended sequencing from here

1. finish **H2-C** first:
   - locate/fix billing overview period resolution
   - locate/fix missing materialization/report admin surfaces
2. then execute cloud-side:
   - summarize
   - reconcile
   - closeout preview/report
   - close
3. then re-run the final tenant request and verify real cloud `402`
4. only after that, move back into H3/H4/H5 hardening and polish

---

# 6) What not to confuse

Do not confuse these:
- local Pilot proof != cloud billing proof complete
- chat traffic works != commercial lifecycle is fully proved
- billing period can be created != tenant overview/report path is correct
- admin list endpoint exists != the tenant-facing read model is coherent

---

# 7) Canonical planning usage

Use this document when discussing:
- current release posture
- what remains before H2 can be called complete
- sequencing after the major 2026-04-27 cloud debugging session

Pair it with:
- `docs/HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/H2_CLOUD_DEPLOYMENT_ROADMAP.md`
- `docs/H2_SESSION_HANDOFF_2026-04-27.md`

# PHASE_2_HARDENING_PLAN

_Last updated: 2026-04-27 (late)_
_Audience: principal/founding engineers driving Metera from re-proved local Pilot into deployment maturity and serious product operation._

## Why this plan exists
Metera’s local Pilot path is re-proved and the Beta module map is effectively complete.
The cloud deployment is now also substantially alive.
That changes the job.

The next phase is not architecture discovery.
The next phase is **hardening the system we actually want to keep** so it survives cloud deployment and becomes a repeatable product operation.

## Guiding stance
- preserve the validated request path
- remove transitional or accidental behavior deliberately, not all at once
- prefer explicit configuration and startup truth over magical defaults
- make cloud/operator flows reproducible from docs and product surfaces where possible
- fix the first real failing gate rather than broadening scope

## Phase 2 milestones

### H1 — Configuration and posture hardening
**Status: materially achieved for the current cloud target.**

Completed in the current baseline:
- local and cloud posture now boot correctly when configured correctly
- startup validation fails fast when critical posture is missing
- `/health` exposes posture and readiness context
- `/ready` is the strict acceptance gate
- Railway now reaches a valid cloud posture with Redis + pgvector + repository identity active

Remaining H1 follow-through:
- keep env layering disciplined across local / cloud / beta
- avoid reintroducing placeholder or stale upstream/admin key assumptions into docs or manifests

### H2 — Cloud deployment proof
**Status: in progress, now blocked on billing/control-plane completion.**

Already achieved in cloud:
- readiness/health posture
- repository-backed identity
- admin bootstrap
- tenant API key scope resolution
- real tenant chat traffic through OpenAI
- request/cost movement
- plan/subscription/period creation
- admin period listing

Remaining H2 proof surfaces:
- final cloud `402 Payment Required` proof still needs to be re-run under a boring API-first proof posture
- cloud proof should report prompts, cache hit rate, token savings, avoided-cost percentage, and repo-native realized savings ratio together
- direct DB seeding should be treated as local/internal validation, not as the canonical cloud proof path

### H3 — Bootstrap and onboarding hardening
**Status: partially advanced indirectly.**

Recent useful progress:
- cloud admin bootstrap path is real and works live
- tenant/workspace/API key creation is not just theoretical anymore

Still remaining:
- operator/bootstrap flows should become less artifact-driven and more intentionally documented/productized

### H4 — Operational correctness and recovery
**Status: partially advanced.**

Recent useful progress:
- failure classification is much sharper now
- upstream provider diagnostics were improved materially
- cloud debugging moved from blind 502s to actionable root causes

Still remaining:
- better runbooks around billing/control-plane debug and recovery
- boring redeploy/rebuild/reproof path after H2 is complete

### H5 — Product-surface maturity
**Status: not current mainline.**

Still remaining:
- customer-grade reporting polish
- cleaner product-surface flows beyond admin-adjacent proof surfaces

## Suggested execution order from here
1. finish H2 billing/control-plane completion
2. then tighten H4 operator recovery/readability around that path
3. then return to H3/H5 polish and productization

## What to defer
Do not jump first to:
- payment integration
- broad pricing/packaging expansion
- dashboard cosmetics without truth/support value
- proxy rewrites
- large auth rewrites that ignore the now-working repository-backed path
- broad billing redesign before the current proof path is completed honestly

## Success criterion for Phase 2 as a whole
Metera should become:
- hard to boot incorrectly
- cloud-provable end to end
- understandable to a cold principal engineer
- operable without hidden rituals
- commercially coherent enough for external managed Beta tenants

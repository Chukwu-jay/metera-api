# PHASE_2_HARDENING_PLAN

_Last updated: 2026-04-26_
_Audience: principal/founding engineers driving Metera from re-proved local Pilot into deployment maturity and serious product operation._

## Why this plan exists
Metera’s local Pilot path is re-proved and the Beta module map is effectively complete.
That changes the job.

The next phase is not architecture discovery.
The next phase is **hardening the system we actually want to keep** so it survives cloud deployment and becomes a repeatable product operation.

## Guiding stance
- preserve the validated request path
- remove transitional or accidental behavior deliberately, not all at once
- prefer explicit configuration and startup truth over magical defaults
- make cloud/operator flows reproducible from docs and product surfaces where possible
- do not confuse a successful local proof with finished deployment maturity

## Phase 2 milestones

### H1 — Configuration and posture hardening
Goal:
Make environment posture explicit, reproducible, and hard to misapply.

Why this matters:
The recent failure mode was not product logic collapse; it was configuration/runtime drift.
The compose/env fix is part of this milestone and should be treated as foundational Phase 2 work, not just a bug patch.

Already repaired and now part of the baseline:
- `docker-compose.yml` now passes pilot posture into `metera-app` correctly
- `.env.pilot.local` is now a real runtime truth source instead of a misleading compose-only artifact

Completed in the current baseline:
- clean explicit pilot-local env posture is passed into the app
- startup validation now fails fast when critical identity/ledger/billing posture is missing
- `/health` now exposes posture and readiness context
- `/ready` is now the strict readiness/acceptance gate
- Docker healthcheck now targets `/ready`, not permissive liveness
- custom detector reporting is deduplicated across JSON/YAML sources so posture output stays unambiguous

Remaining H1 follow-through:
- define clean env layering for local / pilot / cloud / beta beyond the local pilot baseline
- keep cloud/beta manifests aligned to the new readiness contract

Definition of done:
- operators cannot accidentally boot a “healthy but wrong” Metera posture without obvious failure or warning
- deployment acceptance uses `/ready` rather than `/health` alone

### H2 — Cloud deployment proof
Goal:
Prove that the repaired local truth survives in the target cloud deployment.

Required proof surfaces:
- health
- repository-backed identity
- authenticated attribution
- request ledger
- rollup rebuild
- billing/reporting path
- real `402 Payment Required`

Important framing:
This is a controlled deployment proof, not broad production readiness.

Definition of done:
- cloud environment reproduces the local Pilot proof contract with retained evidence

Execution reference:
- See `H2_CLOUD_DEPLOYMENT_ROADMAP.md` for the staged H2 plan, week-by-week cadence, proof gates, and parallelization guidance.

### H3 — Bootstrap and onboarding hardening
Goal:
Reduce dependence on dev-seeded assumptions and make tenant/bootstrap flows feel intentional.

Required work:
- reduce hidden dependency on local/dev seed identity assumptions
- improve operator/bootstrap path for new environments
- move toward API-first or operator-first bootstrap where feasible
- make new-tenant bring-up feel like a product/admin flow, not an engineering ritual

Definition of done:
- a new environment and a new tenant can be stood up without archaeology or direct DB heroics as the default path

### H4 — Operational correctness and recovery
Goal:
Make Metera easier to operate safely under repeated deploy/rebuild/recovery cycles.

Required work:
- stronger readiness/health distinctions
- clearer restart/rebuild/recovery procedures
- better guardrails around rollup/scheduler/retry behavior
- better support/debug visibility for blocked tenants, billing state, and proof-critical flows

Definition of done:
- operators can diagnose and recover without guessing whether the issue is posture, truth, or derived state

### H5 — Product-surface maturity
Goal:
Close the gap between technically working internals and a polished external product posture.

Required work:
- tenant/admin lifecycle flows feel intentional
- reporting/invoice artifacts feel customer-grade
- support/operator surfaces explain state clearly
- product surfaces feel less like admin-adjacent APIs

Definition of done:
- external managed Beta use feels like a product, not just a successfully exposed engineering system

## Suggested execution order
1. H1 — configuration/posture hardening
2. H2 — cloud deployment proof
3. H3 — bootstrap/onboarding hardening
4. H4 — operational correctness and recovery
5. H5 — product-surface maturity

Important nuance:
This order should be treated as the main dependency spine, not a strict single-thread rule.
Selected H3/H4/H5 work can and should run in parallel with H2 when it does not destabilize the cloud proof target.

Parallel-safe during H2:
- H3: bootstrap assumption inventory, operator/bootstrap runbooks, explicit onboarding/admin flow design, non-invasive bring-up tooling
- H4: restart/rebuild/recovery runbooks, failure classification, support/debug visibility for proof-critical flows, observability around blocked tenants and rollup state
- H5: reporting/support surface polish that clarifies already-correct truth without changing system semantics

Usually not parallel-safe during H2:
- major bootstrap rewrites that change identity assumptions mid-proof
- aggressive scheduler/retry or operational architecture redesign
- broad UI/product expansion or cosmetic work not tied to proof/support value
- large auth, billing, or request-path rewrites that move the proof target

Rule of thumb:
If the work makes cloud proof easier to repeat, diagnose, or explain, it is probably safe to run in parallel.
If it changes the semantics of the thing being proved, it should usually wait.

## What to defer
Do not jump first to:
- payment integration
- broad pricing/packaging expansion
- dashboard cosmetics without truth/support value
- proxy rewrites
- large auth rewrites that ignore the now-working repository-backed path

## Success criterion for Phase 2 as a whole
Metera should become:
- hard to boot incorrectly
- cloud-provable
- understandable to a cold principal engineer
- operable without hidden rituals
- credible to external managed Beta tenants

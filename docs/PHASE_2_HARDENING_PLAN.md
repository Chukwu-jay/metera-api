# PHASE_2_HARDENING_PLAN

_Last updated: 2026-04-28 (late)_
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
**Status: complete.**

Achieved in cloud:
- readiness/health posture
- repository-backed identity
- admin bootstrap
- tenant API key scope resolution
- real tenant chat traffic through OpenAI
- request/cost movement
- plan/subscription/period creation
- admin period listing
- billing materialization/summarize/reconcile/report path
- final tenant-facing cloud `402 Payment Required` proof in both `closing` and `closed` states
- retained API-first proof evidence

What carries forward from H2 into hardening:
- keep prompts, cache hit rate, token savings, avoided-cost percentage, and repo-native realized savings ratio together in retained proof output
- keep direct DB seeding as local/internal validation only, not as the canonical cloud proof path
- preserve the API-first harness as the canonical cloud verification path

### H3 — Bootstrap and onboarding hardening
**Status: partially advanced indirectly.**

Recent useful progress:
- cloud admin bootstrap path is real and works live
- tenant/workspace/API key creation is not just theoretical anymore
- semantic isolation evidence is now cleaner because the proof harnesses are stricter and more realistic

Still remaining:
- operator/bootstrap flows should become less artifact-driven and more intentionally documented/productized
- a cold engineer should be able to rerun H2/H3 proofs without archaeology

### H4 — Operational correctness and recovery
**Status: materially advanced.**

Recent useful progress:
- failure classification is much sharper now
- upstream provider diagnostics were improved materially
- cloud debugging moved from blind 502s to actionable root causes
- direct and resumed H3 commercial recovery are proved live
- semantic-cache multi-tenant partitioning moved from convention-dependent to structurally enforced
- corrected strict and soak proofs now exist for semantic partitioning

Still remaining:
- better runbooks around billing/control-plane debug and recovery
- boring redeploy/rebuild/reproof path after H2 is complete
- broader noisy-neighbor and sustained-load confidence beyond the current proof shapes

### H5 — Product-surface maturity
**Status: not current mainline.**

Still remaining:
- customer-grade reporting polish
- cleaner product-surface flows beyond admin-adjacent proof surfaces

## Suggested execution order from here
1. tighten H4 operator recovery/readability around the now-proved cloud path
2. harden H3 onboarding/bootstrap/operator reproducibility so cold engineers can re-run the path with minimal friction
3. then expand multi-tenant/noisy-neighbor confidence beyond the current proof shapes
4. then return to H5 polish and productization

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

## Newly documented hardening result: semantic partitioning closure
This is the major Phase 2 hardening result captured in the latest session.

What changed:
- semantic records now include `tenant_id` and `workspace_id`
- semantic lookup now filters on `tenant_id`, `workspace_id`, and `namespace`
- pgvector schema now includes tenant/workspace columns plus a scoped index
- the H3 correctness harness now includes shared-namespace collision testing
- the multi-round soak harness was corrected so valid later same-tenant semantic reuse is not mislabeled as leakage

Why it matters:
- before: semantic isolation depended partly on namespace hygiene
- now: semantic isolation is structurally enforced in the data/query layer

What proved it:
- `artifacts/h3_multi_tenant_strict_partitioning_single_round.json`
- `artifacts/h3_multi_tenant_strict_partitioning_soak.json`

## Undocumented gaps now made explicit
These are not H2 blockers anymore, but they are real post-H2 hardening gaps that should be treated as active work:

1. **Proof ergonomics still rely too much on high-volume traffic when threshold posture would be cleaner**
   - the final retained H2 proof was valid, but it used a large prompt flood to cross the live threshold
   - future operator proofs should prefer controlled threshold posture over brute-force traffic volume where possible

2. **Commercial recovery after enforcement is now proved live in both direct and resumed forms**
   - blocked-state path is proved: `trialing` -> threshold crossed -> `closing` -> `closed` -> tenant-facing `402`
   - happy-path recovery is proved live: operator subscription activation -> unblock -> resumed tenant service
   - retained resumed proof from a true enforcement-stage checkpoint is now also complete

3. **Semantic multi-tenant partitioning is now materially hardened, but broader concurrency confidence should continue**
   - the original soak concern surfaced a real architectural weakness: namespace-only semantic isolation was too soft
   - that gap is now closed for the current proof shapes with first-class tenant/workspace partitioning
   - remaining work is no longer “is it isolated at all?” but “how broad is the confidence envelope under pressure?”

4. **Operator observability and recovery ergonomics still lag runtime truth, but the gap is narrowing**
   - the system truth is materially better than the operator experience around it
   - new operator-facing helpers now exist for cold execution and tenant control-plane inspection
   - future work should continue improving concise health summaries, incident probes, and recovery playbooks for billing/control-plane issues

5. **Doc and onboarding compression is improved but not yet maximally boring**
   - top-level docs are cleaner now, but there is still overlap across handoff/current-state/readiness/hardening material
   - a cold engineer should eventually be able to onboard from one short entry doc plus one execution runbook

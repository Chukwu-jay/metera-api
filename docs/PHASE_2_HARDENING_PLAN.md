# PHASE_2_HARDENING_PLAN

_Last updated: 2026-04-29 (evening)_
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
**Status: closed as a proof milestone; follow-on operational hardening remains.**

Recent useful progress:
- cloud admin bootstrap path is real and works live
- tenant/workspace/API key creation is not just theoretical anymore
- semantic isolation evidence is now cleaner because the proof harnesses are stricter and more realistic

Still remaining as post-H3 hardening work, not as open H3 proof blockers:
- operator/bootstrap flows should become less artifact-driven and more intentionally documented/productized
- a cold engineer should be able to rerun H2/H3 proofs without archaeology

Newly completed onboarding-hardening improvement within the current H3 follow-through:
- namespace handling for authenticated tenant traffic is now less frictionful
- former supported mode remains valid: client sends explicit `x-metera-namespace`
- new supported mode is now also live: if the namespace header is omitted, Metera derives the namespace from authenticated tenant/workspace identity as `<tenant-slug>-<workspace-slug>`
- this preserves explicit override behavior while removing an unnecessary first-request onboarding step

### H4 — Operational correctness and recovery
**Status: closed as a hardening milestone.**

Achieved in the current baseline:
- failure classification is much sharper now
- upstream provider diagnostics were improved materially
- cloud debugging moved from blind 502s to actionable root causes
- direct and resumed H3 commercial recovery are proved live
- semantic-cache multi-tenant partitioning moved from convention-dependent to structurally enforced
- corrected strict and soak proofs now exist for semantic partitioning
- operator recovery/readability improved materially through cold-operator entrypoints, tenant inspection helpers, and a compact operator runbook
- expanded noisy-neighbor cloud validation now passes with corrected correctness-first interpretation

What carries forward after H4 closure:
- continue improving operator boringness, but do not treat that as an open H4 blocker
- continue expanding the confidence envelope under longer sustained load and broader concurrency patterns

### H5 — Product-surface maturity
**Status: closed.**

Implemented in the current baseline:
- tenant invoice preview route added:
  - `GET /control/tenant/billing/periods/{billing_period_id}/invoice`
- tenant invoice list route added:
  - `GET /control/tenant/billing/invoices`
- tenant billing overview now includes a latest invoice preview surface
- tenant report and invoice payloads are customer-safe by default:
  - no tenant-facing `export_content`
  - no tenant-facing raw `line_items`
  - no tenant-facing raw `reconciliation`
- tenant report and invoice payloads now include customer-readable status fields and explainers
- tenant reports now expose `additional_savings_opportunity_usd` as a customer-readable alias over the internal shadow-savings field
- local regressions for tenant billing routes, admin billing prep, and billing text rendering are passing

Closed with retained Railway cloud acceptance evidence:
- authenticated tenant scope proved live under repository-backed identity
- tenant overview/report/invoice payload shape proved live on the deployed app
- customer-readable fields proved live on the deployed tenant surface
- customer-safe shaping proved live on the deployed tenant surface
- admin/operator billing routes regression-checked live and still full-fidelity
- retained evidence artifact:
  - `docs/archive/railway/H5_CLOUD_ACCEPTANCE_RERUN_2026-04-29_20260429172020.json`

## Suggested execution order from here
1. harden H3 onboarding/bootstrap/operator reproducibility so cold engineers can re-run the path with minimal friction
2. expand from the current noisy-neighbor proof shape into broader sustained-load and concurrency confidence
3. continue H5 productization only after the now-proved deployed tenant contract is reflected cleanly across docs and operator surfaces
4. wire the existing dashboard into tenant-authenticated/customer-safe billing/reporting truth before promoting it as an official beta savings surface (`docs/BETA_DASHBOARD_WIRING_PLAN.md`)

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
   - noisy-neighbor cloud validation now also passes for the current harness shape
   - an initial noisy-neighbor failure was traced to an over-strict harness expectation, not a runtime isolation defect
   - remaining work is no longer “is it isolated at all?” but “how broad is the confidence envelope under pressure?”

4. **Operator observability and recovery ergonomics still lag runtime truth, but the gap is narrowing**
   - the system truth is materially better than the operator experience around it
   - new operator-facing helpers now exist for cold execution and tenant control-plane inspection
   - future work should continue improving concise health summaries, incident probes, and recovery playbooks for billing/control-plane issues

5. **Doc and onboarding compression is improved but not yet maximally boring**
   - top-level docs are cleaner now, but there is still overlap across handoff/current-state/readiness/hardening material
   - a cold engineer should eventually be able to onboard from one short entry doc plus one execution runbook
   - namespace handling is now cleaner than before because first authenticated requests no longer require a manually supplied namespace header, but the docs must continue making both the former explicit mode and the new automatic mode obvious

## Remaining post-H4 gaps
These are no longer reasons to keep H4 open, but they are the next honest hardening gaps:

1. **Sustained-load confidence**
   - current proof coverage now includes strict, soak, and noisy-neighbor cloud validation
   - still missing is a longer-duration confidence shape under more requests, longer runtime, and repeated pressure over time
   - the remaining question is drift and durability, not baseline correctness

2. **Broader concurrency envelope**
   - the current noisy-neighbor proof is useful but still only one asymmetric harness shape
   - still open are higher tenant counts, burstier mixes, and broader uneven concurrency patterns
   - the goal is to keep attribution, accounting, and cache behavior aligned under more varied pressure

3. **Operator ergonomics can still get more boring**
   - cold-operator entrypoints, tenant inspection helpers, and the operator recovery runbook now exist
   - there is still room to improve incident summaries, proof-output condensation, and faster layer-local failure classification

4. **Recovery/debug playbooks can still be compressed**
   - the system is more operable now, but decision trees can still become shorter and less overlapping
   - billing/control-plane recovery sequencing should become even more obvious to a cold engineer

5. **Evidence/document packaging is improved, not finished**
   - the current top-level docs are materially cleaner
   - there is still overlap across handoff/current-state/hardening/evidence surfaces that can be compressed further
   - the goal remains one short entry path plus one boring execution runbook

6. **Repeated cloud rerun confidence**
   - current truth is proved now, but not yet proved repeatedly over time
   - stronger confidence would come from repeat cloud reruns and simple regression comparison across retained artifacts

## H3 status sign-off
**H3 is closed.**

Closed proof obligations:
- direct H3 commercial recovery proved live
- resumed H3 commercial recovery proved live from a true enforcement-stage checkpoint
- semantic multi-tenant partitioning gap investigated, fixed, pushed, deployed, and re-proved
- post-deploy cloud strict proof passed
- post-deploy cloud 3-round soak passed

My judgment: none of the items above should be treated as reasons to say H3 is still open. They are post-H3 hardening and maturity work.

## H4 status sign-off
**H4 is closed.**

Closed hardening obligations:
- operator recovery/readability improved through cold-operator entrypoints and tenant control-plane inspection
- boring reproof path now exists for preflight / inspect / H2 / H3 / reproof execution
- billing/control-plane debug posture is materially sharper than before
- semantic partitioning is structurally enforced and operator-facing proof artifacts are cleaner
- noisy-neighbor cloud validation now passes with the corrected correctness-first interpretation

My judgment: the remaining items above are not reasons to say H4 is still open. They are the next confidence-expansion and operator-maturity steps after H4 closure.

— Metera / OpenClaw engineering sign-off, 2026-04-29 early
4 closure.

— Metera / OpenClaw engineering sign-off, 2026-04-29 early

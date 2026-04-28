# H2_CLOUD_DEPLOYMENT_ROADMAP

_Last updated: 2026-04-27 (late)_
_Audience: founding/principal engineers moving Metera from local Pilot proof to cloud-backed deployment proof without stalling adjacent maturity work._

## Purpose
H2 is not “make cloud production perfect.”
H2 is to prove that the repaired local Pilot truth survives in one real cloud deployment with retained evidence.

That means the roadmap should optimize for:
- preserving the validated local contract
- proving the proof-critical path in one target cloud
- collecting evidence at each gate
- fixing the first real failing gate rather than re-planning

## H2 current status snapshot
### Already achieved in Railway
- app deployed from `Chukwu-jay/metera-api`
- strict startup posture valid
- `/ready` is green
- Redis active
- pgvector active
- repository identity active
- admin bootstrap works
- tenant API key scope resolution works
- live tenant chat traffic works against OpenAI
- request/cost metrics move on live traffic
- plan creation works
- subscription creation works
- billing period creation works
- admin billing period listing works

### Current H2 blocker
The cloud proof is now blocked on **API-first commercial enforcement proof hardening**, not infrastructure.

Specifically:
1. tenant overview and the expected materialization/report admin surfaces are now fixed in cloud
2. the old direct-DB seeding proof harness should not remain the canonical cloud path
3. final summarize/reconcile/close/report/final-402 proof needs a repeatable API-first posture with controlled non-production thresholds when needed

## H2 outcome
By the end of H2, Metera should have one boring, repeatable cloud deployment path that proves:
- health and readiness behave correctly in cloud
- repository-backed identity survives deploys
- authenticated attribution works end-to-end
- request ledger persists correct truth
- rollup rebuild works from stored truth
- billing/reporting paths survive deployment reality
- `402 Payment Required` is enforced for the intended blocked state

## Non-goals for H2
Do not treat H2 as the phase for:
- broad product polish
- deep dashboard cosmetics
- pricing/package redesign
- major auth rewrites
- request-path rewrites unrelated to real cloud blockers

## Current execution sequence

### Stage 0 — Freeze the proof contract
**Done enough.**
The proof contract is now clear: the remaining work is not posture discovery.

### Stage 1 — Stand up the minimum cloud substrate
**Achieved.**
Railway app + Postgres + Redis are functioning.

### Stage 2 — Reproduce repository-backed truth
**Achieved enough to proceed.**
Identity/bootstrap/scope are working live.

### Stage 3 — Run proof-critical scenarios
**Partially achieved.**
Done:
- authenticated tenant traffic
- request accounting movement
- billing plan/subscription/period creation
- tenant billing overview coherence
- materialization/report path
- API-first savings evidence collection

Blocked:
- final enforcement proof under a boring, repeatable non-production threshold posture

### Stage 4 — Make redeploy and rebuild boring
**Not yet complete.**
Do after billing proof is coherent.

## Immediate next engineering tasks
1. inspect implemented admin billing routes vs the proof expectations
2. determine whether the correct route paths differ from the assumed ones, or whether the routes are actually missing
3. fix tenant overview so it resolves the existing open period into `current_billing_period`
4. resume the H2 billing flow:
   - materialize usage/ledger charges
   - summarize
   - reconcile
   - closeout/report
   - close
   - final tenant `402`

## Practical rule for the next engineer
Do not reopen cloud infra questions first.
The current evidence says:
- deployment substrate works
- request path works
- upstream provider path works
- the next real problem is billing/control-plane path correctness

## Exit criteria
H2 is done when:
- the cloud deployment reproduces the local Pilot proof contract
- the proof surfaces have retained evidence
- redeploy/restart does not break the proof path silently
- a cold engineer can reproduce the deployment and verification path from docs

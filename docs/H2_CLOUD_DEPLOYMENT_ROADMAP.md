# H2_CLOUD_DEPLOYMENT_ROADMAP

_Last updated: 2026-04-27_
_Audience: founding/principal engineers moving Metera from local Pilot proof to cloud-backed deployment proof without stalling adjacent maturity work._

## Purpose
H2 is not "make cloud production perfect."
H2 is to prove that the repaired local Pilot truth survives in a target cloud deployment with retained evidence.

That means the roadmap should optimize for:
- preserving the validated local contract
- proving the proof-critical path in one target cloud
- collecting evidence at each gate
- allowing selected H3/H4/H5 work to proceed in parallel where it does not destabilize the proof path

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
- packaging/pricing expansion
- ambitious auth rewrites
- replacing the request path that has already been re-proved locally
- solving every operator experience problem before the first cloud proof is complete

## Recommended target posture
For H2, pick one primary target deployment and optimize around finishing the proof there.

Recommended default:
- Railway for the first cloud proof, if speed and iteration matter more than deep infra control

Why Railway is good enough for H2:
- fast service deployment
- straightforward env/config management
- easy public endpoint exposure
- manageable path for app + database + worker style topology

Why not overcommit to Railway as strategy:
- H2 only needs proof, not final platform theology
- later phases may justify moving if enterprise/network/cost constraints dominate

## Workstreams

### WS1 — Deployment substrate and environment mapping
Objective:
Translate the validated local Pilot posture into an explicit cloud runtime contract.

Deliverables:
- target cloud service definition
- explicit environment variable matrix for local/pilot/cloud
- secret inventory with owners and expected values
- startup/readiness contract preserved in cloud
- deploy/redeploy checklist

Exit evidence:
- cloud instance boots only when required posture is valid
- `/health` and `/ready` behave the same way they do in the repaired local baseline

### WS2 — Stateful truth preservation
Objective:
Prove that truth-bearing state survives in hosted infrastructure.

Deliverables:
- repository-backed identity wired in cloud
- persistent database/storage selection documented
- migration/bootstrap path documented
- seed assumptions identified and either removed or explicitly declared

Exit evidence:
- identity survives deploy/restart
- request ledger persists and can be re-read
- system does not appear healthy while missing proof-critical state

### WS3 — End-to-end request-path proof
Objective:
Re-run the local Pilot proof surfaces in cloud, using retained evidence rather than vibes.

Proof cases:
- authenticated request accepted and attributed correctly
- request ledger entry created correctly
- rollups can be rebuilt from ledger truth
- billing/reporting path reflects ledger truth
- blocked/non-paying state produces real `402 Payment Required`

Exit evidence:
- saved request/response examples
- logs or artifacts showing attribution, ledger, rollup, and billing state
- reproducible proof script or operator runbook

### WS4 — Operator proof package
Objective:
Make H2 repeatable by a cold engineer, not only by the person who remembers the current state.

Deliverables:
- deployment runbook
- verification checklist
- recovery notes for common proof failures
- evidence bundle template

Exit evidence:
- a cold principal engineer can follow the documents and reproduce the cloud proof with minimal oral context

## Execution sequence

### Stage 0 — Freeze the proof contract
Before touching cloud:
- write down the exact local Pilot proof contract
- identify all proof-critical env vars, identities, and dependencies
- identify what is currently implicit, dev-seeded, or hand-held

Gate to continue:
- team agrees on what exactly counts as a successful H2 proof

### Stage 1 — Stand up the minimum cloud substrate
Build the thinnest useful target environment:
- app service
- persistent backing store(s)
- secrets/env wiring
- canonical deploy path

Do not add polish here.
The point is to reproduce the validated runtime truth in hosted form.

Gate to continue:
- app boots in cloud with valid posture
- `/ready` acts as the acceptance gate

### Stage 2 — Reproduce repository-backed truth
Focus on the stateful core:
- identity source
- tenant attribution prerequisites
- request ledger persistence
- rebuild prerequisites

Gate to continue:
- no proof-critical path depends on hand-edited local assumptions without explicit documentation

### Stage 3 — Run proof-critical end-to-end scenarios
Execute the actual cloud proof:
- good-path authenticated usage
- ledger and attribution verification
- rollup rebuild verification
- billing/reporting verification
- blocked-state `402` verification

Gate to continue:
- each proof surface has retained evidence
- failures are categorized as posture, truth, or derived-state failures

### Stage 4 — Make redeploy and rebuild boring
Once the first proof works, immediately test repeatability:
- redeploy
- restart
- rebuild/repair scenarios
- re-run the proof checklist

Gate to finish H2:
- proof survives redeploy/restart without heroics
- evidence and operator docs are current

## Suggested 6-week cadence

### Week 1 — Contract and cloud mapping
- freeze the local Pilot proof contract
- choose target cloud deployment shape
- map environment/secrets/storage explicitly
- write the H2 verification checklist

### Week 2 — First hosted boot
- get app running in cloud
- preserve `/health` and `/ready` semantics
- document deployment and posture expectations

### Week 3 — Truth-bearing state
- wire repository-backed identity
- verify tenant/auth attribution prerequisites
- verify persistent ledger truth

### Week 4 — Proof-critical scenarios
- run authenticated attribution scenario
- run ledger/rollup scenario
- run billing/reporting scenario
- verify real `402 Payment Required`

### Week 5 — Repeatability and failure handling
- test redeploy/restart/rebuild paths
- tighten runbooks
- categorize and close proof-path failures

### Week 6 — Evidence package and handoff
- produce retained proof artifacts
- write final operator proof package
- record what remains for H3/H4/H5

## Parallelization policy
H2 should remain the mainline proof path, but not the only active work.
The rule is simple:

Proceed in parallel only if the work either:
- removes hidden assumptions without rewriting the core proof path, or
- improves operator/product understanding around the proof path without changing truth semantics

Do not parallelize work that:
- changes core auth/identity architecture mid-proof
- rewrites the request path
- introduces major billing model changes
- turns H2 into a moving target

## What can run in parallel with H2

### Parallel-safe from H3
Safe during H2:
- documenting bootstrap assumptions
- reducing dev-seeded setup rituals
- designing explicit bootstrap/admin APIs
- building non-invasive tenant/operator onboarding scripts or runbooks

Usually wait until H2 proof is stable:
- large bootstrap flow rewrites
- heavy tenant lifecycle redesign that changes identity assumptions mid-proof

### Parallel-safe from H4
Safe during H2:
- deploy/restart/rebuild runbooks
- failure classification (posture vs truth vs derived state)
- debug/support visibility for proof-critical flows
- better observability around blocked tenants, rollups, scheduler/retry behavior

Usually wait until H2 proof is stable:
- aggressive scheduler/retry redesign
- deep operational architecture changes that alter core behavior under test

### Parallel-safe from H5
Safe during H2:
- reporting artifact cleanup that reflects existing truth
- support/admin surfaces that explain existing state better
- customer-grade presentation improvements for already-correct outputs

Usually wait until H2 proof is stable:
- broad UI/product-surface expansion
- cosmetic work not tied to proof, support, or customer trust

## Proposed staffing split
If there is bandwidth for parallel work:
- Mainline owner: H2 proof path, deployment substrate, proof execution
- Parallel owner A: H3 bootstrap/runbook cleanup that removes hidden setup rituals
- Parallel owner B: H4 operator visibility and recovery docs
- Optional parallel owner C: H5 reporting/support polish only where it clarifies already-proven truth

## Exit criteria
H2 is done when:
- the cloud deployment reproduces the local Pilot proof contract
- the proof surfaces have retained evidence
- redeploy/restart does not break the proof path silently
- a cold engineer can reproduce the deployment and verification path from docs

H2 is not blocked on:
- fully polished tenant onboarding
- final operator UX
- fully productized customer-facing surfaces

Those should advance in parallel where safe, then become primary in H3-H5 once the cloud proof is boring and repeatable.

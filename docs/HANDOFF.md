# HANDOFF

_Last updated: 2026-04-28 (late)_
_Audience: the next principal/founding engineer or agent taking over Metera._

Read this file first if you want the shortest path to competent action.

---

## 1) What Metera is
Metera is a **financial control plane for AI traffic** built around an **OpenAI-compatible gateway**.

The core runtime spine is:

`scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

The important truth boundaries are:
- `request_ledger` = accounting / usage truth
- rollups = derived summaries
- identity tables = identity truth
- billing periods + subscriptions = billing/commercial truth
- reports/invoices/dashboard = consumer surfaces layered on top of truth

Do not casually destabilize the request path to improve control-plane convenience.

---

## 2) Current project status
### Blunt status
Metera’s local Docker Pilot path is re-proved.
The Railway deployment is now also fully H2-proved:
- `/ready` green
- Redis active
- pgvector active
- repository identity active
- admin bootstrap works
- tenant scope resolution works
- live tenant chat traffic works through OpenAI
- tenant overview resolves the live billing period correctly
- admin billing report/materialization compatibility paths are live
- final API-first cloud billing flow was exercised through summarize/reconcile/close/report
- tenant-facing `402 Payment Required` was observed live in both `closing` and `closed` states

The current blocker is **not** infra anymore.
H2 is closed. The current work is now post-H2 hardening and release progression.

### What this means practically
Metera is not in “does the architecture work?” mode.
Metera is in:
- deployment maturity hardening
- operational clarity
- disciplined next-step execution
- post-H2 beta progression

---

## 3) What happened in the latest cloud session
The session moved H2 from “deployment struggling to come up” into “live request path is working, now fix the billing proof surface.”

### Major live issues found and fixed
- admin auth/header mismatch
- tenant identity key incorrectly forwarded upstream
- response model too strict for modern OpenAI payloads
- opaque upstream failures with poor diagnostics
- empty/default metadata forwarded upstream and rejected by OpenAI

### Result
The cloud request path now works end-to-end.

---

## 4) What is proved live in Railway now
Verified against `https://metera-api-production.up.railway.app`:
- `/ready` succeeds
- `/health` posture is good
- Redis active
- pgvector active
- repository identity active
- admin bootstrap works
- tenant billing scope resolution works
- live tenant chat request succeeds
- `stats/summary` increments on real traffic
- billing plan creation works
- billing subscription creation works
- billing period creation works
- admin billing-period listing works

---

## 5) Former blocking issue, now closed
The former unresolved cloud H2 blocker was:

### API-first commercial enforcement proof
That blocker is now closed.

Observed live and retained:
- billing admin route surface mismatch is fixed
- tenant billing overview/read-model mismatch is fixed
- API-first proof materializes and reports real traffic in cloud
- final `402` enforcement was proved in a repeatable API-first posture with retained evidence

That means the next engineer should work on:
- operator reproducibility cleanup
- proof harness/document polish
- post-H2 beta hardening

Do not restart the investigation from infra or OpenAI unless new contradictory evidence appears.

---

## 6) How to onboard fast
If you are the next agent/engineer, read in this order:
1. `docs/HANDOFF.md`
2. `docs/START_HERE.md`
3. `docs/CURRENT_STATE.md`
4. `docs/H2_SESSION_HANDOFF_2026-04-27.md`
5. `docs/H2_CLOUD_DEPLOYMENT_ROADMAP.md`
6. `docs/CLOUD_PROOF_CHECKLIST.md`
7. `docs/DEPLOYMENT_READINESS_PLAN.md`

Only go into `docs/archive/` if you need historical detail.

---

## 7) Canonical current live facts
### Live deployment
- `https://metera-api-production.up.railway.app`

### Probe tenant continuity
- tenant: `tenant_625fd7ed82c2452a87b72cae2b6653d6`
- workspace: `ws_ecd274ce87744afaaabbb74e275c0f72`
- namespace: `h2-probe-tenant-c-h2-probe-workspace-c`
- plan: `plan_740b273eafee4e6e92f938bc4e684864`
- subscription: `subscription_b9aed986c94c4ce8979be2cb8944297c`
- billing period: `billing_period_001af7ef5d6749eb9a6069a67617be7d`

These are useful anchors for takeover work.

---

## 8) The actual next job
The next job is **post-H2 cleanup and progression**.

### Specifically
1. keep `scripts/run_h2_cloud_proof_api.py` as the canonical H2 cloud proof harness
2. keep `scripts/run_h3_commercial_recovery_proof.py` as the active H3 recovery harness
3. keep `scripts/run_cloud_operator_flow.py` as the cold-operator entrypoint
4. keep direct DB seeding as local/internal validation only
5. preserve the retained proof packs:
   - `docs/archive/railway/H2_FINAL_402_EVIDENCE_2026-04-28.md`
   - `artifacts/h2_live_threshold_run.json`
   - `artifacts/h3_live_recovery_run_700.json`
6. preserve the resumed H3 proof artifacts captured from a true enforcement-stage checkpoint
7. preserve the semantic partitioning validation artifacts:
   - `artifacts/h3_multi_tenant_strict_partitioning_single_round.json`
   - `artifacts/h3_multi_tenant_strict_partitioning_soak.json`
8. continue beta hardening, restart/rebuild boringness, operator reproducibility, and broader multi-tenant confidence work

### Not the next job
- re-debug Redis
- re-debug pgvector
- re-debug OpenAI keys
- re-open local pilot architecture questions
- pretend H2 is still blocked by proof closure

---

## 9) Non-negotiable rules for the next engineer
1. Do not reopen solved lower-layer issues without contradictory runtime evidence.
2. Preserve truth boundaries:
   - ledger = accounting truth
   - rollups = derived
   - identity repo = identity truth
   - billing periods/subscriptions = commercial truth
3. If new docs are historical or one-off, place them under `docs/archive/...`, not back in top-level clutter.
4. Fix the first real billing/control-plane mismatch before broad refactors.

---

## 10) Blunt one-sentence summary
Metera’s cloud runtime and billing/control-plane proof path now survive real Railway deployment with retained final `402` evidence; H2 is closed, direct and resumed H3 recovery are both proved, and the frontier is operator boringness plus broader confidence expansion.
.

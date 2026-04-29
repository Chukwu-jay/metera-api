# Metera Current State

_Last updated: 2026-04-28 (late)_
_Audience: principal/founding engineers, takeover engineers, and operators._

## One-paragraph status
Metera is now past local-only proof. The Railway deployment is live at `https://metera-api-production.up.railway.app`, `/ready` is green, Redis is active, pgvector is active, repository-backed identity is active, admin bootstrap works, tenant API key scope resolution works, and real tenant chat traffic succeeds end-to-end against OpenAI. The earlier H2 billing/control-plane blocker is now resolved in cloud: tenant overview resolves the live billing period, the expected admin materialization/report surfaces are live, the final API-first commercial enforcement proof has been completed with retained evidence, and H3 resumed commercial recovery has now also been proved from a true enforcement-stage checkpoint with tenant-facing `402 Payment Required` in both `closing` and `closed` states followed by successful subscription activation and resumed `200` service. The earlier H3 semantic-cache isolation concern is now also closed: semantic retrieval is partitioned by tenant/workspace/namespace in the semantic store path, and both a strict single-round proof and a corrected 3-round soak proof now pass.

## Release posture
- **Pilot local:** re-proved
- **Cloud proof (H2):** complete
- **H3:** direct recovery proved, resumed recovery proved, multi-tenant semantic partitioning hardening proved
- **Beta modules:** broadly complete in code; next work is post-H2 hardening and reproducibility
- **Rollout:** not current

## What is done
### Local/runtime baseline
- exact cache
- semantic cache
- DLP scrubbing
- OpenAI-compatible chat path
- repository-backed identity
- richer authenticated `ProxyContext`
- request-ledger persistence
- rollups and analytics derivation
- billing control plane foundations
- tenant billing/reporting foundations
- commercial enforcement loop

### Cloud/runtime achievements from 2026-04-27 onward
- isolated `workspace/metera` into its own Git repo and pushed to `https://github.com/Chukwu-jay/metera-api.git`
- Railway app service deployed successfully
- strict startup posture is now valid in cloud
- `/health` green with Redis + pgvector active
- `/ready` green with repository identity posture
- admin bootstrap route works live:
  - `POST /admin/control/bootstrap/tenant-environment`
- tenant scope resolution works live:
  - `GET /control/tenant/billing/scope`
- live tenant chat completions now succeed through Metera to OpenAI
- request metrics and cost accounting now move on real cloud traffic
- admin plan/subscription/billing-period creation works live
- admin billing-period listing works live
- direct H3 recovery proof complete
- resumed H3 recovery proof complete
- semantic cache multi-tenant partitioning now enforced in the store/query path and re-proved with strict and soak validation

## Important bugs fixed during cloud proof and hardening
These were real blockers or correctness gaps found and fixed:
- admin auth/header mismatch (`x-metera-admin-key` vs `Authorization: Bearer`)
- tenant identity key was being forwarded upstream instead of using `METERA_UPSTREAM_API_KEY`
- nested response models were too strict for current OpenAI chat response fields
- upstream provider errors were too opaque to debug quickly
- empty/default `metadata` was being forwarded upstream and rejected by OpenAI unless `store` was enabled
- semantic cache isolation was convention-dependent on namespace only; semantic storage/lookup now includes first-class `tenant_id` and `workspace_id` scope
- H3 multi-tenant proof harness had an outdated billing materialization endpoint assumption; corrected to the current admin route surface
- H3 multi-round soak expectations were over-strict across later rounds; corrected so valid later same-tenant semantic reuse is not misclassified as leakage

## Current live truth
Verified live against Railway:
- public URL: `https://metera-api-production.up.railway.app`
- `/ready` returns success
- `/health` shows:
  - cache backend active = `redis`
  - semantic store active = `pgvector`
  - identity mode = `repository`
- real authenticated tenant request succeeds and returns metera attribution fields
- `stats/summary` increments on real traffic
- strict single-round semantic partitioning proof passes
- corrected 3-round semantic partitioning soak proof passes

## What changed in the semantic partitioning hardening
Code paths updated:
- `app/storage/semantic_base.py`
- `app/cache/semantic_cache.py`
- `app/storage/semantic_memory.py`
- `app/storage/semantic_pgvector.py`
- `app/services/proxy_service.py`
- `scripts/run_h3_multi_tenant_correctness.py`
- `scripts/semantic_pgvector_proof.py`

Functional change:
- semantic records now carry `tenant_id` and `workspace_id`
- semantic lookup now filters on `tenant_id`, `workspace_id`, and `namespace`
- pgvector schema now includes `tenant_id` and `workspace_id`
- pgvector lookup uses scoped matching instead of namespace-only matching
- store indexing now includes a tenant/workspace/namespace/model-family scope index

Why this matters:
- before: semantic isolation depended on namespace discipline
- now: semantic isolation is structurally enforced at the storage/query layer

## What is still not done
### Post-H2 / H3 work
1. **Operator reproducibility cleanup**
   - keep the cloud proof path boring for cold engineers and future operators
   - reduce doc drift across handoff/readiness/checklist files
   - continue making long proof runs resumable, inspectable, and failure-readable

2. **Threshold/proof posture ergonomics**
   - preserve `METERA_BILLING_PATRONAGE_THRESHOLD_USD` as the explicit non-production proof lever
   - avoid future giant proof floods when smaller controlled threshold posture is sufficient
   - remember that script-side target savings do not modify the actual live enforcement threshold

3. **Post-H2 beta hardening**
   - continue deployment maturity, restart/rebuild boringness, and operator clarity

4. **Broader multi-tenant/concurrency confidence**
   - the current semantic partitioning gap is closed for the tested proof shapes
   - continue from correctness-first validation toward noisy-neighbor, sustained-load, and broader concurrency confidence
   - keep proving that attribution, accounting, and cache behavior remain aligned under pressure

5. **Observability / operator ergonomics**
   - improve concise health summaries, incident probes, and recovery playbooks for billing/control-plane issues

## Current interpretation
Metera is no longer blocked by infra, Railway posture, Redis, pgvector, identity bootstrap, upstream OpenAI wiring, tenant overview resolution, missing billing admin paths, final cloud enforcement proof, or the earlier semantic-cache isolation question surfaced by the first H3 soak investigation.
H2 is closed. The current work is now post-H2 hardening and release progression.

## Canonical current commands / probes
### Live readiness
```powershell
Invoke-WebRequest https://metera-api-production.up.railway.app/ready -UseBasicParsing
```

### Live admin bootstrap
```powershell
Invoke-WebRequest -Method Post `
  -Uri 'https://metera-api-production.up.railway.app/admin/control/bootstrap/tenant-environment' `
  -Headers @{ 'x-metera-admin-key'='<admin-key>'; 'Content-Type'='application/json' } `
  -Body '{...}'
```

### Live tenant traffic
```powershell
Invoke-WebRequest -Method Post `
  -Uri 'https://metera-api-production.up.railway.app/v1/chat/completions' `
  -Headers @{ 'Authorization'='Bearer <tenant-key>'; 'x-metera-namespace'='<namespace>'; 'Content-Type'='application/json' } `
  -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: H2_MANUAL_PROBE_OK"}],"temperature":0}'
```

## Immediate next work
1. preserve `scripts/run_h2_cloud_proof_api.py` as the canonical H2 cloud proof harness
2. preserve `scripts/run_h3_commercial_recovery_proof.py` as the active H3 recovery-proof harness and `scripts/run_cloud_operator_flow.py` as the cold-operator entrypoint
3. keep direct DB seeding as local/internal validation only, not as the source-of-truth cloud acceptance path
4. retain and reference the final cloud evidence packs:
   - `docs/archive/railway/H2_FINAL_402_EVIDENCE_2026-04-28.md`
   - `artifacts/h2_live_threshold_run.json`
   - `artifacts/h3_live_recovery_run_700.json`
   - `artifacts/h3_resume_final_checkpoint.json`
   - `artifacts/h3_resume_final_seed.json`
   - `artifacts/h3_resume_final_result.json`
   - `artifacts/h3_multi_tenant_strict_partitioning_single_round.json`
   - `artifacts/h3_multi_tenant_strict_partitioning_soak.json`
5. next concrete hardening tasks:
   - continue operator reproducibility cleanup
   - preserve the semantic partitioning evidence and explanation in active docs
   - expand multi-tenant/noisy-neighbor confidence beyond the current proof shape
   - keep proof harnesses boring and endpoint-current

## Rules
- `request_ledger` is accounting truth
- rollups are derived
- identity tables are identity truth
- billing periods + subscriptions are billing/commercial truth
- do not reopen solved cloud infra questions unless new runtime evidence contradicts them

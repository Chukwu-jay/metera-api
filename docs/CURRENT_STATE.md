# Metera Current State

_Last updated: 2026-04-28 (early)_
_Audience: principal/founding engineers, takeover engineers, and operators._

## One-paragraph status
Metera is now past local-only proof. The Railway deployment is live at `https://metera-api-production.up.railway.app`, `/ready` is green, Redis is active, pgvector is active, repository-backed identity is active, admin bootstrap works, tenant API key scope resolution works, and real tenant chat traffic now succeeds end-to-end against OpenAI. The earlier H2 billing/control-plane blocker is fixed in cloud: tenant overview now resolves the live open billing period, and the expected admin materialization/report surfaces are live. The current remaining H2 frontier is no longer route completeness; it is **repeatable API-first commercial enforcement proof** without relying on direct database seeding or large provider-expensive threshold runs.

## Release posture
- **Pilot local:** re-proved
- **Cloud proof (H2):** substantially advanced, not complete
- **Beta modules:** still broadly complete in code, but cloud billing proof remains incomplete
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

### Cloud/runtime achievements from 2026-04-27
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

## Important bugs fixed during cloud proof
These were real blockers found and fixed on 2026-04-27:
- admin auth/header mismatch (`x-metera-admin-key` vs `Authorization: Bearer`)
- tenant identity key was being forwarded upstream instead of using `METERA_UPSTREAM_API_KEY`
- nested response models were too strict for current OpenAI chat response fields
- upstream provider errors were too opaque to debug quickly
- empty/default `metadata` was being forwarded upstream and rejected by OpenAI unless `store` was enabled

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

## What is still not done
### H2 cloud proof blockers
1. **Final API-first commercial enforcement proof**
   - we still need a boring, repeatable cloud-side `402 Payment Required` proof path
   - the old direct-DB proof harness is not appropriate as the canonical cloud verification path

2. **Proof economics / operator reproducibility**
   - cloud proof should report prompts, cache hit rate, total tokens saved, avoided-cost percentage, and repo-native realized savings ratio together
   - proof should remain API-first and not depend on Railway-internal database access

3. **Threshold/proof posture hardening**
   - for controlled cloud proof runs, we need an explicit non-production threshold/config path instead of giant traffic bursts that risk provider TPM/rate-limit failures

## Current interpretation
Metera is no longer blocked by infra, Railway posture, Redis, pgvector, identity bootstrap, upstream OpenAI wiring, tenant overview resolution, or the missing billing admin paths.
The current work is now squarely an **API-first proof-hardening and enforcement-verification problem**.

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
1. use the API-first proof runner at `scripts/run_h2_cloud_proof_api.py` as the canonical cloud proof harness
2. keep direct DB seeding as local/internal validation only, not as the source-of-truth cloud acceptance path
3. for controlled cloud proof runs, use `METERA_BILLING_PATRONAGE_THRESHOLD_USD` as the explicit non-production lever instead of giant prompt floods
4. complete and retain final cloud `402` evidence using that API-first path

## Rules
- `request_ledger` is accounting truth
- rollups are derived
- identity tables are identity truth
- billing periods + subscriptions are billing/commercial truth
- do not reopen solved cloud infra questions unless new runtime evidence contradicts them

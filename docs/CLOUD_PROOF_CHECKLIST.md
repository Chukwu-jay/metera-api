# Cloud Proof Checklist

_Last updated: 2026-04-28 (early)_
_Audience: principal/founding engineers proving that Metera's repaired local Pilot contract survives cloud deployment._

This checklist remains relevant.
It is the practical H2 execution path, but it has been updated to reflect what is already done and what is still actually blocked.

## 1) Current cloud proof stance
Treat this as **controlled cloud deployment proof**, not broad production readiness.

Preserve these rules:
- `/ready` is the deployment acceptance gate
- `/health` is liveness + posture snapshot only
- `request_ledger` is accounting truth
- rollups are derived
- identity repository is identity truth
- do not reopen solved local Pilot architecture questions without contradictory runtime evidence

## 2) Already achieved in the current Railway deployment
These are no longer aspirational:
- app deploys on Railway
- `/ready` succeeds
- `/health` shows Redis + pgvector active
- repository-backed identity is active
- admin bootstrap works
- tenant API key scope resolution works
- authenticated tenant traffic succeeds through Metera to OpenAI
- request/cost metrics move on real traffic
- billing plan creation works
- subscription creation works
- billing period creation works
- admin billing period listing works

Public deployment used in proof:
- `https://metera-api-production.up.railway.app`

## 3) Still required to finish H2
### 3.1 Final commercial enforcement proof
Still required:
- final live cloud `402 Payment Required`
- retain evidence of the triggering billing/commercial state
- prove this through the real API path, not by writing synthetic ledger rows directly into Railway Postgres

### 3.2 Proof economics / reporting clarity
Required:
- retain prompts, cache hit rate, total tokens saved, avoided-cost percentage, and repo-native realized savings ratio together
- distinguish clearly between:
  - avoided-cost percentage (human/business framing)
  - realized savings ratio (repo/internal ratio currently returned by billing reports)

### 3.3 Controlled threshold posture
Required:
- use an explicit non-production threshold/config lever for proof runs when needed
- avoid giant request bursts that mainly test upstream TPM limits rather than Metera correctness

## 4) Canonical verified probes
### 4.1 `/health`
Expected now and already observed:
- HTTP 200
- `status = ok`
- cache requested backend = `redis`
- cache active backend = `redis`
- semantic store requested backend = `pgvector`
- semantic store active backend = `pgvector`
- identity posture visible

### 4.2 `/ready`
Expected now and already observed:
- HTTP 200
- `status = ready`
- `identity_mode = repository`
- `cache_backend = redis`
- `semantic_store_backend = pgvector`

### 4.3 Admin bootstrap
Expected now and already observed:
- `POST /admin/control/bootstrap/tenant-environment` works

### 4.4 Tenant billing scope
Expected now and already observed:
- `GET /control/tenant/billing/scope` works from proxy context

### 4.5 Authenticated traffic proof
Expected now and already observed:
- tenant `POST /v1/chat/completions` succeeds
- metera attribution fields appear in the response
- stats/summary increments

## 5) Current probe continuity objects
Useful live IDs from the current cloud proof session:
- tenant: `tenant_625fd7ed82c2452a87b72cae2b6653d6`
- workspace: `ws_ecd274ce87744afaaabbb74e275c0f72`
- namespace: `h2-probe-tenant-c-h2-probe-workspace-c`
- plan: `plan_740b273eafee4e6e92f938bc4e684864`
- subscription: `subscription_b9aed986c94c4ce8979be2cb8944297c`
- billing period: `billing_period_001af7ef5d6749eb9a6069a67617be7d`

## 6) What to do next
1. run `scripts/run_h2_cloud_proof_api.py` as the canonical cloud proof harness
2. if a controlled proof run needs a smaller enforcement threshold, set `METERA_BILLING_PATRONAGE_THRESHOLD_USD` explicitly in non-production cloud posture
3. retain the API-first evidence bundle and final `402` output
4. do not treat Railway-internal database seeding as the canonical cloud proof path

## 7) Evidence to retain
Keep a durable proof pack containing:
- deployed env posture used
- `/health` output
- `/ready` output
- bootstrap output
- tenant billing scope output
- successful authenticated traffic sample
- stats/summary after live traffic
- billing period creation output
- admin billing-period listing output
- next materialization/report/summarize/reconcile outputs once fixed
- final cloud `402` output when reached

Without retained evidence, cloud proof becomes storytelling.

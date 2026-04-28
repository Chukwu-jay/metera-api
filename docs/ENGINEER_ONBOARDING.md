# Metera Engineer Onboarding

_Last updated: 2026-04-28_
_Audience: engineers taking over development, debugging, operations, or deployment work._

## First 15 minutes
Read in this order:
1. `docs/START_HERE.md`
2. `docs/CURRENT_STATE.md`
3. `docs/BETA_MASTER_MAP.md`
4. `docs/PILOT_RUNBOOK.md`
5. `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`

That is enough to orient a cold senior engineer.

## Mental model
Metera is a financial control plane around an OpenAI-compatible gateway.

Runtime spine:

`app -> Metera -> scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

The stable center is the request path. Do not destabilize it casually.

## Current project reality
You are not trying to discover whether the architecture works.
That part is proved.

You are working in the phase after proof:
- preserve runtime correctness
- preserve source-of-truth boundaries
- improve reproducibility, productization, and deployment readiness
- document changes so the next engineer does not need archaeology

## Canonical local workflow
Start the stack in explicit pilot posture:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Verify:

```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/identity/status
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/request-ledger?limit=5
```

Interpretation:
- `/health` = liveness + posture snapshot
- `/ready` = strict readiness gate for pilot/deployment acceptance
- if `/health` is green but `/ready` is not, the stack booted but the posture is wrong or degraded

Run the canonical local proof:

```bash
docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

Run the canonical cloud/API-first proof:

```bash
python scripts/run_h2_cloud_proof_api.py
```

Important:
- `scripts/run_h2_cloud_proof.py` is the older direct-DB seeding harness and should not be treated as the canonical cloud acceptance path
- `scripts/run_h2_cloud_proof_api.py` is the source-of-truth cloud proof path because it drives the real admin + tenant APIs

## Expected healthy pilot posture
- identity mode is `repository`
- request ledger returns rows
- rollup rebuild succeeds
- proof script succeeds
- proof includes real `402 Payment Required`

## Code hotspots
- `app/core/lifecycle.py`
- `app/core/app_services.py`
- `app/core/db.py`
- `app/api/routes_chat.py`
- `app/services/proxy_service.py`
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/rollups.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/repositories/commercial_events.py`
- `app/api/routes_tenant_billing.py`
- `app/api/routes_observability_admin.py`

## Operating rules
- `request_ledger` is accounting truth
- billing periods + subscriptions are billing truth
- rollups are derived
- authenticated tenant scope is the intended path
- query-param tenant fallback is transitional only
- preserve the request path; harden around it
- direct DB seeding is acceptable for local/internal validation, but not as the canonical cloud proof path
- customer-facing savings should usually be framed as avoided-cost percentage, while repo-native `realized_savings_ratio` remains an internal/reporting ratio

## What not to do first
Do not begin with:
- a proxy rewrite
- a broad auth rewrite
- payment integration
- dashboard cosmetics
- infra scaling as a substitute for code clarity

## Docs rule
Top-level `docs/` should contain only active source-of-truth docs.
Historical, superseded, and exploratory docs belong in `docs/archive/`.

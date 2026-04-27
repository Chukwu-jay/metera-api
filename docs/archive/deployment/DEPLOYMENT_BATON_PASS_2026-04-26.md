# Deployment Baton Pass — Metera

## How to use this handoff set
- Read this file when you need the fastest possible handoff.
- Read `docs/DEPLOYMENT_DOCS_MASTER_2026-04-26.md` for the full strategic picture.
- Read `docs/DEPLOYMENT_DOCS_EXECUTION_2026-04-26.md` for the concrete deployment sequence and validation steps.

## Principal engineer stance
- Preserve the validated request path.
- Do not reopen solved Pilot questions without contradictory runtime evidence.
- Do not rewrite the proxy to solve deployment friction.
- Treat `request_ledger` as truth; everything else is downstream or derived.
- Optimize for a credible reachable Beta deployment, then close bootstrap/readiness gaps.

---

## Status
- **Pilot:** done
- **Beta modules:** done
- **Beta overall:** ~90% done
- **Rollout:** not done

What is already proved:
- repository-backed identity
- authenticated request attribution
- `request_ledger` persistence
- rollup rebuilds
- billing summarize / reconcile / close / report / invoice
- tenant billing/reporting reads
- threshold lifecycle `open -> closing -> closed`
- real proxy `402 Payment Required`

Canonical proof snapshot:
- seeded requests: `1100`
- upstream cost: `$66.00`
- realized savings: `$55.00`
- tokens saved: `168,297`
- savings ratio: `83.33%`

---

## Current commercial truth
- threshold = `$50.00`
- threshold is **recurring per billing period**
- blocking starts for non-active subscriptions at `closing`
- reason mapping:
  - `closing -> patronage_required`
  - `closed -> service_suspended`
- tenant billing/report/history reads remain available while serving is blocked

---

## Why Docker Compose keeps confusing people
Plain:

```bash
docker compose up -d --build
```

is **not enough** for Pilot-truth.

Use:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Why:
- the stack can look healthy while Pilot flags are wrong
- `metera-app` does not bind-mount repo changes
- local fixes may exist in workspace but not in the running app container
- proof/image parity can drift

---

## Exact local proof commands
Start Pilot posture:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Health:

```bash
curl http://127.0.0.1:8000/health
```

Identity status:

```bash
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/identity/status
```

Ledger check:

```bash
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/request-ledger?limit=5
```

Rollup rebuild:

```bash
docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py"
```

Canonical proof:

```bash
docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

---

## What was pushed yesterday
- `ba1c0f7` — verified identity and billing stack for Railway beta deploy
- `18fca4e` — `.dockerignore` cleanup
- `12e66c1` — deployable Railway beta app folder consolidation
- `78d7124` — Railway start command port fix
- `8c57391` — identity and billing admin routers mounted

---

## Immediate deployment target
Use **Railway** first.

Target shape:
- public: `metera-api`
- private: `metera-postgres`, `metera-redis`
- no dashboard
- no mock-upstream
- no test-runner

Mandatory DB step:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Deployment proof gates
A deploy is not done unless all are true.

### Gate 1 — Runtime truth
- public HTTPS endpoint exists
- Redis active, not fallback
- pgvector active, not fallback
- Postgres private
- Redis private

### Gate 2 — Commercial truth
- threshold crossing drives `closing`
- `closing -> patronage_required`
- blocked tenant gets `402` at `closing`
- explicit close drives `closed`
- `closed -> service_suspended`
- blocked tenant gets `402` at `closed`

### Gate 3 — Operator evidence
Retain:
- public URL
- branch + commit SHA
- health snapshot
- summarize/reconcile/closeout outputs
- commercial events before/after close
- `402` at `closing`
- `402` at `closed`
- rollback path

---

## Biggest remaining gap
Not infrastructure.

It is **control-plane bootstrap**.

Still missing cleanly from the live product surface:
- create tenant
- create workspace
- issue API key
- one-shot bootstrap tenant environment

Right now, cloud proof still depends on seeded identity unless bootstrap routes are implemented.

---

## Next 5 actions
1. Deploy Metera to Railway with Postgres + Redis.
2. Verify `/health` beyond top-level `ok`.
3. Reproduce the commercial `402` path in cloud.
4. Preserve the evidence bundle.
5. Implement or finish admin bootstrap routes for tenant/workspace/API key creation.

---

## After that
Next tranche:
- strict readiness semantics
- API-first proof path
- reporting polish
- rollup/recovery hardening
- broader tenant-facing product maturity
- later: payments + rollout ops

---

## Minimal reading list
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/RAILWAY_BETA_DEPLOY_SPEC_2026-04-25.md`
- `docs/RAILWAY_DEPLOY_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_API_TEST_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_BETA_GAP_ANALYSIS_2026-04-25.md`

---

## One-line handoff
Metera’s spine is proved; the next job is not architecture discovery but clean Railway deployment, live `402` commercial proof, and closure of the bootstrap/readiness gaps without destabilizing the validated system.

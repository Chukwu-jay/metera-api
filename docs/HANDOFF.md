# HANDOFF

_Last updated: 2026-04-26_
_Audience: the next principal/founding engineer or agent taking over Metera._

Read this file first if you want the shortest path to competent action.

---

## 1) What Metera is
Metera is a **financial control plane for AI traffic** built around an **OpenAI-compatible gateway**.

The core runtime spine is:

`scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

This is the main mental model for the whole repo.

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
Metera’s local Docker Pilot path has been **re-proved** on 2026-04-26.

That means the following are currently working again in the repaired runtime:
- repository-backed identity
- authenticated tenant/workspace/api-key attribution
- request-ledger persistence
- rollup rebuilds
- billing summarize / reconcile / close
- tenant-facing billing/reporting reads
- commercial lifecycle events
- real proxy enforcement via `402 Payment Required`
- canonical proof script `scripts/pilot_proof_v1.py`

### What this means practically
Metera is **not** in “does the architecture work?” mode.
That question is answered.

Metera **is** in:
- deployment proof
- deployment maturity hardening
- productization
- operational clarity
- disciplined next-step execution

---

## 3) What went wrong before this handoff
There was a contradiction between older validated docs and the current local runtime.

The older docs were mostly right.
The local runnable system had drifted.

### The repaired issues were:
1. **runtime/source wiring drift**
   - startup/runtime behavior no longer matched the validated docs
2. **compose env posture drift**
   - `.env.pilot.local` existed, but `docker-compose.yml` was not actually passing the intended pilot flags into `metera-app`
3. **identity bootstrap mismatch**
   - startup degraded into `static_fallback` instead of repository-backed identity because config defaults did not match repository truth
4. **rollup conflict bug**
   - namespace rollup uniqueness was too weak and could collide
5. **documentation sprawl**
   - top-level docs had too many competing “truth” documents

### Net interpretation
Do **not** infer that Pilot proof was fake.
Infer that runtime/source/image/config parity had drifted and has now been repaired enough to re-prove the local path.

---

## 4) What was repaired
### Code areas materially touched/repaired
- `app/core/config.py`
- `app/core/lifecycle.py`
- `app/core/app_services.py`
- `app/core/db.py`
- `app/core/dependencies.py`
- `app/api/routes_chat.py`
- `app/services/proxy_service.py`
- `app/controlplane/repositories/rollups.py`
- `docker-compose.yml`

### Important behavior restored
- pilot env flags now actually reach `metera-app`
- identity mode now returns to **repository** instead of `static_fallback`
- request ledger works again
- rollup rebuild works again
- proof script works again in the canonical `metera-app` target

---

## 5) Current validated proof state
The canonical local Pilot proof is working again.

### Revalidated live on 2026-04-26 and posture-hardened on 2026-04-27
- `/health` green
- `/ready` returns strict readiness success in pilot-local posture
- Redis active
- pgvector active
- `/admin/identity/status` reports repository mode
- authenticated chat traffic includes tenant/workspace/api-key attribution
- `/admin/control/request-ledger` returns rows
- rollup rebuild succeeds
- `scripts/pilot_proof_v1.py` succeeds inside `metera-app`

### Proof outputs still align with the known Pilot proof
- realized savings: **$55.00**
- tokens recovered: **168,297**
- savings ratio: **83.33%**
- lifecycle: `open -> closing -> closed`
- real post-close `402 Payment Required`

That is enough to treat the local Pilot path as re-proved.

---

## 6) Beta status
The original Beta module map is effectively complete and has now been revalidated against the repaired runtime.

### Module 1 — reliability / auth / reporting baseline
See:
- `docs/MOD_BETA_RELIABILITY.md`
- `docs/BETA_TENANT_AUTH_MODEL.md`

### Module 2 — commercial policy
See:
- `docs/MOD_COMMERCIAL_POLICY.md`
- `docs/BETA_COMMERCIAL_POLICY_DECISIONS.md`

### Module 3 — operator cleanliness / proof hygiene
See:
- `docs/MOD_OPERATOR_CLEANLINESS.md`
- `docs/BETA_OPERATOR_CLEANLINESS_VALIDATION_2026-04-25.md`

### Practical interpretation
Do **not** spend time rediscovering the meaning of the three Beta modules.
Treat them as largely closed and move into deployment/readiness/productization work.

---

## 7) What the docs look like now
The docs tree was cleaned on 2026-04-26.

### Top-level `docs/` now contains only active source-of-truth docs
Core active docs:
- `docs/START_HERE.md`
- `docs/HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/ENGINEER_ONBOARDING.md`
- `docs/BETA_MASTER_MAP.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- module docs and their supporting references
- `docs/DOCS_CANONICAL_MAP.md`

### Historical/superseded docs were moved into archive
- `docs/archive/pilot/`
- `docs/archive/beta/`
- `docs/archive/deployment/`
- `docs/archive/railway/`
- `docs/archive/bootstrap/`
- `docs/archive/legacy/`

Rule: if a doc is historical, superseded, one-off, or exploratory, it belongs in archive, not top-level.

---

## 8) How to onboard fast
If you are the next agent/engineer, read in this order:
1. `docs/HANDOFF.md`
2. `docs/START_HERE.md`
3. `docs/CURRENT_STATE.md`
4. `docs/BETA_MASTER_MAP.md`
5. `docs/PILOT_RUNBOOK.md`
6. `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
7. `docs/DEPLOYMENT_READINESS_PLAN.md`

Only go into `docs/archive/` if you need historical detail.

---

## 9) Canonical local commands
### Start in explicit pilot posture
```bash
docker compose --env-file .env.pilot.local up -d --build
```

### Quick checks
```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/identity/status
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/request-ledger?limit=5
```

Interpretation:
- `/health` confirms liveness and shows posture detail
- `/ready` is the strict deployment/pilot acceptance gate
- do not accept a deployment on `/health` alone

### Rollup rebuild
```bash
docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py"
```

### Canonical proof
```bash
docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

### Healthy expected identity posture
- `identity_enabled = true`
- `identity_mode = repository`
- `repository_available = true`

---

## 10) Are we ready to try cloud deployment again?
**Yes.**

But use the right framing:
- ready for **controlled cloud deployment proof**
- **not** ready to assume finished deployment maturity

That means the next stage is to prove that the repaired local truth survives in cloud.

---

## 11) The actual next job
The next job is **cloud deployment proof + deployment maturity closure**.

### Do not treat this as architecture discovery
The next engineer should not rewrite fundamentals.
The next engineer should verify that the already-proved local system survives deployment cleanly.

### Recommended next-work focus
Use these as the practical next objectives:
1. treat H1 as closed baseline work unless contradictory runtime evidence appears
2. deploy to cloud (Railway or chosen target) using the repaired baseline
3. confirm health, identity posture, ledger, rollups, billing, and proof path in cloud
4. confirm commercial enforcement survives in cloud (`402` path)
5. identify remaining bootstrap/API-first/operator-flow gaps
6. document the cloud proof and maturity blockers clearly without reintroducing doc sprawl

### What “finished deployment maturity” still means
Use `docs/PHASE_2_HARDENING_PLAN.md` as the concrete working plan.

Important note:
- the Docker/Compose env posture fix is now treated as part of **H1 — configuration and posture hardening**, not just an isolated repair

The best planning references are now:
- `docs/PHASE_2_HARDENING_PLAN.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`

Historical deployment-specific detail now lives in:
- `docs/archive/deployment/`
- `docs/archive/railway/`

---

## 12) Non-negotiable rules for the next engineer
1. Do not reopen solved Pilot architecture questions without contradictory runtime evidence.
2. Do not use Git history as sole truth for the current repo state.
3. Trust the cleaned top-level docs before archive docs.
4. Do not rewrite the proxy path to solve deployment maturity issues.
5. Preserve truth boundaries:
   - ledger = accounting truth
   - rollups = derived
   - identity repo = identity truth
   - billing periods/subscriptions = commercial truth
6. If new docs are historical or one-off, place them under `docs/archive/...`, not back in top-level clutter.

---

## 13) Blunt one-sentence summary
Metera is past “can this work?” and now in “prove the repaired system survives cloud deployment cleanly, then harden it into repeatable product operation” mode.

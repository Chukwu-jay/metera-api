# Metera Railway Handoff — 2026-04-25

## Executive summary

Today established that the **Metera app can build and run on Railway** with:
- Docker build from `metera/`
- Redis active
- pgvector active
- `/health` returning healthy runtime state

However, the final attempt to expose the new identity/billing admin routes failed after a code change that mounted additional routers in `app/main.py`. The last Railway deployment **built successfully** but **never passed healthcheck**.

This means tomorrow should start from a **clean Railway project**, but **not from zero knowledge**. The major deployment unknowns were resolved today.

---

## Source of truth

### Git branch
- Branch: `metera/beta-identity-billing-stack`

### Important pushed commits
- `12e66c1` — `metera: consolidate deployable Railway beta app folder`
- `78d7124` — `metera: fix Railway start command port expansion`
- `8c57391` — `metera: mount identity and billing admin routers`

### Key local docs created/used today
- `metera/docs/RAILWAY_OPERATOR_CHECKLIST_2026-04-25.md`
- `metera/docs/RAILWAY_HANDOFF_2026-04-25.md` (this file)

---

## What happened today

## 1) Initial deployment handoff and repo triage
A PDF handoff in Downloads instructed using:
- `metera/docs/RAILWAY_OPERATOR_CHECKLIST_2026-04-25.md`

Early repo inspection found:
- many modified/untracked files
- the deployable app lived under `metera/`
- the surrounding workspace contained unrelated files/projects, including old robotics artifacts

### Important lesson
Railway must treat `metera/` as the deployment root. Deploying from repo root risks serving the wrong project.

---

## 2) First repo staging strategy was too surgical
An overly narrow staging plan initially omitted deploy-critical files such as:
- `metera/Dockerfile`
- `metera/pyproject.toml`

This caused confusion around whether the project expected:
- `requirements.txt`
- `Caddyfile`

It does **not**. The actual deploy model is:
- `Dockerfile`
- `pyproject.toml`
- `railway.json`

### Correction made
The staging strategy was changed from “surgical selected files only” to “the full deployable `metera/` app folder, with env/pilot junk excluded.”

---

## 3) `.dockerignore` was broken and would have sabotaged Railway
A bad `metera/.dockerignore` had been left behind from the earlier surgical approach. It effectively excluded most of the real app context.

### Fix made
`metera/.dockerignore` was rewritten to allow the actual runtime build context while excluding:
- `.env*`
- local test/build artifacts
- temp scripts
- docs/tests not needed in image

This was a critical fix.

---

## 4) Local Docker validation succeeded
A real local Docker build was run from `metera/`:

```powershell
docker build -t metera-local-verify .
```

### Result
- Build succeeded locally.
- This confirmed the Dockerfile/build context were coherent before Railway deployment.

---

## 5) Railway startup failed because `$PORT` was not expanded
The first successful cloud build still failed at container startup.

### Symptom
Railway logs showed:
- `Error: Invalid value for '--port': '$PORT' is not a valid integer.`

### Cause
`railway.json` used:

```json
"startCommand": "python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

Railway passed `$PORT` literally instead of shell-expanding it.

### Fix made
`railway.json` was changed to:

```json
"startCommand": "sh -c 'python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'"
```

### Commit
- `78d7124`

---

## 6) Runtime health was achieved for the base app
After the start-command fix, the app booted and `/health` responded.

### Verified intermediate state
- service started
- `/health` returned 200
- root `/` returned 404 (acceptable; no homepage route)

This confirmed the base app could run on Railway.

---

## 7) Redis wiring initially failed because the wrong env var names were used
Initial Railway variables used names like:
- `CACHE_BACKEND`
- `VECTOR_STORE_BACKEND`
- `ADMIN_SECRET_KEY`

### Cause
The Metera app uses:
- `env_prefix = "METERA_"`
- `extra = "ignore"`

So it only reads names such as:
- `METERA_EXACT_CACHE_BACKEND`
- `METERA_REDIS_URL`
- `METERA_SEMANTIC_STORE_BACKEND`
- `METERA_SEMANTIC_STORE_DSN`
- `METERA_POLICY_STORE_DSN`
- `METERA_ADMIN_API_KEY`
- `METERA_UPSTREAM_API_KEY`

### Important lesson
Old/generic config names are silently ignored.

---

## 8) Redis was fixed
Once the correct env names were set and the Redis reference was corrected, `/health` eventually showed:
- `cache.requested_backend = redis`
- `cache.active_backend = redis`
- `cache.fallback_active = false`

This proved Redis runtime wiring was correct.

---

## 9) pgvector was fixed
There was confusion for a while because semantic store health showed:
- requested backend looked like `pgvector`
- active backend remained `memory`

The most likely issues during debugging were:
- bad/misread backend string
- wrong or unresolved Postgres DSN references
- ambiguity caused by truncated health outputs

Eventually a full health result showed:
- `semantic.store.requested_backend = pgvector`
- `semantic.store.active_backend = pgvector`
- `semantic.store.fallback_active = false`

This proved pgvector runtime wiring was also correct.

### Critical successful runtime state achieved today
At one point the deployment was confirmed healthy with:
- Redis active
- pgvector active
- no fallback-to-memory

This is the biggest operational win from today.

---

## 10) Live admin/control-plane route testing exposed a code wiring issue
After runtime was healthy, live tests attempted to use control-plane routes like:
- `/admin/identity/status`
- `/admin/control/tenants`

### Result
They returned 404.

### Cause
The route files existed in the repo, but `app/main.py` only mounted:
- health
- chat
- stats
- metrics
- legacy admin router

It did **not** mount the new identity/billing/admin control-plane routers.

### Fix made
`app/main.py` was patched to include:
- `routes_identity_admin`
- `routes_billing_admin`
- `routes_observability_admin`
- `routes_policy_admin`
- `routes_rollups_admin`
- `routes_tenant_billing`

### Commit
- `8c57391`

---

## 11) Final deployment after router-mount commit failed healthcheck
The latest Railway log (`logs.1777169520920.log`) shows:
- Docker build succeeded
- image built and imported successfully
- Railway started healthcheck on `/health`
- every healthcheck attempt failed with `service unavailable`
- replica never became healthy

### Important detail
The log captured is primarily a **build/healthcheck log**, not a detailed Python stacktrace from the failed app runtime.

### What is known
- the failure happened **after** commit `8c57391`
- the earlier app version **did** become healthy
- therefore the new router-mount change almost certainly introduced:
  - an import-time error, or
  - a startup-time error, or
  - a route/module dependency failure

### Most likely failure point
The new routers are now being imported, but one or more of them likely depend on code/state not safely initialized in production startup.

This is the main unresolved issue heading into tomorrow.

---

## Confirmed facts for tomorrow

## Infrastructure facts already proven
These do **not** need to be rediscovered:
- Railway must build from `metera/`
- Docker deployment works from `metera/`
- `railway.json` start command needed shell expansion for `$PORT`
- Redis can be wired successfully
- pgvector can be wired successfully
- `/health` can report healthy Redis + pgvector state

## App behavior facts already proven
- chat app runs
- `/health` route works
- root `/` can legitimately 404

## App integration fact still unresolved
- mounting the new identity/billing/admin routers currently breaks the deployment healthcheck

---

## Likely root causes to investigate tomorrow

Priority suspects after commit `8c57391`:

1. **Import-time dependency break in one of the newly mounted routers**
   - missing import path
   - model mismatch
   - repository dependency mismatch

2. **Startup-time dependency break caused by one of the new router stacks**
   - state/service assumptions not available in production startup
   - policy/control-plane repositories expecting DB schema/state not present

3. **Hidden route module import chain error**
   - `app.main` imports router
   - router imports repository/service/model
   - import explodes before app becomes healthy

4. **Potential mismatch between committed code and runtime assumptions**
   - route files present, but not all required support code was production-ready

---

## Recommended implementation plan for tomorrow

## Phase 1 — Start clean on Railway
Create a **new Railway project** instead of trying to salvage the old one.

### Rebuild sequence
1. Create empty Railway project
2. Add Postgres service
3. Enable extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Add Redis service
5. Add GitHub repo service
6. Set:
   - branch = `metera/beta-identity-billing-stack`
   - root directory = `metera/`
7. Add variables with correct `METERA_...` names
8. Deploy

---

## Phase 2 — First target a known-good healthy base runtime
Do **not** begin tomorrow by chasing the admin routers immediately.

First goal:
- restore the previously proven healthy state where `/health` shows:
  - Redis active
  - pgvector active
  - no fallback

### If using branch head causes immediate failure
Be prepared to temporarily back out or isolate commit `8c57391` so the known-good runtime can be re-established first.

That means tomorrow’s first decision should be:
- determine whether to deploy **before** or **after** router-mount commit `8c57391`

Recommended:
- if speed matters, deploy a known-good health state first
- then add the new routers in a controlled follow-up deploy

---

## Phase 3 — Diagnose router-mount failure separately
Once base runtime is healthy again:

1. inspect startup logs immediately after adding router-mount change
2. identify exact failing module/import
3. patch only that issue
4. redeploy
5. verify admin routes exist:
   - `/admin/identity/status`
   - `/admin/control/tenants`

---

## Phase 4 — Final functional proof
After admin routes are truly live:

1. Verify identity routes respond
2. Verify billing/control-plane routes respond
3. Run live passthrough smoke test
4. Run 402 enforcement proof:
   - threshold crossing returns 402
   - `closing -> patronage_required`
   - `closed -> service_suspended`

---

## Recommended Railway variables for tomorrow

```env
METERA_EXACT_CACHE_BACKEND=redis
METERA_REDIS_URL=${{metera-redis.REDIS_URL}}

METERA_SEMANTIC_STORE_BACKEND=pgvector
METERA_SEMANTIC_STORE_DSN=${{metera-postgres.DATABASE_URL}}
METERA_POLICY_STORE_DSN=${{metera-postgres.DATABASE_URL}}

METERA_ADMIN_API_KEY=<real admin key>
METERA_UPSTREAM_BASE_URL=https://api.openai.com
METERA_UPSTREAM_API_KEY=<real upstream key>
```

### Notes
- prefer unquoted Railway references if the UI supports them cleanly
- exact service reference labels may differ slightly in the Railway picker UI
- the critical point is that they resolve to real values

---

## Security / cleanup note
A real OpenAI API key was temporarily placed into Railway for smoke-test purposes.

Tomorrow:
- confirm whether that key should remain in production
- if not, rotate/remove it

---

## Bottom line
Today was not a loss.

### What was successfully established
- correct deployment root
- correct Docker setup
- correct env naming scheme
- correct Redis wiring
- correct pgvector wiring
- correct `/health` target state

### What remains
- make the newly mounted control-plane routers boot safely in production
- then run the 402 commercial proof flow

The cleanest path tomorrow is:
1. rebuild Railway cleanly
2. restore known-good health state first
3. isolate and fix the router-mount failure
4. only then run the control-plane and 402 proof tests

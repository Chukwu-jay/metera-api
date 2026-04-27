# Railway Deploy Sequence — 2026-04-25

This is the **exact operator sequence** for getting Metera onto Railway today.

It assumes:
- the repo already contains `Dockerfile`
- the repo already contains `railway.json`
- you want one public Metera API service
- you want managed Postgres + managed Redis
- you are **not** deploying dashboard, mock upstream, or test runner

---

## Outcome

At the end of this sequence you should have:
- one public HTTPS Metera endpoint
- one private Railway Postgres instance
- one private Railway Redis instance
- Metera using Redis as exact cache
- Metera using Postgres/pgvector as semantic + policy store
- a live environment ready for cloud repro of the `402` enforcement path

---

## 0. Preflight repo check

From the Metera repo root, verify these files exist:

- `Dockerfile`
- `railway.json`
- `.env.railway.beta.example`
- `docs/RAILWAY_BETA_DEPLOY_SPEC_2026-04-25.md`

If the repo root is not `metera/`, note that now because Railway service root will need to point at `metera/`.

---

## 1. Create Railway project

### Dashboard path
1. Open Railway dashboard
2. Click **New Project**
3. Choose **Empty Project**
4. Name it something like:
   - `metera-beta`

This project will contain three services:
- `metera-api`
- `metera-postgres`
- `metera-redis`

---

## 2. Add Postgres

### Dashboard path
1. Inside the project, click **New**
2. Choose **Database**
3. Choose **Postgres**
4. Rename service to:
   - `metera-postgres`

### Immediate post-create step
Open the Postgres query editor and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This is mandatory for the intended semantic-store topology.

Do not skip this and assume it is already active.

---

## 3. Add Redis

### Dashboard path
1. Click **New**
2. Choose **Database**
3. Choose **Redis**
4. Rename service to:
   - `metera-redis`

No public networking required.
No extra ports required.

---

## 4. Add the application service

### Dashboard path
1. Click **New**
2. Choose **GitHub Repo**
3. Select the repository containing Metera
4. Rename service to:
   - `metera-api`

### Important root-directory rule
If the GitHub repo contains multiple projects and `metera/` is a subfolder, set:
- **Root Directory** = `metera`

If the GitHub repo itself is already the Metera repo root, leave root directory blank.

### Build config expectations
Because the repo now has `railway.json`, Railway should use:
- Dockerfile build
- start command from `railway.json`
- `/health` health check from `railway.json`

---

## 5. Configure environment variables for `metera-api`

Open the **Variables** tab for `metera-api`.
Use **Raw Editor** and paste the following.

```env
METERA_ENVIRONMENT=beta
METERA_UPSTREAM_BASE_URL=https://api.openai.com
METERA_UPSTREAM_API_KEY=REPLACE_ME
METERA_UPSTREAM_TIMEOUT_SECONDS=60
METERA_UPSTREAM_MAX_RETRIES=1

METERA_EXACT_CACHE_BACKEND=redis
METERA_REDIS_URL=${{metera-redis.REDIS_URL}}

METERA_SEMANTIC_ENABLED=true
METERA_SEMANTIC_STORE_BACKEND=pgvector
METERA_SEMANTIC_STORE_DSN=${{metera-postgres.DATABASE_URL}}
METERA_POLICY_STORE_DSN=${{metera-postgres.DATABASE_URL}}

METERA_REQUEST_EVENT_LOGGING_ENABLED=true
METERA_REQUEST_LEDGER_ENABLED=true
METERA_RISK_EVENT_LOGGING_ENABLED=true
METERA_SHADOW_SAVINGS_LOGGING_ENABLED=true
METERA_POLICY_TIMING_BREAKDOWN_ENABLED=true

METERA_ROLLUPS_ENABLED=true
METERA_BILLING_PREP_ENABLED=false
METERA_CONTROLPLANE_IDENTITY_ENABLED=false
METERA_CONTROLPLANE_IDENTITY_SEED_ENABLED=false
METERA_CONTROLPLANE_STATIC_API_KEY=
METERA_ADMIN_API_KEY=REPLACE_WITH_LONG_RANDOM_ADMIN_KEY

METERA_SCOPED_POLICY_ENABLED=true
METERA_TENANT_QUERY_PARAM_FALLBACK_ENABLED=true
METERA_IDENTITY_GUARD_ENABLED=true
METERA_IDENTITY_STRICT_MODE_ENABLED=true
METERA_IDENTITY_PARTITIONING_ENABLED=true
METERA_MULTIMODAL_HARD_ALIGNMENT_ENABLED=true

METERA_SEMANTIC_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
METERA_SEMANTIC_THRESHOLD=0.9
METERA_SEMANTIC_SHADOW_THRESHOLD=0.8
METERA_SEMANTIC_MAX_TEMPERATURE=0.2
METERA_DUAL_MODE_ENABLED=true
METERA_SEMANTIC_DISABLED_NAMESPACE_PREFIXES=
METERA_SEMANTIC_HIGH_RISK_NAMESPACE_PREFIXES=faq-billing

METERA_DEFAULT_EXACT_TTL_SECONDS=3600
METERA_DEFAULT_SEMANTIC_TTL_SECONDS=86400

METERA_DLP_ENABLED=true
METERA_DLP_ANALYZER_MODE=auto
METERA_DLP_SCRUB_LEVEL=technical
METERA_DLP_CUSTOM_DETECTORS_JSON=[{"name":"internal_session_token","pattern":"\\bmetera_tok_[A-Za-z0-9]{24}\\b"},{"name":"internal_db_password","pattern":"internal_pwd_[A-Za-z0-9]{12}","replacement":"[REDACTED_INTERNAL_DB_PASSWORD]"}]
METERA_DLP_CUSTOM_DETECTORS_YAML_PATH=./config/detectors.example.yaml

METERA_NAMESPACE_HEADER=x-metera-namespace
METERA_PROVIDER_AUTH_HEADER=authorization
```

### Replace before deploy
You must replace at least:
- `METERA_UPSTREAM_API_KEY`
- `METERA_ADMIN_API_KEY`

### Secret handling rule
Do **not** commit real values into:
- `.env.railway.beta.example`
- `railway.json`
- docs

Secrets live in Railway Variables only.

---

## 6. Trigger first deploy

After variables are saved, let Railway deploy automatically or trigger a manual deploy.

Expected startup behavior:
- Docker image builds from `Dockerfile`
- app starts with `uvicorn`
- health checks hit `/health`

Because the app warms the sentence-transformer model at startup, allow a longer-than-usual first boot.
That is why `healthcheckTimeout` is generous.

---

## 7. Enable public networking

For `metera-api`:
1. Open **Networking**
2. Enable **Public Networking**
3. Generate a Railway domain

You should now have a public URL like:
- `https://metera-api-production-xxxx.up.railway.app`

Custom domain can wait until after runtime validation.

---

## 8. Verify health correctly

Do **not** stop at top-level `status: ok`.

Run:

```bash
curl https://YOUR_PUBLIC_DOMAIN/health
```

You want all of these to be true:
- `status == ok`
- `cache.active_backend == redis`
- `cache.fallback_active == false`
- `semantic.store.active_backend == pgvector`
- `semantic.store.fallback_active == false`

### Why this matters
The current `/health` endpoint is permissive: the app can still return `ok` while falling back to memory.
For Beta credibility, that is not enough.

---

## 9. Basic smoke test

Send a normal request through the public endpoint using a controlled tenant context.

Confirm:
- request reaches real upstream
- success response comes back
- no obvious auth/header regressions
- no cache/store fallback warnings appear in `/health`

---

## 10. Cloud `402` enforcement proof

This is the real release gate.

You need to demonstrate live behavior for the commercial path.

### Required truth conditions
- blocking begins at `closing`
- response is `402 Payment Required`
- reason is `patronage_required`
- once actually `closed`, blocked state reason is `service_suspended`

### Evidence to retain
Capture at minimum:
- billing period state before threshold crossing
- threshold crossing action
- response body for first blocked request at `closing`
- any commercial event rows or logs showing `patronage_required`
- blocked response after `closed`
- any commercial event rows or logs showing `service_suspended`

If those mappings are not true in cloud, do not call the rollout complete.

---

## 11. Minimal rollback procedure

If deploy is bad:
1. Open `metera-api`
2. Go to **Deployments**
3. Roll back to the previous healthy deployment
4. Re-check `/health`
5. Reconfirm Redis + pgvector are active

Do not do destructive DB changes during this first lift.
Keep rollback app-level whenever possible.

---

## 12. Recommended operator notes to record immediately

Create a short deployment note containing:
- public URL
- Railway project name
- deployed branch
- deployed commit SHA
- whether pgvector extension was enabled successfully
- health payload snapshot
- whether the `402` cloud proof has been completed yet

This avoids chat archaeology later.

---

## Exact fast-path summary

If you want the compressed version:

1. Create empty Railway project
2. Add Postgres service -> run `CREATE EXTENSION IF NOT EXISTS vector;`
3. Add Redis service
4. Add GitHub repo service for `metera-api`
5. Set root directory to `metera/` if needed
6. Paste variables from `.env.railway.beta.example`
7. Replace real secrets in Railway UI
8. Deploy
9. Enable public domain
10. `curl /health` and confirm Redis + pgvector are actually active
11. Reproduce live `402` path:
   - `closing -> patronage_required`
   - `closed -> service_suspended`

---

## Bottom line

This is the shortest path to a credible external Metera Beta:
- managed infra
- same runtime contract
- one public API
- private data services
- commercial enforcement proof as the real acceptance gate

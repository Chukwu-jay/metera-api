# Railway Beta Deploy Spec — 2026-04-25

## Decision

Use **Railway** as the immediate cloud target for Metera Beta.

Why this is the right choice for *today*:
- fastest path from the current Dockerfile/Compose proof to a reachable HTTPS endpoint
- easy separation of app / Postgres / Redis into managed services
- private networking by default between services
- low operational drag compared with ECS for a same-day lift
- maps cleanly to the cloud manifest's required topology

This is intentionally a **founding-engineer speed-to-credible-beta** move, not the final production platform decision.

---

## What this spec produces

### Public surface
- `metera-api` Railway service
- one public HTTPS domain for the API

### Private stateful services
- Railway Postgres service
- Railway Redis service
- no public Postgres ingress
- no public Redis ingress

### Explicit non-goals for this first lift
- no public dashboard
- no mock-upstream in cloud runtime
- no test-runner service in runtime
- no horizontal scaling yet
- no broad platform abstraction layer for multi-cloud today

---

## Source mapping from docker-compose

### Keep
- `metera` app service -> Railway service from repo Dockerfile
- environment-driven runtime contract
- `/health` health gate
- Postgres-backed policy + semantic stores
- Redis exact cache

### Remove from cloud runtime
- `mock-upstream`
- `metera-test`
- `metera-dashboard`
- host port publishing assumptions
- local/default secrets

### Replace
- `pgvector` container -> Railway Postgres service with pgvector extension enabled
- `redis` container -> Railway managed Redis service

---

## Repository artifact

This repo now includes:
- `railway.json`

It defines:
- Dockerfile build
- app start command using Railway's injected `$PORT`
- `/health` deployment health check
- conservative restart policy

---

## Railway project shape

Create **one Railway project** with these services:

1. `metera-api`
   - source: this repository
   - root: `metera/`
   - config file: `railway.json`
   - public networking: enabled

2. `metera-postgres`
   - source: Railway Postgres database service
   - private networking only
   - after provisioning, enable pgvector with:
     - `CREATE EXTENSION IF NOT EXISTS vector;`

3. `metera-redis`
   - source: Railway Redis database service
   - private networking only

Do **not** deploy separate services for dashboard, mock upstream, or tests in this same-day lift.

---

## Required variables for `metera-api`

Paste these in Railway Raw Editor, then replace placeholder values.

```env
METERA_ENVIRONMENT=beta

# real upstream only
METERA_UPSTREAM_BASE_URL=https://api.openai.com
METERA_UPSTREAM_API_KEY=REPLACE_ME
METERA_UPSTREAM_TIMEOUT_SECONDS=60
METERA_UPSTREAM_MAX_RETRIES=1

# exact cache
METERA_EXACT_CACHE_BACKEND=redis
METERA_REDIS_URL=${{metera-redis.REDIS_URL}}

# semantic / policy stores
METERA_SEMANTIC_ENABLED=true
METERA_SEMANTIC_STORE_BACKEND=pgvector
METERA_SEMANTIC_STORE_DSN=${{metera-postgres.DATABASE_URL}}
METERA_POLICY_STORE_DSN=${{metera-postgres.DATABASE_URL}}

# observability / evidence retention toggles
METERA_REQUEST_EVENT_LOGGING_ENABLED=true
METERA_REQUEST_LEDGER_ENABLED=true
METERA_RISK_EVENT_LOGGING_ENABLED=true
METERA_SHADOW_SAVINGS_LOGGING_ENABLED=true
METERA_POLICY_TIMING_BREAKDOWN_ENABLED=true

# control plane / commercial
METERA_ROLLUPS_ENABLED=true
METERA_BILLING_PREP_ENABLED=false
METERA_CONTROLPLANE_IDENTITY_ENABLED=false
METERA_CONTROLPLANE_IDENTITY_SEED_ENABLED=false
METERA_CONTROLPLANE_STATIC_API_KEY=
METERA_ADMIN_API_KEY=REPLACE_WITH_LONG_RANDOM_ADMIN_KEY

# policy / identity safety
METERA_SCOPED_POLICY_ENABLED=true
METERA_TENANT_QUERY_PARAM_FALLBACK_ENABLED=true
METERA_IDENTITY_GUARD_ENABLED=true
METERA_IDENTITY_STRICT_MODE_ENABLED=true
METERA_IDENTITY_PARTITIONING_ENABLED=true
METERA_MULTIMODAL_HARD_ALIGNMENT_ENABLED=true

# semantic behavior
METERA_SEMANTIC_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
METERA_SEMANTIC_THRESHOLD=0.9
METERA_SEMANTIC_SHADOW_THRESHOLD=0.8
METERA_SEMANTIC_MAX_TEMPERATURE=0.2
METERA_DUAL_MODE_ENABLED=true
METERA_SEMANTIC_DISABLED_NAMESPACE_PREFIXES=
METERA_SEMANTIC_HIGH_RISK_NAMESPACE_PREFIXES=faq-billing

# ttl / dlp / headers
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

Notes:
- The `${{service.VAR}}` syntax is Railway reference-variable syntax; wire it in the UI if the raw form does not resolve automatically in your workflow.
- `METERA_UPSTREAM_BASE_URL` should point to the actual provider target for beta, not `mock-upstream`.
- `METERA_ADMIN_API_KEY` must be rotated away from all dev defaults.

---

## Same-day deployment sequence

### 1. Push repo state
Ensure the current Metera repo branch contains:
- `Dockerfile`
- `railway.json`
- the current application code

### 2. Create Railway project
- new empty project
- add Postgres
- add Redis
- add GitHub repo service for `metera-api`

### 3. Point service root correctly
If the GitHub repository root is above `metera/`, set the Railway service root directory to `metera/`.
If the repository itself is already the `metera/` directory, leave root at repo root.

### 4. Set variables
Add the variables block above to `metera-api`.
Replace all placeholders.

### 5. Enable pgvector
Open the Railway Postgres query editor and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This is mandatory if Metera is expected to use the pgvector semantic store instead of silently falling back.

### 6. Deploy
Trigger deploy.

### 7. Confirm health
Expected initial check:

```bash
curl https://YOUR_METERA_DOMAIN/health
```

Minimum acceptable result:
- `status: ok`
- `cache.active_backend: redis`
- `semantic.store.active_backend: pgvector`
- fallback flags should be `false`

If app comes up as `status: ok` but Redis or pgvector show fallback, do **not** call that deployment complete.
That means the platform is reachable but the intended architecture is not actually active.

---

## Critical acceptance gates

### Gate 1 — Runtime topology truth
Pass only if:
- API is publicly reachable over HTTPS
- Redis is active, not memory fallback
- semantic store is pgvector, not memory fallback
- Postgres and Redis are private only

### Gate 2 — Commercial credibility truth
Pass only if live behavior proves:
- threshold-crossing tenant reaches `402 Payment Required`
- `closing -> patronage_required`
- `closed -> service_suspended`
- no contradictory commercial event semantics in retained evidence

### Gate 3 — Operator minimum
Pass only if you have retained:
- public URL
- exact deployed commit SHA
- variable inventory minus secret values
- procedure to roll back to previous Railway deployment
- evidence capture for the cloud `402` proof

---

## Live verification checklist

### Health
- `GET /health`
- verify no fallback warnings

### Basic data plane
- send a normal upstream-backed request through Metera
- verify success path
- verify event/ledger activity is being written

### Commercial proof
Use the existing local proof posture as the baseline and repro it in cloud.
Preserve artifacts showing:
- billing period state before threshold crossing
- threshold crossing event
- `402` response payload
- commercial event emitted at `closing`
- commercial event emitted at `closed`

This is the real release gate, per the manifest.

---

## Rollback posture

For this first Railway lift, rollback is intentionally simple:
- rollback app service to prior successful deployment in Railway
- do not mutate Postgres/Redis destructively during deploy
- keep schema/extension changes minimal and additive

Do not couple the first cloud lift to a risky schema migration program.

---

## Sharp edges / known constraints

1. **Railway does not run `docker-compose.yml` directly**
   Compose is reference topology only.

2. **`depends_on` does not exist in the same way**
   Metera must tolerate dependency startup ordering and retry cleanly.

3. **`/health` is currently liveness-ish, not strict readiness**
   It can still report `status: ok` while fallbacks are active.
   Founding-engineer interpretation: inspect the returned backend fields, not only the top-level status.

4. **Semantic model startup cost is real**
   The container warms a local sentence-transformer model during startup.
   Leave health timeout generous.

5. **Do not expose dashboard yet**
   It adds attack surface and support burden without increasing beta credibility enough to justify it today.

---

## Why not ECS today?

ECS is viable later, but it is the wrong first move for this exact moment because it adds:
- VPC/subnet/security-group ceremony
- ALB/target-group setup
- task-definition drift risk
- more time spent on infrastructure than on proving commercial correctness

The manifest's sequencing is explicit: deploy fast, then repro the `402` path in cloud.
Railway is the better execution choice for that.

---

## Bottom line

This Railway spec is the concrete same-day lift:
- one public app service
- one managed Postgres with pgvector enabled
- one managed Redis
- no mock services
- no public dashboard
- health-gated deployment
- cloud proof of `402` consistency as the real acceptance test

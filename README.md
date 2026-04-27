# Metera

**Metera is the financial control plane for enterprise AI.**

Stop paying the **Safety Tax**.
Metera is a local governance layer that measures, secures, and reduces your LLM infrastructure costs without forcing your team to relax production safety blindly.

For non-technical teams, the short version is simple:

- **you spend less** because repeated or similar AI requests can be handled locally
- **you expose less risk** because sensitive content is scrubbed before caching or upstream calls
- **you gain visibility** because Metera shows both realized savings and unrealized savings opportunity
- **you stay in control** because lower-threshold experiments can run in shadow mode without changing live production behavior

## Who this is for

Metera is for teams that are already using OpenAI-compatible APIs and want stronger control over cost, privacy, and governance without rebuilding their applications from scratch.

Typical users:

- **Finance leaders** who want visibility into AI spend and unrealized savings
- **Platform / infrastructure teams** who need a local control layer in front of upstream models
- **Engineering teams** who want caching and semantic reuse without giving up safety controls
- **Security-conscious organizations** that want local scrubbing before data reaches external model providers

Metera sits between your application and an OpenAI-compatible upstream model endpoint. It is designed to:

- scrub sensitive inputs before cache operations
- reduce cost through exact and semantic reuse
- keep namespace boundaries explicit
- expose cost, savings, and policy signals
- support conservative production behavior with measurable shadow-mode opportunity

Core request flow:

**scrub first → exact cache → semantic cache → upstream → observe everything → govern safely**

## Before / after

### Before Metera

```text
Application → Upstream LLM API
```

Every request goes straight to the model provider, even when:
- the answer was already seen
- the request is only a light paraphrase
- the prompt contains sensitive content that should be scrubbed first

### After Metera

```text
Application → Metera → scrub → exact cache → semantic cache → upstream (only if needed)
```

This turns the model path into a governed pipeline instead of a direct spend pipe.

---

## Why teams use Metera

Enterprise AI teams often overpay because they keep semantic reuse thresholds high to avoid incorrect reuse.
That caution is understandable, but expensive.
Metera helps Finance and Engineering teams work together by making the tradeoff visible instead of guesswork.

In plain terms, Metera helps teams answer:

- Are we paying for the same AI work over and over again?
- How much could we save if we loosened semantic policy safely?
- Are we sending sensitive content upstream that should have been scrubbed first?
- Can we improve AI cost control without changing every application integration?

Metera is built to help teams:

- **eliminate the Compute Tax** through validated local reuse and a shared-embedder architecture
- **reduce the Safety Tax** by measuring unrealized savings in shadow mode before changing policy
- **protect private data** with local PII/secret scrubbing before cache or upstream calls
- **govern production safely** with explicit admin controls, policy persistence, and namespace isolation

## One-line integration

Metera is a drop-in proxy for OpenAI-compatible clients.
In the simplest case, integrating it means pointing your existing client to Metera's local base URL.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key",
)
```

That is often enough to start routing requests through Metera's local control plane.

## Financial Control Panel

Metera also includes a read-only Streamlit dashboard for non-technical visibility into AI economics and system health.

Local URL:
- <http://localhost:8501>

The dashboard highlights:
- **Realized Savings** already captured by caching
- **Safety Tax** (shadow savings opportunity) still left on the table
- observed upstream spend
- cache hit rate
- persisted shadow analytics evidence behind the savings story

### What you should expect to see

For demos or stakeholder reviews, the dashboard is designed to answer a few questions immediately:

- **Are we saving money yet?**
  - see the **Realized Savings** card
- **Are we still being too conservative?**
  - see the **Safety Tax** card and comparison chart
- **Is the system healthy?**
  - see the DB / cache / embedder status strip
- **Is the savings story backed by evidence?**
  - see the shadow analytics evidence table

A good live demo sequence is:

1. open the dashboard at `http://localhost:8501`
2. run a validation or 100-request load test
3. watch the cards and chart update
4. show the shadow analytics table as proof behind the Safety Tax number

## What Metera does

Metera currently provides:

- OpenAI-compatible `POST /v1/chat/completions`
- exact-match caching
- semantic caching with pgvector support
- local DLP scrubbing
- namespace isolation across read, write, and admin paths
- admin policy endpoints with persisted overrides
- shadow-mode analytics for lower-threshold opportunity measurement
- `/health`, `/stats/summary`, and `/metrics`

For non-streaming requests, the default decision order is:

1. normalize the request
2. scrub sensitive content locally
3. check exact cache
4. check semantic cache
5. call upstream only if needed
6. record cost / savings / cache outcome
7. return response metadata
8. run shadow-threshold analytics in the background for live misses

Important note:
- exact cache is always checked before semantic cache
- repeated identical prompts should be expected to return `exact_hit`, not `semantic_hit`

---

## Installation

## Prerequisites

Recommended:

- Python `3.12+`
- Docker + Docker Compose
- a reachable OpenAI-compatible upstream endpoint

Optional but strongly recommended:

- Postgres with pgvector for persisted semantic cache
- Redis for exact cache

## Local development install

From the `metera/` directory:

```bash
cp .env.example .env
pip install -e .
python -m uvicorn app.main:app --reload
```

## Docker-based install

From the `metera/` directory:

```bash
docker compose up -d --build
```

This brings up:

- `metera-app`
- `metera-redis`
- `metera-pgvector`
- `metera-mock-upstream` (for deterministic local validation)
- `metera-test-runner` (when explicitly started)

## Docker image build

```bash
docker build -t metera:local .
```

Run it with an env file:

```bash
docker run --rm -p 8000:8000 --env-file .env metera:local
```

---

## Quick start

### 1) Configure environment

Copy the example env file:

```bash
cp .env.example .env
```

Important values:

- `METERA_UPSTREAM_BASE_URL`
- `METERA_UPSTREAM_API_KEY`
- `METERA_REDIS_URL`
- `METERA_SEMANTIC_STORE_DSN`
- `METERA_POLICY_STORE_DSN`
- `METERA_ADMIN_API_KEY`

### 2) Start services

```bash
docker compose up -d --build
```

### 3) Verify health

```bash
python scripts/smoke_test.py
```

That script waits for app readiness and then validates:

- `/health`
- chat completion flow
- `/stats/summary`

---

## Production deployment

## Recommended production topology

Use:

- Metera app container(s)
- Redis for exact cache
- Postgres + pgvector for semantic persistence and policy persistence
- a real upstream LLM provider endpoint

Recommended production settings:

- exact cache backend: `redis`
- semantic store backend: `pgvector`
- live semantic threshold: `0.9`
- shadow semantic threshold: `0.8`

## Production deployment checklist

1. provision Postgres with pgvector
2. provision Redis
3. create a dedicated restricted DB role
4. apply least-privilege SQL from:
   - `scripts/sql/create_metera_least_privilege.sql`
5. set production secrets via environment / secret manager
6. bootstrap the persistent policy row:

```bash
PYTHONPATH=. python scripts/bootstrap_policy_store.py
```

7. run smoke validation
8. verify `/admin/policy`, `/health`, and `/stats/summary`

## Production notes

- do not use `postgres` superuser credentials for the app in production
- do not expose admin endpoints without setting `METERA_ADMIN_API_KEY`
- do not rely on in-memory policy state for production governance
- use `SECURITY.md` for credential rotation guidance

---

## Configuration reference

## Core upstream settings

- `METERA_UPSTREAM_BASE_URL`
  - OpenAI-compatible upstream base URL
- `METERA_UPSTREAM_API_KEY`
  - upstream API key
- `METERA_PROVIDER_AUTH_HEADER`
  - defaults to `authorization`

## Exact cache settings

- `METERA_EXACT_CACHE_BACKEND`
  - `memory` or `redis`
- `METERA_REDIS_URL`
  - Redis connection URL
- `METERA_DEFAULT_EXACT_TTL_SECONDS`
  - default exact cache TTL

## Semantic cache settings

- `METERA_SEMANTIC_ENABLED`
  - enable/disable semantic reuse
- `METERA_SEMANTIC_STORE_BACKEND`
  - `memory` or `pgvector`
- `METERA_SEMANTIC_STORE_DSN`
  - pgvector/Postgres DSN
- `METERA_SEMANTIC_MODEL_NAME`
  - current default: `sentence-transformers/all-MiniLM-L6-v2`
- `METERA_SEMANTIC_THRESHOLD`
  - live semantic threshold
- `METERA_SEMANTIC_SHADOW_THRESHOLD`
  - lower shadow threshold for analytics only
- `METERA_SEMANTIC_MAX_TEMPERATURE`
  - reuse allowed only up to this temperature
- `METERA_DEFAULT_SEMANTIC_TTL_SECONDS`
  - default semantic TTL

## Policy persistence settings

- `METERA_POLICY_STORE_DSN`
  - Postgres DSN for persisted admin policy state

If unset:
- policy overrides fall back to in-memory runtime state

## DLP settings

- `METERA_DLP_ENABLED`
- `METERA_DLP_ANALYZER_MODE`
- `METERA_DLP_SCRUB_LEVEL`
- `METERA_DLP_CUSTOM_DETECTORS_JSON`
- `METERA_DLP_CUSTOM_DETECTORS_YAML_PATH`

Custom detector YAML uses `yaml.safe_load()`.

## Namespace and admin settings

- `METERA_NAMESPACE_HEADER`
  - defaults to `x-metera-namespace`
- `METERA_ADMIN_API_KEY`
  - required to use admin endpoints safely

---

## Admin API

All admin endpoints require:

```http
x-metera-admin-key: <METERA_ADMIN_API_KEY>
```

Current admin surface:

- `GET /admin/policy`
- `POST /admin/policy`
- `POST /admin/cache/invalidate`
- `POST /admin/detectors/dry-run`

Policy behavior:

- persisted admin policy includes:
  - `semantic_threshold`
  - `semantic_shadow_threshold`
- bootstrap defaults are seeded into Postgres
- current production-intended defaults are:
  - `semantic_threshold = 0.9`
  - `semantic_shadow_threshold = 0.8`

---

## First-run validation checklist

Use this after first install or after major changes.

### Minimum validation

1. start stack:

```bash
docker compose up -d --build
```

2. smoke test:

```bash
python scripts/smoke_test.py
```

3. bootstrap persisted policy:

```bash
PYTHONPATH=. python scripts/bootstrap_policy_store.py
```

### Semantic validation

Semantic demo:

```bash
python scripts/demo_semantic_hit.py
```

This validates:
- first request indexes a miss
- second paraphrased request becomes a semantic hit

### Shadow-mode validation

```bash
python scripts/validate_shadow_mode.py
```

This validates:
- live miss at `0.9`
- shadow hit recorded at lower threshold
- persisted shadow analytics row exists

### Full validation slice

```bash
python scripts/validate_system_slice.py
```

This validates:
- concurrency behavior
- percentile reporting
- default policy fallback
- drift sensitivity around thresholds
- retention purge
- namespace isolation

### Containerized tests

```bash
make test-in-container
```

### Dependency audit

Run in the test container:

```bash
docker exec metera-test-runner sh -lc "cd /app && PYTHONPATH=. python -m pip_audit"
```

---

## Observability

Metera exposes:

- `GET /health`
- `GET /stats/summary`
- `GET /metrics`

Current observability includes:

- request totals
- exact / semantic hits and misses
- semantic shadow-hit analytics counters
- backend fallback posture
- token and cost estimation
- estimated cache savings
- admin invalidation counts
- latency summaries

Shadow mode:

- live misses can trigger lower-threshold semantic checks after the response is sent
- shadow analytics do not change production responses
- shadow analytics do not store embedding vectors
- retention cleanup purges analytics older than 14 days

---

## Security

Start with:

- `SECURITY.md`

That covers:

- secret handling
- least-privilege DB setup
- credential rotation
- dependency audit guidance
- incident-response expectations

---

## Documentation suite

Validation and governance reports:

- `docs/ENGINEERING_VALIDATION.md`
- `docs/SECURITY_GOVERNANCE.md`
- `docs/ECONOMIC_IMPACT.md`
- `docs/ARCHITECTURE_ADR.md`
- `docs/validation-report-shadow-mode.md`

---

## Make targets

Useful commands:

```bash
make test-semantic-pgvector
make clean-semantic-pgvector
make bootstrap-policy-store
make validate-semantic-demo
make validate-shadow-mode
make validate-shadow-stack
make validate-system-slice
make test-in-container
```

---

## Current status

Metera’s current slice is no longer just a prototype proxy.
It now includes:

- exact cache
- semantic cache with pgvector
- shadow-mode analytics
- persistent policy state
- namespace isolation
- security hardening
- validation and documentation suite

Remaining work is primarily production refinement, operational packaging, and broader benchmark coverage rather than missing core architecture.

# Metera Architecture

## Objective

Build a local FastAPI middleware proxy that intercepts LLM calls to reduce cost through exact and semantic caching while preserving privacy and tenant isolation.

## Core design constraints

1. **Local DLP scrubbing before cache processing**
   - Prompts must be scrubbed locally before exact-hash generation.
   - Raw secrets and obvious PII must not become cache keys.

2. **Local embeddings for semantic cache**
   - Semantic matching must use a local embedding model.
   - Prompt meaning must not be sent to third-party embedding APIs for cache decisions.

3. **Namespace isolation**
   - Exact cache, semantic cache, metadata, and invalidation operations must be namespace aware.
   - Tenant_A must never read cache entries created by Tenant_B.

## Request pipeline

1. Receive client request
2. Resolve namespace / tenant context
3. Normalize request
4. DLP scrub normalized content locally
5. Compute exact cache key from scrubbed content + namespace + model + endpoint
6. Check exact cache
7. If miss, build local embedding for scrubbed semantic text
8. Query semantic candidates filtered by namespace + model family + policy
9. If eligible semantic hit, return cached response
10. Otherwise forward to upstream provider
11. Persist response metadata
12. Write exact cache entry and semantic index entry
13. Emit observability events and counters
14. If the live semantic threshold missed, run a non-blocking shadow-threshold check after the response is sent
15. Log shadow-hit analytics without storing embedding vectors

Important request-ordering rule:
- exact cache has priority over semantic cache
- repeated identical prompts should be expected to resolve as exact hits
- semantic validation should use paraphrases or exact-cache bypass/clearing when you specifically want to inspect semantic behavior

## Primary components

### API layer
- OpenAI-compatible endpoints
- health/stats/admin routes
- auth passthrough and operator auth

### Security layer
- DLP scrubbing
- secret detection
- namespace enforcement
- privacy-aware serialization policies
- default analyzer chain: Presidio when installed, regex fallback otherwise
- policy levels:
  - `technical`: redact secrets, tokens, connection strings, JWTs, and IPs
  - `strict`: redact technical secrets plus common personal identifiers like email and phone
  - `off`: disable scrubbing explicitly
- config-driven detector policy for email, phone, IP, and engineering secret classes
- explicit engineering secret detectors for GitHub tokens, Stripe keys, bearer tokens, AWS keys, JWTs, database URLs / connection strings, and private key blocks
- org-specific high-precision regex detectors can be registered through config JSON or YAML and surfaced in health/status output
- detector dry-run validation allows operators to test active rules against sample text before production rollout
- detector config is validated at startup; malformed YAML/JSON, invalid regex, and unsupported flags fail fast with source-aware errors

### Cache layer
- exact cache abstraction supports Redis-backed storage
- backend selected via config (`memory` or `redis`)
- in-memory KV store used as current dev fallback
- semantic cache currently uses local embeddings + repository abstraction with in-memory storage as the active backend
- semantic records now carry TTL/expiry and model-family partition metadata
- pgvector-backed persistence seam exists and is used for semantic retrieval
- conservative policy evaluation
- semantic reuse is gated by policy: disabled entirely when configured off, bypassed for streaming requests, and bypassed when temperature exceeds the configured threshold
- shadow-threshold analytics can evaluate live misses asynchronously after the response is sent, without affecting user-visible behavior
- shadow analytics store prompt text, request id, similarity score, and potential savings only; no embedding vectors are persisted in the analytics log

### Provider layer
- upstream request forwarding
- response normalization
- token/cost extraction

### Observability layer
- request counters
- hit/miss breakdowns
- latency
- estimated cost and savings

## Suggested repo structure

```text
metera/
  app/
    main.py
    api/
      routes_health.py
      routes_chat.py
      routes_stats.py
      routes_admin.py
    core/
      config.py
      logging.py
      lifecycle.py
    models/
      api.py
      domain.py
    providers/
      base.py
      openai_compatible.py
    cache/
      exact_cache.py
      semantic_cache.py
      normalization.py
      policy.py
    embeddings/
      base.py
      local_sentence_transformer.py
    observability/
      metrics.py
      costing.py
    security/
      dlp.py
      secrets.py
      namespace.py
    services/
      proxy_service.py
    storage/
      memory.py
  docs/
    architecture.md
    tasks.md
  tests/
  pyproject.toml
```

## Initial non-goals

- full frontend dashboard
- multi-provider support in v0
- tool-calling semantic reuse
- cross-region distributed cache invalidation

## Near-term implementation priorities

1. passthrough proxy correctness
2. local DLP before cache operations
3. exact cache
4. local embedding semantic cache
5. stats and admin control surface

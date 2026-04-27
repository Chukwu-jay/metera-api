# Metera Task Breakdown

## Milestone 1 — skeleton proxy
- [x] Create Python project with FastAPI entrypoint
- [x] Add OpenAI-compatible `POST /v1/chat/completions`
- [x] Add `GET /health`
- [x] Add settings/config module
- [x] Add upstream client abstraction
- [x] Add basic request logging
- [x] Add smoke test for passthrough flow

## Milestone 2 — exact cache + local DLP scrubbing
- [x] Implement request normalization
- [x] Add local DLP scrubbing module using local analyzers
- [x] Add secret/API-key detectors
- [x] Define scrubbed text representation for hashing
- [x] Add Redis-backed exact cache abstraction
- [x] Include namespace in exact cache keys
- [x] Add TTL policy support
- [x] Add tests proving raw secrets/PII are not used as keys

## Milestone 3 — semantic cache with local embeddings
- [x] Add local embedding interface
- [x] Implement sentence-transformers adapter
- [x] Define semantic cache candidate filters
- [x] Add pgvector-backed semantic search abstraction
- [x] Enforce namespace filter in semantic lookup
- [x] Add similarity threshold policy
- [x] Add tests for semantic hit/miss and namespace boundaries

## Milestone 4 — observability core
- [x] Add in-process counters for requests and cache outcomes
- [x] Add token/cost estimation service
- [x] Add `GET /stats/summary`
- [x] Add `GET /metrics`
- [x] Make logs and metrics scrub-aware

## Milestone 5 — streaming + robustness
- [x] Add streaming passthrough support
- [x] Decide cache-write behavior for streamed responses
- [x] Add timeout/retry policy
- [x] Normalize upstream errors
- [x] Add integration tests for stream and non-stream modes

## Milestone 6 — admin controls + enforced namespace isolation
- [x] Add policy endpoints
- [x] Add cache invalidation endpoint
- [x] Add namespace resolution contract
- [x] Enforce namespace isolation in read path
- [x] Enforce namespace isolation in write path
- [x] Enforce namespace isolation in admin operations
- [x] Add tests that Tenant_A cannot hit Tenant_B cache entries

## Milestone 7 — packaging
- [x] Add Dockerfile
- [x] Add local docker-compose for dependencies
- [x] Add README run instructions
- [x] Add environment example file
- [x] Add smoke test script

## Current reality

Metera now has a complete proxy-core path:
- scrub-first request handling
- exact cache + semantic cache
- SQL-backed pgvector retrieval
- namespace isolation
- admin-gated policy and invalidation controls
- observability for hits, misses, cost, savings, and backend posture
- streaming passthrough with explicit cache bypass behavior
- local packaging/run instructions and smoke test scaffolding

## Immediate next implementation sequence
1. Namespace-filtered semantic retrieval benchmarking
2. Structured observability for semantic hit quality
3. Semantic candidate expiry / pruning observability
4. Model-family-aware semantic partition tuning
5. Container/runtime polish for Milestone 7
   - deferred: optimize image size and dependency layering after real build validation
   - validate sentence-transformers / optional dependency behavior in container runtime

## Current implementation notes

- Exact cache is intentionally checked before semantic cache.
- Postgres-backed policy state now persists production bootstrap defaults so threshold changes are not lost across restarts.
- JSON decoding must be explicit on asyncpg read paths; this has already bitten both the semantic store and policy store once.
- Shadow mode is now the preferred path for tuning lower semantic thresholds without changing production responses.

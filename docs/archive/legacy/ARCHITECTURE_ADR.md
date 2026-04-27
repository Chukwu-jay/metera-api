# ARCHITECTURE_ADR

## Scope

This ADR records the key architecture decisions finalized in the current Metera slice.

## Decision 1: Shared Singleton Embedder

### Problem

The original request path constructed semantic embedder state too close to request handling, which introduced repeated model initialization cost and destroyed concurrency performance.

Observed impact:

- 100-request batch wall-clock time was approximately **174.16s** before the fix

This created a substantial **Compute Tax**:

- expensive model setup work was effectively leaking into request handling
- concurrency gains were muted by repeated initialization overhead
- the system could not plausibly scale into enterprise request volumes in that form

### Decision

Move to a **singleton embedder lifecycle**:

- initialize the sentence-transformer embedder once during app startup
- store it in app state
- reuse it across subsequent request handling

### Result

Observed benchmark progression after the change:

- **17.71s** for the shared-embedder benchmark
- **12.82s** in the final polished validation run

This reduced the compute tax enough to make semantic reuse operational under concurrent load.

## Decision 2: pgvector for Semantic Memory Indexing

### Problem

In-memory semantic storage is useful for development but insufficient for production-grade persistence, durability, and cross-request continuity.

### Decision

Use **Postgres + pgvector** for semantic memory indexing.

### Why pgvector

- semantic embeddings can be persisted durably
- similarity search runs inside the database
- indexed semantic memory survives process restarts
- integrates naturally with existing Postgres operational practices

### Result

Metera now persists semantic entries in `semantic_cache_entries`, enabling:

- namespace-scoped semantic reuse
- persisted similarity search
- stable benchmarking and validation across restarts

## Decision 3: Dual Threshold Policy (Live + Shadow)

### Problem

A single semantic threshold forces an unstable tradeoff between:

- correctness / technical safety
- cost reduction through more aggressive reuse

### Decision

Adopt a dual-threshold model:

- **Live threshold:** `0.90`
- **Shadow threshold:** `0.80`

### Result

- requests above `0.90` are eligible for live semantic reuse
- requests between `0.80` and `0.90` are logged as shadow opportunities only
- production responses remain conservative while lower-threshold economics are still measured

## Decision 4: Post-Response Shadow Analytics

### Problem

Evaluating lower-threshold opportunities inline would add latency and pollute the production path.

### Decision

Run shadow semantic checks asynchronously after the production response is sent.

### Result

- no added user-facing latency from shadow-mode analysis
- persisted shadow-hit analytics in Postgres
- measurable opportunity without production behavior change

## Architectural Outcome

These decisions collectively define Metera’s current architecture:

- **singleton embedder** to eliminate repeated model startup cost
- **pgvector-backed semantic memory** for durable similarity indexing
- **dual-threshold policy** for safe and measurable cost control
- **post-response shadow analytics** for low-risk threshold tuning

This architecture is now validated, measurable, and ready for further production hardening.

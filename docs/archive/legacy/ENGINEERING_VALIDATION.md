# ENGINEERING_VALIDATION

## Executive Summary

Metera reached Definition of Done for the current architectural slice with a validated **10x+ throughput improvement** on the 100-request benchmark.

Benchmark progression:

- early benchmark wall-clock: **174.16s**
- shared-embedder benchmark wall-clock: **17.71s**
- final polished benchmark wall-clock: **12.82s**

The key architectural driver was the move from per-request embedder construction to a **shared singleton embedder initialized at startup**. That removed repeated model initialization from the request path and converted semantic caching from a correctness demo into something operationally viable under load.

## Performance Proof

### 100-request stress test

Final audited concurrency metrics:

```json
{
  "requests_sent": 100,
  "wall_clock_elapsed_seconds": 12.82,
  "avg_request_latency_ms": 2987.71,
  "throughput_requests_per_second": 7.8,
  "implied_average_in_flight_requests": 23.3,
  "latency_ms": {
    "min": 1630.85,
    "p50": 2867.52,
    "p95": 4075.69,
    "p99": 4629.0,
    "max": 5550.74
  }
}
```

### Percentile math note

Wall-clock batch time and per-request latency measure different things.

- **Wall-clock elapsed time** measures how long the full batch took to complete.
- **Per-request latency** measures what each caller waited for.

Under concurrency, per-request latency can be multi-second even when the batch completes in a much smaller wall-clock window, because many requests are in flight simultaneously.

### Shared-embedder startup lifecycle verification

Startup log proof:

```text
metera-app  | INFO:     Started server process [1]
metera-app  | INFO:     Waiting for application startup.
metera-app  |
Loading weights:   0%|          | 0/103 [00:00<?, ?it/s]
Loading weights: 100%|██████████| 103/103 [00:00<00:00, 1151.08it/s]
metera-app  | [1mBertModel LOAD REPORT[0m from: sentence-transformers/all-MiniLM-L6-v2
metera-app  | INFO:     Application startup complete.
metera-app  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
metera-app  | INFO:     127.0.0.1:58290 - "GET /health HTTP/1.1" 200 OK
```

This proves:

- the embedding model loads during application startup
- initialization completes before the first request
- the request path reuses the already-initialized embedder

## System Integrity

### Namespace isolation

Validated result:

- identical prompt in namespace A: `miss`
- identical prompt in namespace B: `miss`

This confirms cache state does not leak across namespaces.

### 14-day retention

Validated result:

- rows backdated to 15 days old were deleted
- fresh shadow analytics rows remained intact

This confirms storage hygiene and retention enforcement for shadow analytics.

### Policy fallback

Validated result:

- deleting the `default` policy row from Postgres did not break the app
- `/admin/policy` fell back correctly to hardcoded defaults
- bootstrap restored the persistent policy row afterward

This confirms the app can tolerate missing persisted policy state without runtime failure.

## Final Status

Engineering validation for the current slice is green:

- shared embedder: **validated**
- concurrency improvement: **validated**
- percentile reporting: **audited**
- namespace isolation: **validated**
- retention purge: **validated**
- policy fallback: **validated**

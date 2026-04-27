from __future__ import annotations

from collections import Counter
from typing import Any

COUNTERS = Counter()
DISTRIBUTIONS: dict[str, dict[str, float]] = {}


def increment(name: str, value: int | float = 1) -> None:
    COUNTERS[name] += value


def observe(name: str, value: float) -> None:
    bucket = DISTRIBUTIONS.setdefault(name, {"count": 0.0, "sum": 0.0, "max": 0.0})
    bucket["count"] += 1
    bucket["sum"] += value
    bucket["max"] = max(bucket["max"], value)


def reset_metrics() -> None:
    COUNTERS.clear()
    DISTRIBUTIONS.clear()


def snapshot_metrics() -> dict[str, Any]:
    requests_total = COUNTERS.get("requests_total", 0)
    exact_hits = COUNTERS.get("cache_exact_hits", 0)
    semantic_hits = COUNTERS.get("cache_semantic_hits", 0)
    misses = COUNTERS.get("cache_misses", 0)
    hit_total = exact_hits + semantic_hits

    return {
        "requests": {
            "total": requests_total,
            "cache_outcomes": {
                "exact_hits": exact_hits,
                "semantic_hits": semantic_hits,
                "misses": misses,
                "hit_rate": (hit_total / requests_total) if requests_total else 0.0,
            },
        },
        "semantic": {
            "candidates_indexed": COUNTERS.get("semantic_candidates_indexed", 0),
            "bypasses": COUNTERS.get("semantic_bypasses", 0),
            "shadow_hits": COUNTERS.get("semantic_shadow_hits", 0),
            "shadow_logs_written": COUNTERS.get("semantic_shadow_logs_written", 0),
            "store_backend": {
                "pgvector": COUNTERS.get("semantic_store_backend_pgvector", 0),
                "memory": COUNTERS.get("semantic_store_backend_memory", 0),
                "fallbacks": COUNTERS.get("semantic_store_backend_fallbacks", 0),
            },
        },
        "scrubbing": {
            "scrubbed_requests": COUNTERS.get("scrubbed_requests", 0),
            "pii_entities_redacted": COUNTERS.get("scrubbed_pii_entities", 0),
            "secret_entities_redacted": COUNTERS.get("scrubbed_secret_entities", 0),
        },
        "cache_backends": {
            "redis": COUNTERS.get("cache_backend_redis", 0),
            "memory": COUNTERS.get("cache_backend_memory", 0),
            "fallbacks": COUNTERS.get("cache_backend_fallbacks", 0),
        },
        "admin": {
            "cache_invalidations": COUNTERS.get("admin_cache_invalidations", 0),
            "exact_cache_deleted": COUNTERS.get("admin_exact_cache_deleted", 0),
            "semantic_cache_deleted": COUNTERS.get("admin_semantic_cache_deleted", 0),
        },
        "tokens": {
            "prompt": COUNTERS.get("usage_prompt_tokens_total", 0),
            "completion": COUNTERS.get("usage_completion_tokens_total", 0),
            "total": COUNTERS.get("usage_total_tokens_total", 0),
        },
        "costs_usd": {
            "upstream_total": round(float(COUNTERS.get("estimated_upstream_cost_usd_total", 0.0)), 8),
            "savings_total": round(float(COUNTERS.get("estimated_savings_usd_total", 0.0)), 8),
        },
        "latency_ms": {
            "overall": _distribution_snapshot("request_latency_ms"),
            "upstream": _distribution_snapshot("request_latency_ms_upstream"),
            "exact_hit": _distribution_snapshot("request_latency_ms_exact_hit"),
            "semantic_hit": _distribution_snapshot("request_latency_ms_semantic_hit"),
        },
    }


def _distribution_snapshot(name: str) -> dict[str, float]:
    bucket = DISTRIBUTIONS.get(name, {"count": 0.0, "sum": 0.0, "max": 0.0})
    count = bucket["count"]
    total = bucket["sum"]
    return {
        "count": int(count),
        "avg": (total / count) if count else 0.0,
        "max": bucket["max"],
    }

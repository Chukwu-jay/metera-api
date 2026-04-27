from app.observability.metrics import increment, observe, reset_metrics, snapshot_metrics


def test_stats_summary_groups_observability_signals() -> None:
    reset_metrics()
    increment("requests_total", 4)
    increment("cache_exact_hits", 1)
    increment("cache_semantic_hits", 1)
    increment("cache_misses", 2)
    increment("semantic_candidates_indexed", 3)
    increment("semantic_bypasses", 1)
    increment("scrubbed_requests", 2)
    increment("scrubbed_pii_entities", 4)
    increment("scrubbed_secret_entities", 1)
    increment("usage_prompt_tokens_total", 120)
    increment("usage_completion_tokens_total", 80)
    increment("usage_total_tokens_total", 200)
    increment("estimated_upstream_cost_usd_total", 0.123456789)
    increment("estimated_savings_usd_total", 0.5)
    increment("cache_backend_memory", 1)
    increment("semantic_store_backend_pgvector", 1)
    increment("admin_cache_invalidations", 2)
    increment("admin_exact_cache_deleted", 5)
    increment("admin_semantic_cache_deleted", 3)
    observe("request_latency_ms", 10.0)
    observe("request_latency_ms", 30.0)
    observe("request_latency_ms_upstream", 30.0)

    snapshot = snapshot_metrics()

    assert snapshot["requests"]["total"] == 4
    assert snapshot["requests"]["cache_outcomes"]["hit_rate"] == 0.5
    assert snapshot["semantic"]["candidates_indexed"] == 3
    assert snapshot["scrubbing"]["pii_entities_redacted"] == 4
    assert snapshot["admin"]["cache_invalidations"] == 2
    assert snapshot["admin"]["exact_cache_deleted"] == 5
    assert snapshot["admin"]["semantic_cache_deleted"] == 3
    assert snapshot["tokens"]["total"] == 200
    assert snapshot["costs_usd"]["upstream_total"] == 0.12345679
    assert snapshot["costs_usd"]["savings_total"] == 0.5
    assert snapshot["cache_backends"]["memory"] == 1
    assert snapshot["semantic"]["store_backend"]["pgvector"] == 1
    assert snapshot["latency_ms"]["overall"]["count"] == 2
    assert snapshot["latency_ms"]["overall"]["avg"] == 20.0
    assert snapshot["latency_ms"]["upstream"]["max"] == 30.0

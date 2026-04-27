from __future__ import annotations

import json
import math
import subprocess
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8000"
ADMIN_KEY = "dev-admin-key"
PROMPT_GROUPS = [
    (
        "A homeowner in southern Ontario is dealing with a driveway snow problem that keeps repeating after every major storm. The municipal plow clears the street, but it leaves behind a dense berm across the mouth of the driveway, and the owner still has to clear compacted snow packed around two parked cars near the garage. They are not looking for a giant commercial machine or a tractor attachment. What they want is a compact autonomous robot that can handle the ugly last part of residential snow clearing: the ridge at the curb, the awkward edges along the driveway, and the heavy snow trapped around vehicles where shoveling is slow, cold, and physically draining. Explain the job to be done, the pain points, and why this problem matters so much to an ordinary homeowner.",
        "Describe this same customer problem in different wording and with a different framing. In a Canadian suburb, the street is plowed but the homeowner still faces the hardest cleanup afterward: a thick windrow at the end of the driveway, piles of pushed snow near the sidewalk, and frozen buildup surrounding parked vehicles that makes getting out in the morning frustrating and time consuming. The customer is imagining a self-driving residential snow robot, not a full-size loader, because the real need is precise and repeatable cleanup in tight household spaces. They want relief from repetitive winter labor, especially the part that happens after the main plowing is done. Summarize the underlying task, the functional requirements, and the emotional frustration behind the request.",
        "Rephrase the same scenario again while preserving the meaning. The user is a homeowner who does not mind that the road gets cleared by the city, but they hate the leftover mess that remains on private property: the packed ridge at the curb cut, the snow banks that block the driveway entrance, and the stubborn accumulation around parked cars that is difficult to reach with a shovel or a traditional snowblower. They are interested in an autonomous driveway robot because the problem is not just moving snow in general, it is handling the annoying final twenty percent of cleanup that is most inconsistent, most tiring, and most likely to be ignored until it becomes a bigger inconvenience. Explain the practical use case and why a purpose-built household robot could be compelling here.",
    ),
    (
        "A finance team wants an internal AI helper that can summarize vendor contracts, compare recurring software spend, and surface renewal risk before annual budgets are finalized. The team is not asking for a general chatbot; they want a narrow assistant that can read procurement context, identify cost drivers, and flag obligations that could surprise the business later. Explain the operational problem, the value of reducing manual review, and why finance leaders care about speed, consistency, and auditability here.",
        "Describe the same finance workflow in different words. A company needs an AI assistant for procurement and budgeting work: something that can read vendor agreements, highlight expensive terms, track renewal exposure, and help the team prepare budget decisions with fewer manual spreadsheet passes. The need is practical rather than experimental. Explain the job to be done and why reliable cost visibility matters in this setting.",
        "Reframe the same scenario while keeping the meaning. The customer wants an internal finance copilot that reviews contracts and recurring SaaS commitments so the organization can spot budget risk, renewal timing, and hidden spend drivers earlier. The core problem is repetitive review and inconsistent follow-through, not a lack of raw documents. Explain the use case and why this kind of assistant is appealing.",
    ),
    (
        "An operations lead at a mid-sized warehouse is trying to reduce the morning chaos around shift handoff. Important issues are written in scattered notes, supervisors repeat themselves across radio calls, and small exceptions become bigger delays because no one has a single summary of what changed overnight. The team wants an AI assistant that can consolidate the overnight notes, organize risks, and give incoming staff a concise, structured handoff. Explain the underlying operational pain and why consistent summaries matter.",
        "Describe the same warehouse handoff problem in different wording. Overnight supervisors leave fragmented notes, verbal updates get lost, and the incoming team spends too much time piecing together what happened before they can act. The organization wants a focused AI handoff assistant that turns messy shift information into a clean operational summary. Explain the job to be done and why this is valuable.",
        "Rephrase that warehouse scenario while preserving the meaning. The company is not looking for a broad chat tool; it wants a reliable way to collect overnight exceptions, delays, and risks into a structured shift-start briefing so incoming managers are aligned faster. Explain the use case and why operations teams would adopt it.",
    ),
    (
        "A support manager is overwhelmed by long customer complaint threads that include billing disputes, shipping issues, and multiple tone escalations. Agents are spending too much time reading every message from the beginning before they can decide what happened and how urgent the case is. The manager wants an AI assistant that can summarize the thread, detect the likely root issue, and surface urgency signals without inventing facts. Explain the problem and why this matters for support teams.",
        "Describe the same support scenario in a different way. Customer service agents face giant email chains and ticket histories where billing, logistics, and frustration are all mixed together. The business wants an AI summarization assistant that can compress the case history, identify the probable issue, and help agents respond faster with less repetitive reading. Explain the job to be done and why support leadership would care.",
        "Rephrase the same case-handling problem while keeping the meaning. The goal is a customer support copilot that turns long complaint conversations into a clear case summary with urgency context and likely issue category, so agents can spend less time reconstructing history and more time resolving the problem. Explain the use case and its operational value.",
    ),
]


def main() -> int:
    _set_policy(semantic_threshold=0.9, semantic_shadow_threshold=0.82)

    concurrency_result = _run_concurrency_validation()
    fallback_result = _run_default_policy_fallback_validation()
    drift_result = _run_drift_validation()
    retention_result = _run_retention_validation()
    namespace_result = _run_namespace_validation()
    metrics_snapshot = _get_json(f"{BASE_URL}/stats/summary")
    db_counts = _global_db_counts()
    financial_impact = _financial_impact(db_counts=db_counts, metrics_snapshot=metrics_snapshot)

    summary = {
        "concurrency": concurrency_result,
        "default_policy_fallback": fallback_result,
        "drift": drift_result,
        "retention": retention_result,
        "namespace_isolation": namespace_result,
        "in_memory_counters": metrics_snapshot,
        "authoritative_db_counts": db_counts,
        "financial_impact": financial_impact,
    }
    print(json.dumps(summary, indent=2))
    return 0


def _run_concurrency_validation() -> dict:
    namespace = f"load-test-{uuid.uuid4().hex[:8]}"
    prompts = []
    for group_index, group in enumerate(PROMPT_GROUPS):
        for i in range(25):
            base = group[i % len(group)]
            prompts.append((namespace, f"{base} Unique marker batch={group_index} item={i}."))

    started = time.perf_counter()
    results = []
    durations_ms = []
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(_timed_chat, ns, prompt) for ns, prompt in prompts]
        for future in as_completed(futures):
            result = future.result()
            results.append(result["response"])
            durations_ms.append(result["duration_ms"])
    elapsed = time.perf_counter() - started

    stats = _get_json(f"{BASE_URL}/stats/summary")
    shadow_rows = _count_shadow_rows(namespace)
    indexed_rows = _count_semantic_rows(namespace)

    avg_latency_ms = round(sum(durations_ms) / len(durations_ms), 2) if durations_ms else 0.0
    throughput = round(len(prompts) / elapsed, 2) if elapsed else 0.0
    concurrency_factor = round((avg_latency_ms / 1000.0) / elapsed * len(prompts), 2) if elapsed and avg_latency_ms else 0.0

    return {
        "namespace": namespace,
        "requests_sent": len(prompts),
        "wall_clock_elapsed_seconds": round(elapsed, 2),
        "avg_request_latency_ms": avg_latency_ms,
        "throughput_requests_per_second": throughput,
        "implied_average_in_flight_requests": concurrency_factor,
        "latency_ms": _percentiles(durations_ms),
        "latency_math_note": "Per-request latency can exceed wall-clock/requests under concurrency; wall-clock measures batch completion, while latency measures each request's own response time.",
        "misses": sum(1 for item in results if item["metera"]["cache"] == "miss"),
        "semantic_hits": sum(1 for item in results if item["metera"]["cache"] == "semantic_hit"),
        "exact_hits": sum(1 for item in results if item["metera"]["cache"] == "exact_hit"),
        "semantic_rows": indexed_rows,
        "shadow_rows": shadow_rows,
        "shadow_logs_written_metric": stats["semantic"]["shadow_logs_written"],
    }


def _run_default_policy_fallback_validation() -> dict:
    sql_delete = "DELETE FROM admin_policy_overrides WHERE policy_name = 'default';"
    _psql(sql_delete)
    policy = _get_json_with_headers(f"{BASE_URL}/admin/policy", {"x-metera-admin-key": ADMIN_KEY})
    _bootstrap_policy_store()
    return {
        "semantic_threshold": policy["semantic_threshold"],
        "semantic_shadow_threshold": policy["semantic_shadow_threshold"],
        "semantic_enabled": policy["semantic_enabled"],
    }


def _run_drift_validation() -> dict:
    namespace = f"drift-test-{uuid.uuid4().hex[:8]}"
    prompts = [
        PROMPT_GROUPS[0][0],
        PROMPT_GROUPS[0][0] + " Please keep the wording nearly identical.",
        PROMPT_GROUPS[0][1],
        "A small team wants a short explanation of how to organize a weekend neighborhood cleanup with volunteers, garbage bags, and a meetup point in the local park.",
    ]
    first = _chat(namespace, prompts[0])
    second = _chat(namespace, prompts[1])
    third = _chat(namespace, prompts[2])
    fourth = _chat(namespace, prompts[3])
    return {
        "namespace": namespace,
        "live_hit_candidate": {"cache": second["metera"]["cache"], "similarity": second["metera"].get("semantic_similarity")},
        "shadow_candidate": _latest_shadow_row(namespace),
        "total_miss_candidate": {"cache": fourth["metera"]["cache"], "request_id": fourth["metera"].get("request_id")},
        "baseline_request_id": first["metera"].get("request_id"),
        "mid_candidate": {"cache": third["metera"]["cache"], "request_id": third["metera"].get("request_id")},
    }


def _run_retention_validation() -> dict:
    namespace = f"retention-test-{uuid.uuid4().hex[:8]}"
    old_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    new_id = str(uuid.uuid4())
    for request_id in old_ids:
        _psql(
            "INSERT INTO semantic_shadow_analytics (request_id, namespace, model, prompt_text, similarity_score, calculated_savings_usd, live_threshold, shadow_threshold, created_at) "
            f"VALUES ('{request_id}', '{namespace}', 'gpt-4o-mini', 'old', 0.83, 0.00000375, 0.9, 0.82, NOW() - INTERVAL '15 days');"
        )
    _psql(
        "INSERT INTO semantic_shadow_analytics (request_id, namespace, model, prompt_text, similarity_score, calculated_savings_usd, live_threshold, shadow_threshold, created_at) "
        f"VALUES ('{new_id}', '{namespace}', 'gpt-4o-mini', 'new', 0.83, 0.00000375, 0.9, 0.82, NOW());"
    )
    _psql("DELETE FROM semantic_shadow_analytics WHERE created_at <= NOW() - INTERVAL '14 days';")
    remaining = _psql("SELECT request_id FROM semantic_shadow_analytics WHERE namespace = '%s' ORDER BY created_at;" % namespace)
    return {"namespace": namespace, "remaining_rows": remaining.strip().splitlines() if remaining.strip() else []}


def _run_namespace_validation() -> dict:
    namespace_a = f"ns-a-{uuid.uuid4().hex[:6]}"
    namespace_b = f"ns-b-{uuid.uuid4().hex[:6]}"
    prompt = PROMPT_GROUPS[1][0]
    first = _chat(namespace_a, prompt)
    second = _chat(namespace_b, prompt)
    return {
        "namespace_a_cache": first["metera"]["cache"],
        "namespace_b_cache": second["metera"]["cache"],
        "namespace_a_request_id": first["metera"]["request_id"],
        "namespace_b_request_id": second["metera"]["request_id"],
    }


def _chat(namespace: str, prompt: str) -> dict:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.0,
    }
    return _post_json(f"{BASE_URL}/v1/chat/completions", payload, headers={"x-metera-namespace": namespace})


def _timed_chat(namespace: str, prompt: str) -> dict:
    started = time.perf_counter()
    response = _chat(namespace, prompt)
    duration_ms = (time.perf_counter() - started) * 1000.0
    return {"response": response, "duration_ms": duration_ms}


def _set_policy(*, semantic_threshold: float, semantic_shadow_threshold: float) -> None:
    _post_json(
        f"{BASE_URL}/admin/policy",
        {"semantic_threshold": semantic_threshold, "semantic_shadow_threshold": semantic_shadow_threshold},
        headers={"x-metera-admin-key": ADMIN_KEY},
    )


def _bootstrap_policy_store() -> None:
    subprocess.run(
        ["docker", "exec", "metera-app", "sh", "-lc", "cd /app && PYTHONPATH=. python scripts/bootstrap_policy_store.py"],
        check=True,
        capture_output=True,
        text=True,
    )


def _count_semantic_rows(namespace: str) -> int:
    out = _psql(f"SELECT count(*) FROM semantic_cache_entries WHERE namespace = '{namespace}';")
    return int(out.strip().splitlines()[-1]) if out.strip() else 0


def _count_shadow_rows(namespace: str) -> int:
    out = _psql(f"SELECT count(*) FROM semantic_shadow_analytics WHERE namespace = '{namespace}';")
    return int(out.strip().splitlines()[-1]) if out.strip() else 0


def _latest_shadow_row(namespace: str) -> dict | None:
    out = _psql(
        "SELECT request_id, similarity_score, live_threshold, shadow_threshold FROM semantic_shadow_analytics "
        f"WHERE namespace = '{namespace}' ORDER BY created_at DESC LIMIT 1;",
        raw=True,
    )
    line = out.strip()
    if not line:
        return None
    request_id, similarity, live_threshold, shadow_threshold = line.split("|")
    return {
        "request_id": request_id,
        "similarity": float(similarity),
        "live_threshold": float(live_threshold),
        "shadow_threshold": float(shadow_threshold),
    }


def _psql(sql: str, raw: bool = False) -> str:
    args = ["docker", "exec", "metera-pgvector", "psql", "-U", "postgres", "-d", "metera"]
    if raw:
        args.extend(["-At", "-F", "|"])
    else:
        args.extend(["-At"])
    args.extend(["-c", sql])
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {"min": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    ordered = sorted(values)
    return {
        "min": round(ordered[0], 2),
        "p50": round(_percentile(ordered, 0.50), 2),
        "p95": round(_percentile(ordered, 0.95), 2),
        "p99": round(_percentile(ordered, 0.99), 2),
        "max": round(ordered[-1], 2),
    }



def _percentile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    rank = fraction * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _global_db_counts() -> dict:
    semantic_rows = int(_psql("SELECT count(*) FROM semantic_cache_entries;").strip().splitlines()[-1])
    shadow_rows = int(_psql("SELECT count(*) FROM semantic_shadow_analytics;").strip().splitlines()[-1])
    shadow_savings = float(_psql("SELECT COALESCE(sum(calculated_savings_usd), 0) FROM semantic_shadow_analytics;").strip().splitlines()[-1])
    return {
        "semantic_cache_rows_total": semantic_rows,
        "semantic_shadow_rows_total": shadow_rows,
        "potential_shadow_savings_usd_total": round(shadow_savings, 8),
    }



def _financial_impact(*, db_counts: dict, metrics_snapshot: dict) -> dict:
    return {
        "calculated_savings_usd_total": metrics_snapshot["costs_usd"]["savings_total"],
        "upstream_cost_usd_total": metrics_snapshot["costs_usd"]["upstream_total"],
        "potential_shadow_savings_usd_total": db_counts["potential_shadow_savings_usd_total"],
    }



def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json_with_headers(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import concurrent.futures
import json
import os
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = os.getenv("METERA_ADMIN_API_KEY", "dev-admin-key")
RUN_TAG = os.getenv("METERA_PROOF_RUN_TAG") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
TENANT_COUNT = int(os.getenv("METERA_MT_TENANT_COUNT", "4"))
MAX_WORKERS = int(os.getenv("METERA_MT_MAX_WORKERS", "16"))
MODEL = os.getenv("METERA_PROOF_MODEL", "gpt-4o-mini")
MESSAGE_BLOCK_REPEATS = int(os.getenv("METERA_PROOF_MESSAGE_BLOCK_REPEATS", "1200"))
OUTPUT_PATH = os.getenv("METERA_PROOF_OUTPUT_PATH")
PERIOD_START = os.getenv("METERA_PROOF_PERIOD_START", "2026-04-01T00:00:00+00:00")
PERIOD_END = os.getenv("METERA_PROOF_PERIOD_END", "2026-05-01T00:00:00+00:00")
REQUIRE_SAME_TENANT_EXACT_HIT = os.getenv("METERA_MT_REQUIRE_EXACT_HIT", "true").strip().lower() == "true"
REQUIRE_SHARED_SEED_MISS = os.getenv("METERA_MT_REQUIRE_SHARED_SEED_MISS", "true").strip().lower() == "true"
STRICT_FIRST_ROUND_ONLY = os.getenv("METERA_MT_STRICT_FIRST_ROUND_ONLY", "true").strip().lower() == "true"
MAX_MESSAGE_CHARS = int(os.getenv("METERA_MT_MAX_MESSAGE_CHARS", "18000"))
SOAK_ROUNDS = int(os.getenv("METERA_MT_SOAK_ROUNDS", "3"))
SHARED_NAMESPACE = os.getenv("METERA_MT_SHARED_NAMESPACE", f"mt-shared-{RUN_TAG}")


def main() -> int:
    ready = _get_json(f"{BASE_URL}/ready")
    tenants = [_bootstrap_tenant(i) for i in range(TENANT_COUNT)]

    phase_results: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    for round_index in range(1, SOAK_ROUNDS + 1):
        round_tag = f"r{round_index}"
        shared_seed_payload = _chat_payload(
            system_text="Reply with exactly MT_SHARED_OK",
            user_text=_bounded_text(
                f"MT_SHARED_SEED {RUN_TAG} {round_tag} ",
                "SHARED_BLOCK ",
                MESSAGE_BLOCK_REPEATS,
            ),
        )
        shared_seed_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:shared_cross_tenant_seed",
            tenants=tenants,
            payload_factory=lambda _tenant, payload=shared_seed_payload: payload,
        )
        phase_results.extend(shared_seed_results)

        if REQUIRE_SHARED_SEED_MISS and (not STRICT_FIRST_ROUND_ONLY or round_index == 1):
            for row in shared_seed_results:
                if row.get("ok") and row.get("cache") != "miss":
                    anomalies.append(
                        {
                            "type": "cross_tenant_shared_seed_not_miss",
                            "tenant_id": row["tenant_id"],
                            "workspace_id": row["workspace_id"],
                            "cache": row.get("cache"),
                            "phase": row["phase"],
                        }
                    )

        same_tenant_repeat_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:same_tenant_exact_repeat",
            tenants=tenants,
            payload_factory=lambda _tenant, payload=shared_seed_payload: payload,
        )
        phase_results.extend(same_tenant_repeat_results)

        if REQUIRE_SAME_TENANT_EXACT_HIT and (not STRICT_FIRST_ROUND_ONLY or round_index == 1):
            for row in same_tenant_repeat_results:
                if row.get("ok") and row.get("cache") != "exact_hit":
                    anomalies.append(
                        {
                            "type": "same_tenant_repeat_not_exact_hit",
                            "tenant_id": row["tenant_id"],
                            "workspace_id": row["workspace_id"],
                            "cache": row.get("cache"),
                            "phase": row["phase"],
                        }
                    )

        shared_namespace_collision_seed_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:shared_namespace_collision_seed",
            tenants=tenants,
            payload_factory=lambda tenant, rt=round_tag: _chat_payload(
                system_text="Reply with exactly MT_COLLISION_OK",
                user_text=_bounded_text(
                    f"MT_COLLISION_SEED {RUN_TAG} {rt} {tenant['tenant_id']} ",
                    "COLLISION_BLOCK ",
                    MESSAGE_BLOCK_REPEATS,
                ),
            ),
            namespace_factory=lambda _tenant: SHARED_NAMESPACE,
        )
        phase_results.extend(shared_namespace_collision_seed_results)
        if not STRICT_FIRST_ROUND_ONLY or round_index == 1:
            for row in shared_namespace_collision_seed_results:
                if row.get("ok") and row.get("cache") != "miss":
                    anomalies.append(
                        {
                            "type": "shared_namespace_cross_tenant_seed_not_miss",
                            "tenant_id": row["tenant_id"],
                            "workspace_id": row["workspace_id"],
                            "cache": row.get("cache"),
                            "phase": row["phase"],
                        }
                    )

        shared_namespace_collision_repeat_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:shared_namespace_collision_repeat",
            tenants=tenants,
            payload_factory=lambda tenant, rt=round_tag: _chat_payload(
                system_text="Reply with exactly MT_COLLISION_OK",
                user_text=_bounded_text(
                    f"MT_COLLISION_SEED {RUN_TAG} {rt} {tenant['tenant_id']} ",
                    "COLLISION_BLOCK ",
                    MESSAGE_BLOCK_REPEATS,
                ),
            ),
            namespace_factory=lambda _tenant: SHARED_NAMESPACE,
        )
        phase_results.extend(shared_namespace_collision_repeat_results)
        if REQUIRE_SAME_TENANT_EXACT_HIT and (not STRICT_FIRST_ROUND_ONLY or round_index == 1):
            for row in shared_namespace_collision_repeat_results:
                if row.get("ok") and row.get("cache") != "exact_hit":
                    anomalies.append(
                        {
                            "type": "shared_namespace_same_tenant_repeat_not_exact_hit",
                            "tenant_id": row["tenant_id"],
                            "workspace_id": row["workspace_id"],
                            "cache": row.get("cache"),
                            "phase": row["phase"],
                        }
                    )

        tenant_unique_seed_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:tenant_unique_seed",
            tenants=tenants,
            payload_factory=lambda tenant, rt=round_tag: _chat_payload(
                system_text="Reply with exactly MT_UNIQUE_OK",
                user_text=_bounded_text(
                    f"MT_UNIQUE_SEED {RUN_TAG} {rt} {tenant['tenant_id']} ",
                    "TENANT_UNIQUE_BLOCK ",
                    MESSAGE_BLOCK_REPEATS,
                ),
            ),
        )
        phase_results.extend(tenant_unique_seed_results)

        tenant_semantic_variant_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:tenant_semantic_variant",
            tenants=tenants,
            payload_factory=lambda tenant, rt=round_tag: _chat_payload(
                system_text="Reply with exactly MT_UNIQUE_OK",
                user_text=_bounded_text(
                    (
                        f"Please respond exactly with MT_UNIQUE_OK for tenant {tenant['tenant_id']} in run {RUN_TAG} {rt}. "
                        f"This is a semantic restatement of the tenant-unique seed request. "
                    ),
                    "TENANT_UNIQUE_VARIANT ",
                    max(80, MESSAGE_BLOCK_REPEATS // 8),
                ),
            ),
        )
        phase_results.extend(tenant_semantic_variant_results)

        tenant_isolation_probe_results = _run_phase_concurrently(
            phase_name=f"{round_tag}:tenant_isolation_probe",
            tenants=tenants,
            payload_factory=lambda tenant, rt=round_tag: _chat_payload(
                system_text="Reply with exactly MT_ISOLATION_OK",
                user_text=_bounded_text(
                    f"MT_ISOLATION_PROBE {RUN_TAG} {rt} tenant={tenant['tenant_id']} workspace={tenant['workspace']['id']} ",
                    "ISOLATION_BLOCK ",
                    MESSAGE_BLOCK_REPEATS,
                ),
            ),
        )
        phase_results.extend(tenant_isolation_probe_results)

    for row in phase_results:
        anomalies.extend(_identity_anomalies(row))

    per_tenant = []
    request_rows_by_tenant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in phase_results:
        request_rows_by_tenant[row["tenant_id"]].append(row)

    for tenant in tenants:
        tenant_id = tenant["tenant_id"]
        billing_period_id = tenant["billing_period"]["id"]
        subscription_id = tenant["subscription"]["id"]
        materialized = _post_json(
            f"{BASE_URL}/admin/control/billing/materialize/ledger",
            {
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "billing_period_id": billing_period_id,
                "rollup_date": None,
                "limit": 5000,
            },
            headers=_admin_headers(),
        )
        summarized = _post_json(
            f"{BASE_URL}/admin/control/billing/periods/{billing_period_id}/summarize",
            {},
            headers=_admin_headers(),
        )
        report = _get_json(
            f"{BASE_URL}/admin/control/billing/periods/{billing_period_id}/report?format=json",
            headers=_admin_headers(),
        )
        tenant_rows = request_rows_by_tenant[tenant_id]
        cache_counts = dict(Counter((row.get("cache") or "null") for row in tenant_rows if row.get("ok")))
        expected_requests = len(tenant_rows)
        actual_requests = int((summarized or {}).get("request_count", 0) or 0)
        if actual_requests < expected_requests:
            anomalies.append(
                {
                    "type": "request_count_too_low",
                    "tenant_id": tenant_id,
                    "workspace_id": tenant["workspace"]["id"],
                    "expected_min": expected_requests,
                    "actual": actual_requests,
                }
            )
        per_tenant.append(
            {
                "tenant_id": tenant_id,
                "workspace_id": tenant["workspace"]["id"],
                "subscription_id": subscription_id,
                "billing_period_id": billing_period_id,
                "expected_request_count": expected_requests,
                "observed_ok_request_count": sum(1 for row in tenant_rows if row.get("ok")),
                "cache_counts": cache_counts,
                "materialized": materialized,
                "summarized": summarized,
                "report": report,
            }
        )

    phase_summary = _build_phase_summary(phase_results)
    payload = {
        "proof_run": {
            "run_tag": RUN_TAG,
            "base_url": BASE_URL,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "ready": ready,
        },
        "tenant_count": TENANT_COUNT,
        "soak_rounds": SOAK_ROUNDS,
        "phase_order": [
            "shared_cross_tenant_seed",
            "same_tenant_exact_repeat",
            "shared_namespace_collision_seed",
            "shared_namespace_collision_repeat",
            "tenant_unique_seed",
            "tenant_semantic_variant",
            "tenant_isolation_probe",
        ],
        "phase_summary": phase_summary,
        "responses": phase_results,
        "per_tenant": per_tenant,
        "anomalies": anomalies,
        "passed": len(anomalies) == 0,
    }
    rendered = json.dumps(payload, indent=2)
    print(rendered)
    if OUTPUT_PATH:
        out = Path(OUTPUT_PATH)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not anomalies else 1


def _build_phase_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["phase"]].append(row)
    summary: dict[str, Any] = {}
    for phase, phase_rows in grouped.items():
        ok_rows = [row for row in phase_rows if row.get("ok")]
        summary[phase] = {
            "request_count": len(phase_rows),
            "ok_count": len(ok_rows),
            "error_count": len(phase_rows) - len(ok_rows),
            "cache_counts": dict(Counter((row.get("cache") or "null") for row in ok_rows)),
            "distinct_response_tenant_ids": sorted({row.get("metera_tenant_id") for row in ok_rows if row.get("metera_tenant_id")}),
        }
    return summary


def _identity_anomalies(row: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    if not row.get("ok"):
        anomalies.append(
            {
                "type": "request_failed",
                "tenant_id": row["tenant_id"],
                "workspace_id": row["workspace_id"],
                "phase": row["phase"],
                "status_code": row.get("status_code"),
                "error": row.get("error"),
                "body": row.get("body"),
            }
        )
        return anomalies
    if row.get("tenant_id") != row.get("metera_tenant_id"):
        anomalies.append(
            {
                "type": "tenant_id_mismatch",
                "tenant_id": row["tenant_id"],
                "workspace_id": row["workspace_id"],
                "phase": row["phase"],
                "metera_tenant_id": row.get("metera_tenant_id"),
            }
        )
    if row.get("workspace_id") != row.get("metera_workspace_id"):
        anomalies.append(
            {
                "type": "workspace_id_mismatch",
                "tenant_id": row["tenant_id"],
                "workspace_id": row["workspace_id"],
                "phase": row["phase"],
                "metera_workspace_id": row.get("metera_workspace_id"),
            }
        )
    return anomalies


def _run_phase_concurrently(phase_name: str, tenants: list[dict[str, Any]], payload_factory, namespace_factory=None) -> list[dict[str, Any]]:
    namespace_factory = namespace_factory or (lambda tenant: f"{tenant['tenant_id']}-{tenant['workspace']['slug']}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tenants) or 1)) as ex:
        futures = [
            ex.submit(_tenant_request, tenant, phase_name, payload_factory(tenant), namespace_factory(tenant))
            for tenant in tenants
        ]
        return [future.result() for future in futures]


def _bootstrap_tenant(index: int) -> dict[str, Any]:
    slug = f"h3-mt-{RUN_TAG}-{index}"
    ws_slug = f"h3-mt-ws-{RUN_TAG}-{index}"
    identity = _post_json(
        f"{BASE_URL}/admin/control/bootstrap/tenant-environment",
        {
            "tenant": {"slug": slug, "name": f"H3 MT {index}", "metadata": {"run_tag": RUN_TAG}},
            "workspace": {"slug": ws_slug, "name": f"H3 MT WS {index}", "metadata": {"run_tag": RUN_TAG}},
            "api_key": {
                "display_name": f"H3 MT Key {index}",
                "tenant_role": "tenant_admin",
                "tenant_capabilities": ["billing:read", "billing:scope:read"],
                "metadata": {"run_tag": RUN_TAG},
            },
        },
        headers=_admin_headers(),
    )
    plan = _post_json(
        f"{BASE_URL}/admin/control/billing/plans",
        {
            "code": f"h3_mt_plan_{RUN_TAG}_{index}",
            "name": f"H3 MT Plan {index}",
            "monthly_base_price_usd": 50.0,
            "soft_cap_threshold_ratio": 0.8,
            "hard_cap_enabled": False,
            "metadata": {"scenario": "H3_MT", "run_tag": RUN_TAG},
        },
        headers=_admin_headers(),
    )
    subscription = _post_json(
        f"{BASE_URL}/admin/control/billing/subscriptions",
        {
            "tenant_id": identity["tenant"]["id"],
            "plan_id": plan["id"],
            "status": "trialing",
            "current_period_start": PERIOD_START,
            "current_period_end": PERIOD_END,
            "trial_ends_at": None,
        },
        headers=_admin_headers(),
    )
    billing_period = _post_json(
        f"{BASE_URL}/admin/control/billing/periods",
        {
            "tenant_id": identity["tenant"]["id"],
            "subscription_id": subscription["id"],
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
        },
        headers=_admin_headers(),
    )
    return {
        "tenant_id": identity["tenant"]["id"],
        "workspace": identity["workspace"],
        "plaintext_api_key": identity["api_key"]["plaintext_api_key"],
        "subscription": subscription,
        "billing_period": billing_period,
    }


def _tenant_request(tenant: dict[str, Any], phase_name: str, payload: dict[str, Any], namespace: str) -> dict[str, Any]:
    body, status_code, error = _post_json_with_status(
        f"{BASE_URL}/v1/chat/completions",
        payload,
        headers={
            "authorization": f"Bearer {tenant['plaintext_api_key']}",
            "x-metera-namespace": namespace,
            "content-type": "application/json",
        },
    )
    metera = (body or {}).get("metera") or {}
    return {
        "phase": phase_name,
        "tenant_id": tenant["tenant_id"],
        "workspace_id": tenant["workspace"]["id"],
        "metera_tenant_id": metera.get("tenant_id"),
        "metera_workspace_id": metera.get("workspace_id"),
        "cache": metera.get("cache"),
        "estimated_cost_usd": float(metera.get("estimated_cost_usd", 0.0) or 0.0),
        "estimated_savings_usd": float(metera.get("estimated_savings_usd", 0.0) or 0.0),
        "request_id": metera.get("request_id"),
        "status_code": status_code,
        "ok": error is None and 200 <= status_code < 300,
        "error": error,
        "body": body if error else None,
    }


def _chat_payload(system_text: str, user_text: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0,
    }


def _bounded_text(prefix: str, repeated_token: str, requested_repeats: int) -> str:
    text = prefix + (repeated_token * requested_repeats)
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    budget = max(1, MAX_MESSAGE_CHARS - len(prefix))
    token_len = max(1, len(repeated_token))
    allowed_repeats = max(1, budget // token_len)
    return prefix + (repeated_token * allowed_repeats)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body, status_code, error = _post_json_with_status(url, payload, headers=headers)
    if error is not None:
        raise RuntimeError(f"POST {url} failed with status {status_code}: {error} body={body}")
    return body or {}


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _post_json_with_status(url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[dict[str, Any] | None, int, str | None]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body else {}), int(response.status), None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return parsed, int(exc.code), f"http_error:{exc.code}"
    except urllib.error.URLError as exc:
        return {"reason": str(exc.reason)}, 0, f"url_error:{exc.reason}"


def _admin_headers() -> dict[str, str]:
    return {"x-metera-admin-key": ADMIN_KEY, "content-type": "application/json"}


if __name__ == "__main__":
    raise SystemExit(main())

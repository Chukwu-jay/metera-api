from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = os.getenv("METERA_ADMIN_API_KEY", "dev-admin-key")
RUN_TAG = os.getenv("METERA_PROOF_RUN_TAG") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
TENANT_SLUG = os.getenv("METERA_PROOF_TENANT_SLUG", f"tenant-pilot-alpha-{RUN_TAG}")
WORKSPACE_SLUG = os.getenv("METERA_PROOF_WORKSPACE_SLUG", f"workspace-pilot-alpha-{RUN_TAG}")
TENANT_NAME = os.getenv("METERA_PROOF_TENANT_NAME", TENANT_SLUG.replace("-", " ").title())
WORKSPACE_NAME = os.getenv("METERA_PROOF_WORKSPACE_NAME", WORKSPACE_SLUG.replace("-", " ").title())
PLAN_CODE = os.getenv("METERA_PROOF_PLAN_CODE", f"pilot_alpha_proof_{RUN_TAG}")
NAMESPACE = os.getenv("METERA_PROOF_NAMESPACE", f"{TENANT_SLUG}-{WORKSPACE_SLUG}")
POLICY_STORE_DSN = os.getenv("METERA_POLICY_STORE_DSN") or os.getenv("METERA_SEMANTIC_STORE_DSN")
OUTPUT_PATH = os.getenv("METERA_PROOF_OUTPUT_PATH")
THRESHOLD_REQUEST_COUNT = int(os.getenv("METERA_PROOF_REQUEST_COUNT", "1100"))
THRESHOLD_REALIZED_SAVINGS_USD = float(os.getenv("METERA_PROOF_REALIZED_SAVINGS_PER_REQUEST_USD", "0.05"))
THRESHOLD_UPSTREAM_COST_USD = float(os.getenv("METERA_PROOF_UPSTREAM_COST_PER_REQUEST_USD", "0.06"))


def main() -> int:
    ready = _wait_for_ready()
    period_start = datetime.now(UTC) - timedelta(hours=8)
    period_end = datetime.now(UTC) + timedelta(hours=1)

    identity = _bootstrap_identity()
    _reset_proof_state(
        tenant_id=identity["tenant_id"],
        workspace_id=identity["workspace_id"],
        api_key_id=identity["api_key_id"],
        plan_code=PLAN_CODE,
        period_start=period_start,
        period_end=period_end,
    )
    seeded = _seed_threshold_scenario(
        tenant_id=identity["tenant_id"],
        workspace_id=identity["workspace_id"],
        api_key_id=identity["api_key_id"],
        period_start=period_start,
    )
    plan, subscription, billing_period = _ensure_billing_setup(
        tenant_id=identity["tenant_id"],
        period_start=period_start,
        period_end=period_end,
    )

    materialized = _post_json(
        f"{BASE_URL}/admin/control/billing/materialize/ledger",
        {
            "tenant_id": identity["tenant_id"],
            "subscription_id": subscription["id"],
            "billing_period_id": billing_period["id"],
            "rollup_date": None,
            "limit": 2000,
        },
        headers=_admin_headers(),
    )
    summarized = _post_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/summarize",
        {},
        headers=_admin_headers(),
    )
    reconciliation = _get_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/reconcile",
        headers=_admin_headers(),
    )
    closeout_preview = _get_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/closeout-preview",
        headers=_admin_headers(),
    )
    report = _get_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/report?format=json",
        headers=_admin_headers(),
    )
    invoice = _post_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/invoice-stub?format=json",
        {},
        headers=_admin_headers(),
    )
    tenant_scope = _get_json(
        f"{BASE_URL}/control/tenant/billing/scope",
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    tenant_overview_closing = _get_json(
        f"{BASE_URL}/control/tenant/billing/overview",
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    commercial_events_before_close = _get_json(
        f"{BASE_URL}/admin/control/billing/commercial-events?tenant_id={urllib.parse.quote(identity['tenant_id'])}&limit=20",
        headers=_admin_headers(),
    )
    enforcement_probe_closing = _post_json_allow_error(
        f"{BASE_URL}/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Enforcement probe during closing state."}],
        },
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    closed = _post_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/close",
        {},
        headers=_admin_headers(),
    )
    commercial_events_after_close = _get_json(
        f"{BASE_URL}/admin/control/billing/commercial-events?tenant_id={urllib.parse.quote(identity['tenant_id'])}&limit=20",
        headers=_admin_headers(),
    )
    enforcement_probe_closed = _post_json_allow_error(
        f"{BASE_URL}/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Enforcement probe after period close."}],
        },
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    tenant_overview_closed = _get_json(
        f"{BASE_URL}/control/tenant/billing/overview",
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    ledger_truth = _ledger_truth(
        tenant_id=identity["tenant_id"],
        period_start=period_start,
        period_end=period_end,
    )

    bundle = {
        "proof_run": {
            "run_tag": RUN_TAG,
            "base_url": BASE_URL,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "namespace": NAMESPACE,
            "ready": ready,
        },
        "identity": {
            "tenant": identity["tenant"],
            "workspace": identity["workspace"],
            "api_key": {
                "id": identity["api_key"]["id"],
                "key_prefix": identity["api_key"]["key_prefix"],
                "display_name": identity["api_key"]["display_name"],
                "tenant_role": identity["api_key"]["tenant_role"],
                "tenant_capabilities": identity["api_key"]["tenant_capabilities"],
            },
        },
        "seeded": seeded,
        "billing": {
            "plan": plan,
            "subscription": subscription,
            "billing_period": billing_period,
            "materialized": materialized,
            "summarized": summarized,
            "reconciliation": reconciliation,
            "closeout_preview": closeout_preview,
            "closed": closed,
        },
        "tenant_views": {
            "scope": tenant_scope,
            "overview_closing": tenant_overview_closing,
            "overview_closed": tenant_overview_closed,
        },
        "commercial_events": {
            "before_close": commercial_events_before_close,
            "after_close": commercial_events_after_close,
        },
        "enforcement": {
            "closing_probe": enforcement_probe_closing,
            "closed_probe": enforcement_probe_closed,
        },
        "artifacts": {
            "report": report,
            "invoice": invoice,
            "ledger_truth": ledger_truth,
        },
        "pass_fail": _evaluate_pass_fail(
            ready=ready,
            summarized=summarized,
            reconciliation=reconciliation,
            closeout_preview=closeout_preview,
            commercial_events_before_close=commercial_events_before_close,
            commercial_events_after_close=commercial_events_after_close,
            enforcement_probe_closing=enforcement_probe_closing,
            enforcement_probe_closed=enforcement_probe_closed,
            tenant_scope=tenant_scope,
        ),
    }

    rendered = json.dumps(bundle, indent=2)
    print(rendered)
    print()
    print(_markdown_summary(bundle))

    if OUTPUT_PATH:
        output_path = Path(OUTPUT_PATH)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")

    return 0 if bundle["pass_fail"]["passed"] else 1


def _wait_for_ready(timeout_seconds: float = 180.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_response: dict | None = None
    while time.monotonic() < deadline:
        try:
            last_response = _get_json(f"{BASE_URL}/ready")
            if last_response.get("status") == "ready":
                return last_response
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError(f"app did not become ready; last response={last_response}")


def _bootstrap_identity() -> dict:
    payload = {
        "tenant": {
            "slug": TENANT_SLUG,
            "name": TENANT_NAME,
            "metadata": {"seeded_by": "run_h2_cloud_proof", "run_tag": RUN_TAG},
        },
        "workspace": {
            "slug": WORKSPACE_SLUG,
            "name": WORKSPACE_NAME,
            "metadata": {"seeded_by": "run_h2_cloud_proof", "run_tag": RUN_TAG},
        },
        "api_key": {
            "display_name": "H2 Cloud Proof Key",
            "tenant_role": "tenant_admin",
            "tenant_capabilities": [
                "billing:read",
                "billing:history:read",
                "billing:adjustments:read",
                "billing:scope:read",
            ],
            "metadata": {"seeded_by": "run_h2_cloud_proof", "run_tag": RUN_TAG},
        },
    }
    response = _post_json(
        f"{BASE_URL}/admin/control/bootstrap/tenant-environment",
        payload,
        headers=_admin_headers(),
    )
    return {
        "tenant_id": response["tenant"]["id"],
        "workspace_id": response["workspace"]["id"],
        "api_key_id": response["api_key"]["id"],
        "plaintext_api_key": response["api_key"]["plaintext_api_key"],
        "tenant": response["tenant"],
        "workspace": response["workspace"],
        "api_key": response["api_key"],
    }


def _reset_proof_state(*, tenant_id: str, workspace_id: str, api_key_id: str, plan_code: str, period_start: datetime, period_end: datetime) -> None:
    if not POLICY_STORE_DSN:
        raise RuntimeError("METERA_POLICY_STORE_DSN or METERA_SEMANTIC_STORE_DSN is required")
    start_iso = period_start.isoformat()
    end_iso = period_end.isoformat()
    sql = f"""
DELETE FROM usage_charges WHERE tenant_id = '{tenant_id}';
DELETE FROM invoices WHERE tenant_id = '{tenant_id}';
DELETE FROM billing_periods WHERE tenant_id = '{tenant_id}';
DELETE FROM subscriptions WHERE tenant_id = '{tenant_id}';
DELETE FROM commercial_events WHERE tenant_id = '{tenant_id}';
DELETE FROM request_ledger WHERE tenant_id = '{tenant_id}' AND observed_at >= '{start_iso}'::timestamptz AND observed_at < '{end_iso}'::timestamptz;
DELETE FROM api_key_lifecycle_log WHERE tenant_id = '{tenant_id}' AND api_key_id = '{api_key_id}';
DELETE FROM api_keys WHERE id = '{api_key_id}';
DELETE FROM environments WHERE workspace_id = '{workspace_id}';
DELETE FROM workspaces WHERE id = '{workspace_id}';
DELETE FROM tenants WHERE id = '{tenant_id}';
DELETE FROM plans WHERE code = '{plan_code}';
"""
    _psql(sql)


def _seed_threshold_scenario(*, tenant_id: str, workspace_id: str, api_key_id: str, period_start: datetime) -> dict:
    rows: list[str] = []
    total_tokens_saved = 0
    for i in range(THRESHOLD_REQUEST_COUNT):
        observed_at = (period_start + timedelta(minutes=i % 180, seconds=i % 60)).isoformat()
        cache_outcome = "semantic_hit" if i % 3 else "exact_hit"
        total_tokens = 150 + (i % 7)
        total_tokens_saved += total_tokens
        rows.append(
            "(" + ", ".join([
                f"'h2_cloud_proof_{RUN_TAG}_{i:04d}'",
                f"'{observed_at}'::timestamptz",
                f"'{tenant_id}'",
                f"'{workspace_id}'",
                "NULL",
                f"'{api_key_id}'",
                f"'{NAMESPACE}'",
                "'gpt-4o-mini'",
                "'openai_compatible'",
                f"'{cache_outcome}'",
                "NULL",
                "NULL",
                "NULL",
                "FALSE",
                "FALSE",
                "FALSE",
                "FALSE",
                "100",
                "50",
                str(total_tokens),
                f"{THRESHOLD_UPSTREAM_COST_USD}",
                f"{THRESHOLD_REALIZED_SAVINGS_USD}",
                "0.0",
                "20.0",
                "1.0",
                "2.0",
                "0.5",
                "0.0",
                f"'{{\"proof\":\"run_h2_cloud_proof\",\"run_tag\":\"{RUN_TAG}\"}}'::jsonb",
            ]) + ")"
        )
    sql = """
INSERT INTO request_ledger (
    request_id, observed_at, tenant_id, workspace_id, environment_id, api_key_id,
    namespace, model, provider, cache_outcome, semantic_bypass_reason,
    effective_policy_version_id, effective_policy_mode,
    has_visual_context, has_dom_context, is_agentic, identity_sensitive,
    prompt_tokens, completion_tokens, total_tokens,
    estimated_upstream_cost_usd, estimated_realized_savings_usd, estimated_shadow_savings_usd,
    request_latency_ms, profile_build_ms, semantic_lookup_ms, compatibility_validation_ms, upstream_ms,
    metadata
) VALUES
""" + ",\n".join(rows) + "\nON CONFLICT (request_id) DO NOTHING;"
    _psql(sql)
    return {
        "request_count": THRESHOLD_REQUEST_COUNT,
        "target_realized_savings_usd": round(THRESHOLD_REQUEST_COUNT * THRESHOLD_REALIZED_SAVINGS_USD, 2),
        "target_upstream_cost_usd": round(THRESHOLD_REQUEST_COUNT * THRESHOLD_UPSTREAM_COST_USD, 2),
        "target_total_tokens_saved": total_tokens_saved,
    }


def _ensure_billing_setup(*, tenant_id: str, period_start: datetime, period_end: datetime) -> tuple[dict, dict, dict]:
    plan = _post_json(
        f"{BASE_URL}/admin/control/billing/plans",
        {
            "code": PLAN_CODE,
            "name": "Pilot Alpha Proof",
            "monthly_base_price_usd": 50.0,
            "soft_cap_threshold_ratio": 0.8,
            "hard_cap_enabled": False,
            "metadata": {"scenario": "H2_Cloud_Proof", "proof": "run_h2_cloud_proof"},
        },
        headers=_admin_headers(),
    )
    subscription = _post_json(
        f"{BASE_URL}/admin/control/billing/subscriptions",
        {
            "tenant_id": tenant_id,
            "plan_id": plan["id"],
            "status": "trialing",
            "current_period_start": period_start.isoformat(),
            "current_period_end": period_end.isoformat(),
            "trial_ends_at": None,
        },
        headers=_admin_headers(),
    )
    billing_period = _post_json(
        f"{BASE_URL}/admin/control/billing/periods",
        {
            "tenant_id": tenant_id,
            "subscription_id": subscription["id"],
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
        headers=_admin_headers(),
    )
    return plan, subscription, billing_period


def _ledger_truth(*, tenant_id: str, period_start: datetime, period_end: datetime) -> dict:
    sql = f"""
SELECT
  COUNT(*),
  COALESCE(SUM(estimated_upstream_cost_usd), 0.0),
  COALESCE(SUM(estimated_realized_savings_usd), 0.0),
  COALESCE(SUM(CASE WHEN cache_outcome IN ('exact_hit','semantic_hit') THEN total_tokens ELSE 0 END), 0)
FROM request_ledger
WHERE tenant_id = '{tenant_id}'
  AND observed_at >= '{period_start.isoformat()}'::timestamptz
  AND observed_at < '{period_end.isoformat()}'::timestamptz
  AND metadata->>'proof' = 'run_h2_cloud_proof';
"""
    out = _psql(sql, raw=True).strip()
    request_count, upstream, realized, tokens = out.split("|")
    return {
        "request_count": int(request_count),
        "upstream_cost_usd_total": float(upstream),
        "realized_savings_usd_total": float(realized),
        "total_tokens_saved": int(tokens),
    }


def _evaluate_pass_fail(*, ready: dict, summarized: dict, reconciliation: dict, closeout_preview: dict, commercial_events_before_close: list[dict], commercial_events_after_close: list[dict], enforcement_probe_closing: dict, enforcement_probe_closed: dict, tenant_scope: dict) -> dict:
    event_types_before = {row.get("event_type") for row in commercial_events_before_close}
    event_types_after = {row.get("event_type") for row in commercial_events_after_close}
    checks = {
        "ready_status": ready.get("status") == "ready",
        "tenant_scope_authenticated": tenant_scope.get("source") == "proxy_context",
        "tenant_scope_admin_role": tenant_scope.get("role") == "tenant_admin",
        "billing_period_closing": summarized.get("status") == "closing",
        "reconciliation_matches": bool(reconciliation.get("matches_realized_savings")),
        "closeout_ready": closeout_preview.get("recommended_action") == "ready_to_close",
        "patronage_event_emitted": "patronage_required" in event_types_before,
        "closing_probe_is_402": int(enforcement_probe_closing.get("status_code", 0)) == 402,
        "closing_probe_reason": _extract_error_reason(enforcement_probe_closing) == "patronage_required",
        "service_suspended_event_emitted": "service_suspended" in event_types_after,
        "closed_probe_is_402": int(enforcement_probe_closed.get("status_code", 0)) == 402,
        "closed_probe_reason": _extract_error_reason(enforcement_probe_closed) == "service_suspended",
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {"passed": not failed, "checks": checks, "failed_checks": failed}


def _extract_error_reason(response: dict) -> str | None:
    body = response.get("body") or {}
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("reason")
    return None


def _markdown_summary(bundle: dict) -> str:
    pass_fail = bundle["pass_fail"]
    checks = pass_fail["checks"]
    lines = [
        "# H2 Cloud Proof Summary",
        "",
        f"- Base URL: `{bundle['proof_run']['base_url']}`",
        f"- Run Tag: `{bundle['proof_run']['run_tag']}`",
        f"- Tenant: `{bundle['identity']['tenant']['id']}`",
        f"- Workspace: `{bundle['identity']['workspace']['id']}`",
        f"- Namespace: `{bundle['proof_run']['namespace']}`",
        f"- Passed: `{pass_fail['passed']}`",
        "",
        "## Check Results",
    ]
    for name, ok in checks.items():
        lines.append(f"- {name}: {'PASS' if ok else 'FAIL'}")
    lines.extend([
        "",
        "## Commercial Outcome",
        f"- Closing probe status: `{bundle['enforcement']['closing_probe'].get('status_code')}`",
        f"- Closing probe reason: `{_extract_error_reason(bundle['enforcement']['closing_probe'])}`",
        f"- Closed probe status: `{bundle['enforcement']['closed_probe'].get('status_code')}`",
        f"- Closed probe reason: `{_extract_error_reason(bundle['enforcement']['closed_probe'])}`",
        "",
        "## Billing Snapshot",
        f"- Billing period: `{bundle['billing']['billing_period']['id']}`",
        f"- Summarized status: `{bundle['billing']['summarized'].get('status')}`",
        f"- Realized savings: `${bundle['billing']['summarized'].get('realized_savings_usd_total', 0.0):.2f}`",
        f"- Usage charges total: `${bundle['billing']['reconciliation'].get('usage_charges_total_usd', 0.0):.2f}`",
        f"- Tokens saved: `{bundle['billing']['summarized'].get('total_tokens_saved', 0)}`",
    ])
    return "\n".join(lines)


def _admin_headers() -> dict[str, str]:
    return {"x-metera-admin-key": ADMIN_KEY, "content-type": "application/json"}


def _tenant_headers(plaintext_api_key: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {plaintext_api_key}",
        "x-metera-namespace": NAMESPACE,
        "content-type": "application/json",
    }


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _post_json_allow_error(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return {"ok": True, "status_code": response.status, "body": json.loads(body) if body else {}}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return {"ok": False, "status_code": exc.code, "body": json.loads(body) if body else {}}


def _psql(sql: str, raw: bool = False) -> str:
    return asyncio.run(_psql_async(POLICY_STORE_DSN, sql, raw=raw))


async def _psql_async(dsn: str, sql: str, raw: bool = False) -> str:
    conn = await asyncpg.connect(dsn)
    try:
        statements = [part.strip() for part in sql.split(";") if part.strip()]
        if not statements:
            return ""
        if len(statements) > 1:
            async with conn.transaction():
                for statement in statements[:-1]:
                    await conn.execute(statement)
                final = statements[-1]
                if final.lower().startswith("select"):
                    rows = await conn.fetch(final)
                    return _format_asyncpg_rows(rows, raw=raw)
                await conn.execute(final)
                return ""
        statement = statements[0]
        if statement.lower().startswith("select"):
            rows = await conn.fetch(statement)
            return _format_asyncpg_rows(rows, raw=raw)
        await conn.execute(statement)
        return ""
    finally:
        await conn.close()


def _format_asyncpg_rows(rows, raw: bool = False) -> str:
    if not rows:
        return ""
    lines: list[str] = []
    for row in rows:
        values = ["" if value is None else str(value) for value in row]
        if raw:
            lines.append("|".join(values))
        else:
            lines.extend(values)
    return "\n".join(lines) + ("\n" if lines else "")


if __name__ == "__main__":
    raise SystemExit(main())

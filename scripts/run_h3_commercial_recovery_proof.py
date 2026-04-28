from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = os.getenv("METERA_ADMIN_API_KEY", "dev-admin-key")
RUN_TAG = os.getenv("METERA_PROOF_RUN_TAG") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
OUTPUT_PATH = os.getenv("METERA_PROOF_OUTPUT_PATH")
MODEL = os.getenv("METERA_PROOF_MODEL", "gpt-4o-mini")
TARGET_PROMPTS = int(os.getenv("METERA_PROOF_TARGET_PROMPTS", "20"))
MESSAGE_BLOCK_REPEATS = int(os.getenv("METERA_PROOF_MESSAGE_BLOCK_REPEATS", "3000"))
MESSAGE_COUNT = int(os.getenv("METERA_PROOF_MESSAGE_COUNT", "5"))
TENANT_SLUG = os.getenv("METERA_PROOF_TENANT_SLUG", f"h3-recovery-{RUN_TAG}")
WORKSPACE_SLUG = os.getenv("METERA_PROOF_WORKSPACE_SLUG", f"h3-recovery-ws-{RUN_TAG}")
TENANT_NAME = os.getenv("METERA_PROOF_TENANT_NAME", TENANT_SLUG.replace("-", " ").title())
WORKSPACE_NAME = os.getenv("METERA_PROOF_WORKSPACE_NAME", WORKSPACE_SLUG.replace("-", " ").title())
PLAN_CODE = os.getenv("METERA_PROOF_PLAN_CODE", f"h3_recovery_plan_{RUN_TAG}")
NAMESPACE = os.getenv("METERA_PROOF_NAMESPACE", f"{TENANT_SLUG}-{WORKSPACE_SLUG}")
PERIOD_START = os.getenv("METERA_PROOF_PERIOD_START", "2026-04-01T00:00:00+00:00")
PERIOD_END = os.getenv("METERA_PROOF_PERIOD_END", "2026-05-01T00:00:00+00:00")


def main() -> int:
    ready = _get_json(f"{BASE_URL}/ready")
    identity = _bootstrap_identity()
    plan, subscription, billing_period = _ensure_billing_setup(tenant_id=identity["tenant_id"])

    pre_enforcement_probe = _post_json(
        f"{BASE_URL}/v1/chat/completions",
        _chat_request_payload(),
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    traffic = _drive_cached_traffic(identity["plaintext_api_key"])

    materialized = _post_json(
        f"{BASE_URL}/admin/control/billing/usage-charges/materialize?source=ledger",
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
    report_before_close = _get_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/report?format=json",
        headers=_admin_headers(),
    )
    overview_closing = _get_json(
        f"{BASE_URL}/control/tenant/billing/overview",
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    closing_probe = _post_json_allow_error(
        f"{BASE_URL}/v1/chat/completions",
        _chat_request_payload(),
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )

    closed = _post_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period['id']}/close",
        {},
        headers=_admin_headers(),
    )
    overview_closed = _get_json(
        f"{BASE_URL}/control/tenant/billing/overview",
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    closed_probe = _post_json_allow_error(
        f"{BASE_URL}/v1/chat/completions",
        _chat_request_payload(),
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )

    recovery_activation = _activate_or_replace_subscription(
        tenant_id=identity["tenant_id"],
        prior_subscription=subscription,
        plan=plan,
    )
    overview_recovered = _get_json(
        f"{BASE_URL}/control/tenant/billing/overview",
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )
    recovered_probe = _post_json_allow_error(
        f"{BASE_URL}/v1/chat/completions",
        _chat_request_payload(),
        headers=_tenant_headers(identity["plaintext_api_key"]),
    )

    commercial_events = _get_json(
        f"{BASE_URL}/admin/control/billing/commercial-events?tenant_id={urllib.parse.quote(identity['tenant_id'])}&limit=50",
        headers=_admin_headers(),
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
        "billing": {
            "plan": plan,
            "subscription_initial": subscription,
            "billing_period": billing_period,
            "materialized": materialized,
            "summarized": summarized,
            "reconciliation": reconciliation,
            "closed": closed,
            "recovery_activation": recovery_activation,
            "report_before_close": report_before_close,
        },
        "tenant_views": {
            "overview_closing": overview_closing,
            "overview_closed": overview_closed,
            "overview_recovered": overview_recovered,
        },
        "traffic": {
            "pre_enforcement_probe": _extract_probe_summary(pre_enforcement_probe),
            "responses": traffic,
        },
        "enforcement": {
            "closing_probe": closing_probe,
            "closed_probe": closed_probe,
            "recovered_probe": recovered_probe,
        },
        "commercial_events": commercial_events,
        "pass_fail": _evaluate_pass_fail(
            ready=ready,
            closing_probe=closing_probe,
            closed_probe=closed_probe,
            recovered_probe=recovered_probe,
            recovery_activation=recovery_activation,
            overview_recovered=overview_recovered,
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


def _bootstrap_identity() -> dict:
    payload = {
        "tenant": {"slug": TENANT_SLUG, "name": TENANT_NAME, "metadata": {"seeded_by": "run_h3_commercial_recovery_proof", "run_tag": RUN_TAG}},
        "workspace": {"slug": WORKSPACE_SLUG, "name": WORKSPACE_NAME, "metadata": {"seeded_by": "run_h3_commercial_recovery_proof", "run_tag": RUN_TAG}},
        "api_key": {
            "display_name": "H3 Commercial Recovery Proof API Key",
            "tenant_role": "tenant_admin",
            "tenant_capabilities": ["billing:read", "billing:history:read", "billing:adjustments:read", "billing:scope:read"],
            "metadata": {"seeded_by": "run_h3_commercial_recovery_proof", "run_tag": RUN_TAG},
        },
    }
    response = _post_json(f"{BASE_URL}/admin/control/bootstrap/tenant-environment", payload, headers=_admin_headers())
    return {
        "tenant_id": response["tenant"]["id"],
        "workspace_id": response["workspace"]["id"],
        "api_key_id": response["api_key"]["id"],
        "plaintext_api_key": response["api_key"]["plaintext_api_key"],
        "tenant": response["tenant"],
        "workspace": response["workspace"],
        "api_key": response["api_key"],
    }


def _ensure_billing_setup(*, tenant_id: str) -> tuple[dict, dict, dict]:
    plan = _post_json(
        f"{BASE_URL}/admin/control/billing/plans",
        {
            "code": PLAN_CODE,
            "name": "H3 Commercial Recovery Proof Plan",
            "monthly_base_price_usd": 50.0,
            "soft_cap_threshold_ratio": 0.8,
            "hard_cap_enabled": False,
            "metadata": {"scenario": "H3_Commercial_Recovery_Proof", "proof": "run_h3_commercial_recovery_proof"},
        },
        headers=_admin_headers(),
    )
    subscription = _post_json(
        f"{BASE_URL}/admin/control/billing/subscriptions",
        {
            "tenant_id": tenant_id,
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
            "tenant_id": tenant_id,
            "subscription_id": subscription["id"],
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
        },
        headers=_admin_headers(),
    )
    return plan, subscription, billing_period


def _chat_request_payload() -> dict:
    chunk = "BLOCK " * MESSAGE_BLOCK_REPEATS
    messages = [{"role": "system", "content": "Reply with exactly H3_RECOVERY_OK"}]
    for _ in range(MESSAGE_COUNT):
        messages.append({"role": "user", "content": chunk})
    return {"model": MODEL, "messages": messages, "temperature": 0}


def _activate_or_replace_subscription(*, tenant_id: str, prior_subscription: dict, plan: dict) -> dict:
    status_update = _post_json_allow_error(
        f"{BASE_URL}/admin/control/billing/subscriptions/{prior_subscription['id']}/status",
        {"status": "active"},
        headers=_admin_headers(),
    )
    if status_update.get("ok"):
        body = status_update.get("body") or {}
        body["recovery_method"] = "status_update"
        return body
    if int(status_update.get("status_code", 0) or 0) != 404:
        return {
            "recovery_method": "status_update_failed",
            "status_code": status_update.get("status_code"),
            "body": status_update.get("body"),
        }
    replacement = _post_json(
        f"{BASE_URL}/admin/control/billing/subscriptions",
        {
            "tenant_id": tenant_id,
            "plan_id": plan["id"],
            "status": "active",
            "current_period_start": PERIOD_START,
            "current_period_end": PERIOD_END,
            "trial_ends_at": None,
        },
        headers=_admin_headers(),
    )
    replacement["recovery_method"] = "replacement_subscription"
    return replacement


def _drive_cached_traffic(plaintext_api_key: str) -> list[dict]:
    payload = _chat_request_payload()
    responses: list[dict] = []
    for _ in range(TARGET_PROMPTS):
        row = _post_json(f"{BASE_URL}/v1/chat/completions", payload, headers=_tenant_headers(plaintext_api_key))
        responses.append(
            {
                "cache": ((row.get("metera") or {}).get("cache")),
                "estimated_cost_usd": float(((row.get("metera") or {}).get("estimated_cost_usd", 0.0) or 0.0)),
                "estimated_savings_usd": float(((row.get("metera") or {}).get("estimated_savings_usd", 0.0) or 0.0)),
                "content": (((row.get("choices") or [{}])[0].get("message") or {}).get("content")),
            }
        )
    return responses


def _evaluate_pass_fail(*, ready: dict, closing_probe: dict, closed_probe: dict, recovered_probe: dict, recovery_activation: dict, overview_recovered: dict) -> dict:
    checks = {
        "ready_status": ready.get("status") == "ready",
        "closing_probe_is_402": int(closing_probe.get("status_code", 0) or 0) == 402,
        "closed_probe_is_402": int(closed_probe.get("status_code", 0) or 0) == 402,
        "recovery_activation_is_active": recovery_activation.get("status") == "active",
        "overview_active_subscription_after_recovery": ((overview_recovered.get("active_subscription") or {}).get("status")) == "active",
        "recovery_method_recorded": recovery_activation.get("recovery_method") in {"status_update", "replacement_subscription"},
        "recovered_probe_is_200": bool(recovered_probe.get("ok")) and int(recovered_probe.get("status_code", 0) or 0) == 200,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {"passed": not failed, "checks": checks, "failed_checks": failed}


def _extract_probe_summary(row: dict) -> dict:
    return {
        "cache": ((row.get("metera") or {}).get("cache")),
        "estimated_cost_usd": float(((row.get("metera") or {}).get("estimated_cost_usd", 0.0) or 0.0)),
        "estimated_savings_usd": float(((row.get("metera") or {}).get("estimated_savings_usd", 0.0) or 0.0)),
        "content": (((row.get("choices") or [{}])[0].get("message") or {}).get("content")),
    }


def _markdown_summary(bundle: dict) -> str:
    lines = [
        "# H3 Commercial Recovery Proof Summary",
        "",
        f"- Base URL: `{bundle['proof_run']['base_url']}`",
        f"- Run Tag: `{bundle['proof_run']['run_tag']}`",
        f"- Tenant: `{bundle['identity']['tenant']['id']}`",
        f"- Subscription: `{bundle['billing']['subscription_initial']['id']}`",
        f"- Billing period: `{bundle['billing']['billing_period']['id']}`",
        f"- Closing probe status: `{bundle['enforcement']['closing_probe'].get('status_code')}`",
        f"- Closed probe status: `{bundle['enforcement']['closed_probe'].get('status_code')}`",
        f"- Recovery activation status: `{bundle['billing']['recovery_activation'].get('status')}`",
        f"- Recovered probe status: `{bundle['enforcement']['recovered_probe'].get('status_code')}`",
        f"- Passed: `{bundle['pass_fail']['passed']}`",
    ]
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


if __name__ == "__main__":
    raise SystemExit(main())

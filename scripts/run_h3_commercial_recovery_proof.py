from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = os.getenv("METERA_ADMIN_API_KEY", "dev-admin-key")
RUN_TAG = os.getenv("METERA_PROOF_RUN_TAG") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
OUTPUT_PATH = os.getenv("METERA_PROOF_OUTPUT_PATH")
CHECKPOINT_PATH = os.getenv("METERA_PROOF_CHECKPOINT_PATH")
HTTP_TIMEOUT_SECONDS = float(os.getenv("METERA_PROOF_HTTP_TIMEOUT_SECONDS", "60"))
HTTP_RETRIES = int(os.getenv("METERA_PROOF_HTTP_RETRIES", "3"))
HTTP_RETRY_SLEEP_SECONDS = float(os.getenv("METERA_PROOF_HTTP_RETRY_SLEEP_SECONDS", "2"))
MODEL = os.getenv("METERA_PROOF_MODEL", "gpt-4o-mini")
TARGET_PROMPTS = int(os.getenv("METERA_PROOF_TARGET_PROMPTS", "20"))
MESSAGE_BLOCK_REPEATS = int(os.getenv("METERA_PROOF_MESSAGE_BLOCK_REPEATS", "3000"))
MESSAGE_COUNT = int(os.getenv("METERA_PROOF_MESSAGE_COUNT", "5"))
AUTO_SCALE_TO_ENFORCEMENT = os.getenv("METERA_PROOF_AUTO_SCALE_TO_ENFORCEMENT", "true").lower() in {"1", "true", "yes", "on"}
TARGET_REALIZED_SAVINGS_USD = float(os.getenv("METERA_PROOF_TARGET_REALIZED_SAVINGS_USD", os.getenv("METERA_BILLING_PATRONAGE_THRESHOLD_USD", "50.0")))
MAX_PROMPTS = int(os.getenv("METERA_PROOF_MAX_PROMPTS", "1200"))
CHECKPOINT_EVERY = int(os.getenv("METERA_PROOF_CHECKPOINT_EVERY", "50"))
PAUSE_SECONDS = float(os.getenv("METERA_PROOF_PAUSE_SECONDS", "0.0"))
MAX_REASONABLE_PROMPTS = int(os.getenv("METERA_PROOF_MAX_REASONABLE_PROMPTS", "2000"))
RESUME_FROM_CHECKPOINT = os.getenv("METERA_PROOF_RESUME_FROM_CHECKPOINT", "false").lower() in {"1", "true", "yes", "on"}
STOP_AFTER_ENFORCEMENT_CHECKPOINT = os.getenv("METERA_PROOF_STOP_AFTER_ENFORCEMENT_CHECKPOINT", "false").lower() in {"1", "true", "yes", "on"}
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
    resumed = False
    checkpoint_state = _load_checkpoint_state() if RESUME_FROM_CHECKPOINT else None
    if checkpoint_state is not None:
        resumed = True
        identity = checkpoint_state["identity"]
        plan = checkpoint_state["plan"]
        subscription = checkpoint_state["subscription"]
        billing_period = checkpoint_state["billing_period"]
        checkpoint_summarized = checkpoint_state.get("checkpoint_summarized") or {}
        checkpoint_guidance = checkpoint_state.get("checkpoint_guidance") or {}
        pre_enforcement_probe = checkpoint_state.get("pre_enforcement_probe") or {
            "cache": None,
            "estimated_cost_usd": 0.0,
            "estimated_savings_usd": 0.0,
            "content": None,
        }
    else:
        checkpoint_summarized = {}
        checkpoint_guidance = {}
        identity = _bootstrap_identity()
        plan, subscription, billing_period = _ensure_billing_setup(tenant_id=identity["tenant_id"])
        pre_enforcement_probe = _post_json(
            f"{BASE_URL}/v1/chat/completions",
            _chat_request_payload(),
            headers=_tenant_headers(identity["plaintext_api_key"]),
        )

    if resumed and str((billing_period or {}).get("status") or "") in {"closing", "closed"}:
        traffic = []
        materialized = {"resumed": True, "skipped": True}
        summarized = checkpoint_summarized or billing_period
        scaling = {
            "auto_scale_to_enforcement": AUTO_SCALE_TO_ENFORCEMENT,
            "target_realized_savings_usd": TARGET_REALIZED_SAVINGS_USD,
            "initial_target_prompts": TARGET_PROMPTS,
            "max_prompts": MAX_PROMPTS,
            "max_reasonable_prompts": MAX_REASONABLE_PROMPTS,
            "final_prompt_count": 0,
            "steps": [],
            "guidance": checkpoint_guidance,
            "resume_mode": "post-enforcement-state",
        }
    else:
        traffic, materialized, summarized, scaling = _drive_until_enforcement(
            plaintext_api_key=identity["plaintext_api_key"],
            tenant_id=identity["tenant_id"],
            subscription_id=subscription["id"],
            billing_period_id=billing_period["id"],
            plan=plan,
            subscription=subscription,
            billing_period=billing_period,
            pre_enforcement_probe=_extract_probe_summary(pre_enforcement_probe) if isinstance(pre_enforcement_probe, dict) and "choices" in pre_enforcement_probe else pre_enforcement_probe,
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

    if STOP_AFTER_ENFORCEMENT_CHECKPOINT and summarized.get("status") in {"closing", "closed"} and not resumed:
        bundle = {
            "proof_run": {
                "run_tag": RUN_TAG,
                "base_url": BASE_URL,
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "namespace": NAMESPACE,
                "ready": ready,
                "resumed_from_checkpoint": resumed,
                "stopped_after_enforcement_checkpoint": True,
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
                "report_before_close": report_before_close,
            },
            "tenant_views": {
                "overview_closing": overview_closing,
            },
            "traffic": {
                "pre_enforcement_probe": _extract_probe_summary(pre_enforcement_probe),
                "responses": traffic,
                "scaling": scaling,
            },
            "enforcement": {
                "closing_probe": closing_probe,
            },
        }
        print(json.dumps(bundle, indent=2))
        _write_json_file(OUTPUT_PATH, bundle)
        return 0

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
            "resumed_from_checkpoint": resumed,
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
            "scaling": scaling,
        },
        "enforcement": {
            "closing_probe": closing_probe,
            "closed_probe": closed_probe,
            "recovered_probe": recovered_probe,
        },
        "commercial_events": commercial_events,
        "pass_fail": _evaluate_pass_fail(
            ready=ready,
            summarized=summarized,
            scaling=scaling,
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

    _write_json_file(OUTPUT_PATH, bundle)

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


def _drive_cached_traffic(plaintext_api_key: str, *, prompt_count: int) -> list[dict]:
    payload = _chat_request_payload()
    responses: list[dict] = []
    for _ in range(prompt_count):
        row = _post_json(f"{BASE_URL}/v1/chat/completions", payload, headers=_tenant_headers(plaintext_api_key))
        responses.append(
            {
                "cache": ((row.get("metera") or {}).get("cache")),
                "estimated_cost_usd": float(((row.get("metera") or {}).get("estimated_cost_usd", 0.0) or 0.0)),
                "estimated_savings_usd": float(((row.get("metera") or {}).get("estimated_savings_usd", 0.0) or 0.0)),
                "content": (((row.get("choices") or [{}])[0].get("message") or {}).get("content")),
            }
        )
        if PAUSE_SECONDS > 0:
            time.sleep(PAUSE_SECONDS)
    return responses


def _materialize_and_summarize(*, tenant_id: str, subscription_id: str, billing_period_id: str) -> tuple[dict, dict]:
    materialized = _post_json(
        f"{BASE_URL}/admin/control/billing/usage-charges/materialize?source=ledger",
        {
            "tenant_id": tenant_id,
            "subscription_id": subscription_id,
            "billing_period_id": billing_period_id,
            "rollup_date": None,
            "limit": 2000,
        },
        headers=_admin_headers(),
    )
    summarized = _post_json(
        f"{BASE_URL}/admin/control/billing/periods/{billing_period_id}/summarize",
        {},
        headers=_admin_headers(),
    )
    return materialized, summarized


def _write_json_file(path_value: str | None, payload: dict) -> None:
    if not path_value:
        return
    output_path = Path(path_value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_checkpoint_state() -> dict | None:
    if not CHECKPOINT_PATH:
        raise RuntimeError("METERA_PROOF_RESUME_FROM_CHECKPOINT=true requires METERA_PROOF_CHECKPOINT_PATH")
    checkpoint_file = Path(CHECKPOINT_PATH)
    if not checkpoint_file.exists():
        raise RuntimeError(f"checkpoint file not found: {checkpoint_file}")
    payload = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    checkpoint = payload.get("checkpoint") or {}
    identity = checkpoint.get("identity") or {}
    plan = checkpoint.get("plan") or {}
    subscription = checkpoint.get("subscription") or {}
    billing_period = checkpoint.get("billing_period") or {}
    if not identity.get("plaintext_api_key"):
        raise RuntimeError("checkpoint missing plaintext_api_key; cannot resume tenant traffic")
    required = [identity.get("tenant_id"), subscription.get("id"), billing_period.get("id")]
    if any(not value for value in required):
        raise RuntimeError("checkpoint missing tenant/subscription/billing_period identifiers")
    period_rows = _get_json(
        f"{BASE_URL}/admin/control/billing/periods?tenant_id={urllib.parse.quote(identity['tenant_id'])}",
        headers=_admin_headers(),
    )
    current_subscription = _get_json(
        f"{BASE_URL}/admin/control/billing/subscriptions?tenant_id={urllib.parse.quote(identity['tenant_id'])}",
        headers=_admin_headers(),
    )
    current_period = next((row for row in period_rows if isinstance(row, dict) and row.get('id') == billing_period['id']), billing_period) if isinstance(period_rows, list) else billing_period
    latest_subscription = current_subscription[0] if isinstance(current_subscription, list) and current_subscription else subscription
    normalized_identity = {
        "tenant_id": identity.get("tenant_id"),
        "workspace_id": identity.get("workspace_id"),
        "api_key_id": identity.get("api_key_id"),
        "plaintext_api_key": identity.get("plaintext_api_key"),
        "tenant": identity.get("tenant") or {"id": identity.get("tenant_id")},
        "workspace": identity.get("workspace") or {"id": identity.get("workspace_id")},
        "api_key": identity.get("api_key") or {
            "id": identity.get("api_key_id"),
            "key_prefix": None,
            "display_name": "checkpoint_resume_key",
            "tenant_role": None,
            "tenant_capabilities": [],
        },
    }
    return {
        "identity": normalized_identity,
        "plan": plan,
        "subscription": latest_subscription,
        "billing_period": current_period if isinstance(current_period, dict) else billing_period,
        "pre_enforcement_probe": checkpoint.get("pre_enforcement_probe"),
        "checkpoint_summarized": checkpoint.get("summarized") or {},
        "checkpoint_guidance": checkpoint.get("guidance") or {},
    }


def _drive_until_enforcement(*, plaintext_api_key: str, tenant_id: str, subscription_id: str, billing_period_id: str, plan: dict, subscription: dict, billing_period: dict, pre_enforcement_probe: dict | None = None) -> tuple[list[dict], dict, dict, dict]:
    responses: list[dict] = []
    scaling_steps: list[dict] = []
    requested_total = min(TARGET_PROMPTS, MAX_PROMPTS)
    materialized: dict = {}
    summarized: dict = {}
    guidance: dict = {}

    while True:
        remaining = max(0, requested_total - len(responses))
        if remaining > 0:
            batch = _drive_cached_traffic(plaintext_api_key, prompt_count=remaining)
            responses.extend(batch)
        materialized, summarized = _materialize_and_summarize(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            billing_period_id=billing_period_id,
        )
        realized = float((summarized or {}).get("realized_savings_usd_total", 0.0) or 0.0)
        request_count = int((summarized or {}).get("request_count", 0) or 0)
        average_realized_per_request = (realized / request_count) if request_count > 0 else 0.0
        estimated_required_prompts = math.ceil(TARGET_REALIZED_SAVINGS_USD / average_realized_per_request) if average_realized_per_request > 0 else None
        scaling_steps.append(
            {
                "after_requests": len(responses),
                "billing_request_count": request_count,
                "realized_savings_usd_total": realized,
                "billing_period_status": summarized.get("status"),
                "average_realized_savings_per_request": average_realized_per_request,
                "estimated_required_prompts": estimated_required_prompts,
            }
        )
        if estimated_required_prompts and estimated_required_prompts > MAX_REASONABLE_PROMPTS:
            guidance = {
                "reason": "threshold_not_reasonably_reachable",
                "estimated_required_prompts": estimated_required_prompts,
                "max_reasonable_prompts": MAX_REASONABLE_PROMPTS,
                "target_realized_savings_usd": TARGET_REALIZED_SAVINGS_USD,
                "suggested_actions": [
                    "lower METERA_BILLING_PATRONAGE_THRESHOLD_USD for proof posture",
                    "or raise METERA_PROOF_MAX_PROMPTS if you intentionally want a long burn-in proof",
                ],
            }
        _write_json_file(
            CHECKPOINT_PATH,
            {
                "proof_run": {
                    "run_tag": RUN_TAG,
                    "base_url": BASE_URL,
                    "generated_at_utc": datetime.now(UTC).isoformat(),
                    "namespace": NAMESPACE,
                },
                "checkpoint": {
                    "after_requests": len(responses),
                    "target_realized_savings_usd": TARGET_REALIZED_SAVINGS_USD,
                    "max_prompts": MAX_PROMPTS,
                    "billing_period_id": billing_period_id,
                    "subscription_id": subscription_id,
                    "tenant_id": tenant_id,
                    "identity": {
                        "tenant_id": tenant_id,
                        "plaintext_api_key": plaintext_api_key,
                    },
                    "plan": plan,
                    "subscription": subscription,
                    "billing_period": billing_period,
                    "pre_enforcement_probe": pre_enforcement_probe,
                    "materialized": materialized,
                    "summarized": summarized,
                    "steps": scaling_steps,
                    "guidance": guidance,
                },
            },
        )
        if summarized.get("status") == "closing":
            break
        if guidance:
            break
        if not AUTO_SCALE_TO_ENFORCEMENT:
            break
        if len(responses) >= MAX_PROMPTS:
            break
        if average_realized_per_request <= 0.0:
            next_total = min(MAX_PROMPTS, max(len(responses) + CHECKPOINT_EVERY, requested_total + CHECKPOINT_EVERY))
        else:
            required_total = math.ceil(TARGET_REALIZED_SAVINGS_USD / average_realized_per_request)
            next_total = min(MAX_PROMPTS, max(required_total, len(responses) + CHECKPOINT_EVERY))
        if next_total <= len(responses):
            break
        requested_total = next_total

    scaling = {
        "auto_scale_to_enforcement": AUTO_SCALE_TO_ENFORCEMENT,
        "target_realized_savings_usd": TARGET_REALIZED_SAVINGS_USD,
        "initial_target_prompts": TARGET_PROMPTS,
        "max_prompts": MAX_PROMPTS,
        "max_reasonable_prompts": MAX_REASONABLE_PROMPTS,
        "final_prompt_count": len(responses),
        "steps": scaling_steps,
        "guidance": guidance,
    }
    return responses, materialized, summarized, scaling


def _evaluate_pass_fail(*, ready: dict, summarized: dict, scaling: dict, closing_probe: dict, closed_probe: dict, recovered_probe: dict, recovery_activation: dict, overview_recovered: dict) -> dict:
    checks = {
        "ready_status": ready.get("status") == "ready",
        "billing_period_reached_closing": summarized.get("status") in {"closing", "closed"},
        "threshold_reasonably_reachable": not bool((scaling or {}).get("guidance")),
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


def _open_with_retry(request: urllib.request.Request, *, allow_http_error: bool = False) -> tuple[bool, int, dict | list]:
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
                return True, int(response.status), json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            if allow_http_error:
                return False, int(exc.code), parsed
            last_error = exc
            if attempt >= HTTP_RETRIES:
                raise RuntimeError(f"HTTP {exc.code} from {request.full_url}: {parsed}") from exc
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt >= HTTP_RETRIES:
                raise RuntimeError(f"Request failed for {request.full_url} after {HTTP_RETRIES} attempts: {exc}") from exc
            time.sleep(HTTP_RETRY_SLEEP_SECONDS)
        except TimeoutError as exc:
            last_error = exc
            if attempt >= HTTP_RETRIES:
                raise RuntimeError(f"Request timed out for {request.full_url} after {HTTP_RETRIES} attempts: {exc}") from exc
            time.sleep(HTTP_RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"Request failed for {request.full_url}: {last_error}")


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    _, _, payload = _open_with_retry(request)
    return payload


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {"content-type": "application/json"},
        method="POST",
    )
    _, _, body = _open_with_retry(request)
    return body if isinstance(body, dict) else {}


def _post_json_allow_error(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {"content-type": "application/json"},
        method="POST",
    )
    ok, status_code, body = _open_with_retry(request, allow_http_error=True)
    return {"ok": ok, "status_code": status_code, "body": body if isinstance(body, dict) else {}}


if __name__ == "__main__":
    raise SystemExit(main())

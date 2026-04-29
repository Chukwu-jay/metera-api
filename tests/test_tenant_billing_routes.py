from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.routes_tenant_billing import router


class FakeBillingRepository:
    def __init__(self) -> None:
        self.invoices: dict[str, dict] = {}

    async def list_subscriptions(self, *, tenant_id=None):
        scoped_tenant_id = tenant_id or "tenant_1"
        return [
            {
                "id": "subscription_1",
                "tenant_id": scoped_tenant_id,
                "plan_id": "plan_1",
                "status": "active",
                "current_period_start": datetime.fromisoformat("2026-04-01T00:00:00"),
                "current_period_end": datetime.fromisoformat("2026-05-01T00:00:00"),
            },
            {
                "id": "subscription_2",
                "tenant_id": scoped_tenant_id,
                "plan_id": "plan_2",
                "status": "active",
                "current_period_start": datetime.fromisoformat("2026-05-01T00:00:00"),
                "current_period_end": datetime.fromisoformat("2026-06-01T00:00:00"),
            },
        ]

    async def list_billing_periods(self, *, tenant_id=None, subscription_id=None):
        scoped_tenant_id = tenant_id or "tenant_1"
        rows = [
            {
                "id": "billing_period_1",
                "tenant_id": scoped_tenant_id,
                "subscription_id": subscription_id or "subscription_1",
                "period_start": datetime.fromisoformat("2026-04-01T00:00:00"),
                "period_end": datetime.fromisoformat("2026-05-01T00:00:00"),
                "status": "closing",
                "request_count": 12,
                "upstream_cost_usd_total": 60.0,
                "realized_savings_usd_total": 50.01,
                "shadow_savings_usd_total": 0.75,
                "total_tokens_saved": 1800,
                "closed_at": None,
            },
            {
                "id": "billing_period_2",
                "tenant_id": scoped_tenant_id,
                "subscription_id": subscription_id or "subscription_1",
                "period_start": datetime.fromisoformat("2026-03-01T00:00:00"),
                "period_end": datetime.fromisoformat("2026-04-01T00:00:00"),
                "status": "open",
                "request_count": 8,
                "upstream_cost_usd_total": 40.0,
                "realized_savings_usd_total": 15.0,
                "shadow_savings_usd_total": 0.25,
                "total_tokens_saved": 420,
                "closed_at": None,
            },
        ]
        return rows

    async def generate_billing_report(self, *, billing_period_id, export_format="json"):
        return {
            "billing_period_id": billing_period_id,
            "tenant_id": "tenant_1",
            "subscription_id": "subscription_1",
            "status": "closing",
            "period_start": "2026-04-01T00:00:00",
            "period_end": "2026-05-01T00:00:00",
            "request_count": 12,
            "gross_cost_usd": 60.0,
            "metera_savings_usd": 50.01,
            "shadow_savings_usd": 0.75,
            "usage_charges_total_usd": 50.01,
            "total_tokens_saved": 1800,
            "realized_savings_ratio": 0.8335,
            "matches_realized_savings": True,
            "blocking_issues": [],
            "summary_lines": ["Gross Cost: $60.00", "Intelligence Recovered (Tokens): 1,800"],
            "line_items": ["gross_cost_usd=60.00", "metera_savings_usd=50.01", "total_tokens_saved=1800"],
            "billing_window": {
                "period_start": "2026-04-01T00:00:00",
                "period_end": "2026-05-01T00:00:00",
                "closed_at": None,
            },
            "totals": {
                "gross_cost_usd": 60.0,
                "metera_savings_usd": 50.01,
                "shadow_savings_usd": 0.75,
                "usage_charges_total_usd": 50.01,
                "realized_savings_ratio": 0.8335,
                "total_tokens_saved": 1800.0,
            },
            "reconciliation": {
                "matches_realized_savings": True,
                "difference_usd": 0.0,
            },
            "narrative": ["Processed 12 requests in the billing window."],
            "export_content": '{"billing_period_id":"billing_period_1"}' if export_format == "json" else "Metera Billing Report",
            "export_filename": "billing_report_billing_period_1.json" if export_format == "json" else "billing_report_billing_period_1.txt",
            "format": export_format,
        }

    async def generate_invoice_stub(self, *, billing_period_id, export_format="json"):
        invoice = {
            "id": f"invoice_for_{billing_period_id}",
            "tenant_id": "tenant_1",
            "billing_period_id": billing_period_id,
            "status": "draft",
            "subtotal_usd": 60.0,
            "total_usd": 0.0,
            "gross_cost_usd": 60.0,
            "metera_savings_usd": 50.01,
            "net_cost_avoided_usd": 50.01,
            "total_tokens_saved": 1800,
            "realized_savings_ratio": 0.8335,
            "summary_lines": ["Gross Cost: $60.00", "Intelligence Recovered (Tokens): 1,800"],
            "billing_window": {
                "period_start": "2026-04-01T00:00:00",
                "period_end": "2026-05-01T00:00:00",
                "closed_at": None,
            },
            "totals": {
                "gross_cost_usd": 60.0,
                "metera_savings_usd": 50.01,
                "net_cost_avoided_usd": 50.01,
                "realized_savings_ratio": 0.8335,
                "total_tokens_saved": 1800.0,
            },
            "narrative": ["Customer-facing invoice preview generated from the current billing-period snapshot."],
            "proven_roi": {
                "gross_cost_usd": 60.0,
                "metera_savings_usd": 50.01,
                "net_cost_avoided_usd": 50.01,
                "realized_savings_ratio": 0.8335,
                "total_tokens_saved": 1800.0,
            },
            "format": export_format,
            "export_content": '{"billing_period_id":"billing_period_1"}' if export_format == "json" else "Metera Invoice Preview",
            "export_filename": "invoice_stub_billing_period_1.json" if export_format == "json" else "invoice_stub_billing_period_1.txt",
        }
        self.invoices[billing_period_id] = invoice
        return invoice

    async def list_usage_charges(self, *, tenant_id=None, limit=100):
        return [
            {
                "id": "adjustment_1",
                "tenant_id": tenant_id or "tenant_1",
                "subscription_id": "subscription_1",
                "billing_period_id": "billing_period_1",
                "source_table": "manual",
                "source_ref": "manual_adjustment:adjustment_1",
                "description": "Late-arriving correction",
                "amount_usd": 5.0,
                "charge_type": "manual_adjustment",
            },
            {
                "id": "charge_2",
                "tenant_id": tenant_id or "tenant_1",
                "subscription_id": "subscription_1",
                "billing_period_id": "billing_period_1",
                "source_table": "daily_usage_rollups",
                "source_ref": "2026-04-22:workspace_1",
                "description": "Managed spend",
                "amount_usd": 50.01,
                "charge_type": "managed_spend",
            },
            {
                "id": "charge_3",
                "tenant_id": tenant_id or "tenant_1",
                "subscription_id": "subscription_1",
                "billing_period_id": "billing_period_2",
                "source_table": "request_ledger",
                "source_ref": "req_123",
                "description": "Request overage",
                "amount_usd": 3.5,
                "charge_type": "request_overage",
            },
        ][:limit]


class FakeCommercialEventRepository:
    async def list_events_for_tenant(self, *, tenant_id: str, limit: int = 50):
        return [
            {
                "event_id": "billing_period_closed:billing_period_1",
                "billing_period_id": "billing_period_1",
                "event_type": "billing_period_closed",
                "status": "closed",
                "reason": "close_confirmed",
                "tenant_id": tenant_id,
            },
            {
                "event_id": "billing_period_previewed:billing_period_2",
                "billing_period_id": "billing_period_2",
                "event_type": "billing_period_previewed",
                "status": "ready",
                "reason": "preview_generated",
                "tenant_id": tenant_id,
            },
        ][:limit]


def build_app(
    with_repo: bool = True,
    scoped_tenant_id: str | None = None,
    scoped_tenant_role: str | None = None,
    scoped_tenant_capabilities: tuple[str, ...] | None = None,
    tenant_query_param_fallback_enabled: bool | None = True,
    environment: str = "dev",
) -> FastAPI:
    app = FastAPI()

    if scoped_tenant_id is not None:
        @app.middleware("http")
        async def inject_proxy_context(request: Request, call_next):
            request.state.proxy_context = type(
                "ProxyContext",
                (),
                {
                    "tenant_id": scoped_tenant_id,
                    "tenant_role": scoped_tenant_role,
                    "tenant_capabilities": scoped_tenant_capabilities or (),
                },
            )()
            return await call_next(request)

    app.include_router(router)
    app.state.services = type(
        "Services",
        (),
        {
            "billing_repository": FakeBillingRepository() if with_repo else None,
            "commercial_event_repository": FakeCommercialEventRepository() if with_repo else None,
        },
    )()
    runtime_settings = type("S", (), {})()
    runtime_settings.tenant_query_param_fallback_enabled = tenant_query_param_fallback_enabled
    runtime_settings.environment = environment
    runtime_settings.effective_tenant_query_param_fallback_enabled = (
        tenant_query_param_fallback_enabled
        if tenant_query_param_fallback_enabled is not None
        else environment.lower() in {"dev", "local", "test"}
    )
    app.state.runtime_settings = runtime_settings
    return app


def test_tenant_billing_routes_query_param_fallback() -> None:
    client = TestClient(build_app())
    scope = client.get("/control/tenant/billing/scope?tenant_id=tenant_1")
    overview = client.get("/control/tenant/billing/overview?tenant_id=tenant_1")
    subscriptions = client.get("/control/tenant/billing/subscriptions?tenant_id=tenant_1&limit=1")
    periods = client.get("/control/tenant/billing/periods?tenant_id=tenant_1&status_filter=closing&limit=1")
    reports = client.get("/control/tenant/billing/reports?tenant_id=tenant_1&limit=1&format=json")
    invoices = client.get("/control/tenant/billing/invoices?tenant_id=tenant_1&limit=1&format=json")
    history = client.get("/control/tenant/billing/history?tenant_id=tenant_1&event_type=billing_period_closed&limit=1")
    usage_charges = client.get("/control/tenant/billing/usage-charges?tenant_id=tenant_1&billing_period_id=billing_period_1&charge_type=managed_spend&limit=1")
    adjustments = client.get("/control/tenant/billing/adjustments?tenant_id=tenant_1&billing_period_id=billing_period_1&limit=1")
    report = client.get("/control/tenant/billing/periods/billing_period_1/report?tenant_id=tenant_1&format=text")
    invoice = client.get("/control/tenant/billing/periods/billing_period_1/invoice?tenant_id=tenant_1&format=text")

    assert scope.status_code == 200
    assert scope.json()["source"] == "query_param_fallback"
    assert scope.json()["role"] == "tenant_reader"
    assert scope.json()["capabilities"] == ["billing:read", "billing:scope:read"]
    assert overview.status_code == 200
    assert overview.json()["tenant_id"] == "tenant_1"
    assert overview.json()["role"] == "tenant_reader"
    assert overview.json()["active_subscription"]["id"] == "subscription_1"
    assert overview.json()["current_billing_period"]["id"] == "billing_period_1"
    assert overview.json()["current_billing_period"]["total_tokens_saved"] == 1800
    assert overview.json()["current_billing_customer_status"] == "review_ready"
    assert "ready for closeout" in overview.json()["current_billing_status_explainer"]
    assert overview.json()["latest_report"]["billing_period_id"] == "billing_period_1"
    assert overview.json()["latest_report"]["total_tokens_saved"] == 1800
    assert "line_items" not in overview.json()["latest_report"]
    assert "reconciliation" not in overview.json()["latest_report"]
    assert "export_content" not in overview.json()["latest_report"]
    assert overview.json()["latest_invoice"]["billing_period_id"] == "billing_period_1"
    assert overview.json()["latest_invoice"]["total_tokens_saved"] == 1800
    assert "export_content" not in overview.json()["latest_invoice"]
    assert overview.json()["recent_history"] == []
    assert overview.json()["outstanding_adjustments"] == []
    assert overview.json()["grouped_charge_totals"]["managed_spend"] == 50.01
    assert overview.json()["health_flags"] == ["billing_period_closing"]
    assert overview.json()["recommended_action"] == "review_period_for_closeout"
    assert "confirm whether it is ready for closeout" in overview.json()["recommended_action_explainer"]
    assert subscriptions.status_code == 200
    assert subscriptions.json()["count"] == 1
    assert subscriptions.json()["has_more"] is True
    assert subscriptions.json()["next_offset"] == 1
    assert subscriptions.json()["items"][0]["tenant_id"] == "tenant_1"
    assert periods.status_code == 200
    assert periods.json()["count"] == 1
    assert periods.json()["has_more"] is False
    assert periods.json()["next_offset"] is None
    assert periods.json()["items"][0]["status"] == "closing"
    assert reports.status_code == 200
    assert reports.json()["count"] == 1
    assert reports.json()["has_more"] is True
    assert reports.json()["next_offset"] == 1
    assert reports.json()["items"][0]["billing_period_id"] == "billing_period_1"
    assert reports.json()["items"][0]["total_tokens_saved"] == 1800
    assert reports.json()["items"][0]["customer_status"] == "review_ready"
    assert reports.json()["items"][0]["additional_savings_opportunity_usd"] == 0.75
    assert "line_items" not in reports.json()["items"][0]
    assert "reconciliation" not in reports.json()["items"][0]
    assert "export_content" not in reports.json()["items"][0]
    assert invoices.status_code == 200
    assert invoices.json()["count"] == 1
    assert invoices.json()["has_more"] is True
    assert invoices.json()["next_offset"] == 1
    assert invoices.json()["items"][0]["billing_period_id"] == "billing_period_1"
    assert invoices.json()["items"][0]["status"] == "draft"
    assert invoices.json()["items"][0]["customer_status"] == "preview"
    assert "preview generated from the current billing snapshot" in invoices.json()["items"][0]["status_explainer"]
    assert "export_content" not in invoices.json()["items"][0]
    assert usage_charges.status_code == 200
    assert usage_charges.json()["count"] == 1
    assert usage_charges.json()["items"][0]["charge_type"] == "managed_spend"
    assert usage_charges.json()["items"][0]["source_table"] == "daily_usage_rollups"
    assert history.status_code == 403
    assert history.json()["detail"] == "Tenant role 'tenant_reader' is not allowed to perform 'billing:history:read'"
    assert adjustments.status_code == 403
    assert adjustments.json()["detail"] == "Tenant role 'tenant_reader' is not allowed to perform 'billing:adjustments:read'"
    assert report.status_code == 200
    assert report.json()["billing_period_id"] == "billing_period_1"
    assert report.json()["total_tokens_saved"] == 1800
    assert report.json()["customer_status"] == "review_ready"
    assert report.json()["export_filename"].endswith(".txt")
    assert "line_items" not in report.json()
    assert "reconciliation" not in report.json()
    assert "export_content" not in report.json()
    assert invoice.status_code == 200
    assert invoice.json()["billing_period_id"] == "billing_period_1"
    assert invoice.json()["status"] == "draft"
    assert invoice.json()["customer_status"] == "preview"
    assert invoice.json()["export_filename"].endswith(".txt")
    assert "export_content" not in invoice.json()


def test_tenant_billing_routes_prefer_authenticated_scope() -> None:
    client = TestClient(build_app(scoped_tenant_id="tenant_scoped"))
    scope = client.get("/control/tenant/billing/scope")
    overview = client.get("/control/tenant/billing/overview")
    subscriptions = client.get("/control/tenant/billing/subscriptions?limit=1&offset=1")
    history = client.get("/control/tenant/billing/history?limit=1")
    usage_charges = client.get("/control/tenant/billing/usage-charges?limit=2")
    invoices = client.get("/control/tenant/billing/invoices?limit=1")
    adjustments = client.get("/control/tenant/billing/adjustments?billing_period_id=billing_period_1&limit=1")

    assert scope.status_code == 200
    assert scope.json()["tenant_id"] == "tenant_scoped"
    assert scope.json()["source"] == "proxy_context"
    assert scope.json()["role"] == "tenant_admin"
    assert scope.json()["capabilities"] == [
        "billing:adjustments:read",
        "billing:history:read",
        "billing:read",
        "billing:scope:read",
    ]
    assert overview.status_code == 200
    assert overview.json()["tenant_id"] == "tenant_scoped"
    assert overview.json()["recent_history"][0]["event_id"] == "billing_period_closed:billing_period_1"
    assert overview.json()["outstanding_adjustments"][0]["id"] == "adjustment_1"
    assert overview.json()["recent_usage_charges"][0]["id"] == "adjustment_1"
    assert overview.json()["totals_snapshot"]["current_period_realized_savings_usd_total"] == 50.01
    assert overview.json()["totals_snapshot"]["current_period_total_tokens_saved"] == 1800.0
    assert overview.json()["current_billing_customer_status"] == "review_ready"
    assert overview.json()["grouped_charge_totals"]["manual_adjustment"] == 5.0
    assert overview.json()["grouped_charge_totals"]["managed_spend"] == 50.01
    assert "manual_adjustments_present" in overview.json()["health_flags"]
    assert "billing_period_closing" in overview.json()["health_flags"]
    assert overview.json()["recommended_action"] == "review_period_for_closeout"
    assert subscriptions.status_code == 200
    assert subscriptions.json()["count"] == 1
    assert subscriptions.json()["has_more"] is False
    assert subscriptions.json()["next_offset"] is None
    assert subscriptions.json()["items"][0]["tenant_id"] == "tenant_scoped"
    assert subscriptions.json()["items"][0]["id"] == "subscription_2"
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["has_more"] is True
    assert history.json()["next_offset"] == 1
    assert usage_charges.status_code == 200
    assert usage_charges.json()["count"] == 2
    assert usage_charges.json()["has_more"] is True
    assert usage_charges.json()["next_offset"] == 2
    assert usage_charges.json()["items"][0]["tenant_id"] == "tenant_scoped"
    assert invoices.status_code == 200
    assert invoices.json()["count"] == 1
    assert invoices.json()["items"][0]["billing_period_id"] == "billing_period_1"
    assert adjustments.status_code == 200
    assert adjustments.json()["count"] == 1
    assert adjustments.json()["has_more"] is False
    assert adjustments.json()["items"][0]["charge_type"] == "manual_adjustment"


def test_tenant_billing_routes_reject_tenant_mismatch() -> None:
    client = TestClient(build_app(scoped_tenant_id="tenant_scoped"))
    response = client.get("/control/tenant/billing/subscriptions?tenant_id=tenant_other")
    assert response.status_code == 403
    assert response.json()["detail"] == "Requested tenant does not match authenticated tenant scope"


def test_tenant_billing_routes_reject_role_without_capability() -> None:
    client = TestClient(build_app(scoped_tenant_id="tenant_scoped", scoped_tenant_role="tenant_guest"))
    response = client.get("/control/tenant/billing/history")
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant role 'tenant_guest' is not allowed to perform 'billing:history:read'"


def test_tenant_billing_routes_derive_role_from_capabilities() -> None:
    client = TestClient(
        build_app(
            scoped_tenant_id="tenant_scoped",
            scoped_tenant_role=None,
            scoped_tenant_capabilities=(
                "billing:read",
                "billing:scope:read",
                "billing:history:read",
                "billing:adjustments:read",
            ),
        )
    )
    scope = client.get("/control/tenant/billing/scope")
    history = client.get("/control/tenant/billing/history")

    assert scope.status_code == 200
    assert scope.json()["role"] == "tenant_admin"
    assert scope.json()["capabilities"] == [
        "billing:adjustments:read",
        "billing:history:read",
        "billing:read",
        "billing:scope:read",
    ]
    assert history.status_code == 200


def test_tenant_billing_routes_capabilities_override_unrecognized_role() -> None:
    client = TestClient(
        build_app(
            scoped_tenant_id="tenant_scoped",
            scoped_tenant_role="workspace_member",
            scoped_tenant_capabilities=("billing:read", "billing:scope:read"),
        )
    )
    scope = client.get("/control/tenant/billing/scope")
    history = client.get("/control/tenant/billing/history")

    assert scope.status_code == 200
    assert scope.json()["role"] == "tenant_reader"
    assert scope.json()["capabilities"] == ["billing:read", "billing:scope:read"]
    assert history.status_code == 403
    assert history.json()["detail"] == "Tenant role 'tenant_reader' is not allowed to perform 'billing:history:read'"


def test_tenant_billing_routes_union_role_defaults_with_explicit_capabilities() -> None:
    client = TestClient(
        build_app(
            scoped_tenant_id="tenant_scoped",
            scoped_tenant_role="tenant_reader",
            scoped_tenant_capabilities=("billing:history:read",),
        )
    )
    scope = client.get("/control/tenant/billing/scope")
    history = client.get("/control/tenant/billing/history")

    assert scope.status_code == 200
    assert scope.json()["role"] == "tenant_reader"
    assert scope.json()["capabilities"] == ["billing:history:read", "billing:read", "billing:scope:read"]
    assert history.status_code == 200


def test_tenant_billing_routes_preserve_unknown_capabilities_in_scope() -> None:
    client = TestClient(
        build_app(
            scoped_tenant_id="tenant_scoped",
            scoped_tenant_role="tenant_reader",
            scoped_tenant_capabilities=("billing:exports:read",),
        )
    )
    scope = client.get("/control/tenant/billing/scope")

    assert scope.status_code == 200
    assert scope.json()["capabilities"] == ["billing:exports:read", "billing:read", "billing:scope:read"]


def test_tenant_billing_routes_require_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/control/tenant/billing/subscriptions?tenant_id=tenant_1")
    assert response.status_code == 503
    assert response.json()["detail"] == "Billing repository is not available"


def test_tenant_query_param_fallback_can_be_disabled() -> None:
    client = TestClient(build_app(tenant_query_param_fallback_enabled=False))
    response = client.get("/control/tenant/billing/subscriptions?tenant_id=tenant_1")
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant query parameter fallback is disabled; authenticated tenant scope is required"


def test_tenant_query_param_fallback_defaults_off_in_prod() -> None:
    client = TestClient(build_app(tenant_query_param_fallback_enabled=None, environment="prod"))
    response = client.get("/control/tenant/billing/subscriptions?tenant_id=tenant_1")
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant query parameter fallback is disabled; authenticated tenant scope is required"


def test_tenant_query_param_fallback_defaults_on_in_dev() -> None:
    client = TestClient(build_app(tenant_query_param_fallback_enabled=None, environment="dev"))
    response = client.get("/control/tenant/billing/subscriptions?tenant_id=tenant_1")
    assert response.status_code == 200


def test_tenant_billing_pagination_metadata() -> None:
    client = TestClient(build_app(scoped_tenant_id="tenant_scoped"))

    subscriptions = client.get("/control/tenant/billing/subscriptions?limit=1")
    reports = client.get("/control/tenant/billing/reports?limit=1&offset=1&format=json")
    invoices = client.get("/control/tenant/billing/invoices?limit=1&offset=1&format=json")
    usage_charges = client.get("/control/tenant/billing/usage-charges?limit=1&offset=1")
    history = client.get("/control/tenant/billing/history?limit=1&offset=1")

    assert subscriptions.status_code == 200
    assert subscriptions.json()["items"][0]["id"] == "subscription_1"
    assert subscriptions.json()["has_more"] is True
    assert subscriptions.json()["next_offset"] == 1

    assert reports.status_code == 200
    assert reports.json()["count"] == 1
    assert reports.json()["items"][0]["billing_period_id"] == "billing_period_2"
    assert reports.json()["has_more"] is False
    assert reports.json()["next_offset"] is None

    assert invoices.status_code == 200
    assert invoices.json()["count"] == 1
    assert invoices.json()["items"][0]["billing_period_id"] == "billing_period_2"
    assert invoices.json()["has_more"] is False
    assert invoices.json()["next_offset"] is None

    assert usage_charges.status_code == 200
    assert usage_charges.json()["count"] == 1
    assert usage_charges.json()["items"][0]["id"] == "charge_2"
    assert usage_charges.json()["has_more"] is True
    assert usage_charges.json()["next_offset"] == 2

    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["billing_period_id"] == "billing_period_2"
    assert history.json()["has_more"] is False
    assert history.json()["next_offset"] is None

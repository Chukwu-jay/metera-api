from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_billing_admin import router
from app.core.config import get_settings


class FakeCommercialEventRepository:
    def __init__(self) -> None:
        self.rows = []

    async def log_event(self, payload):
        self.rows.append(payload)

    async def recent_events(self, limit=20):
        return self.rows[:limit]

    async def list_events_for_tenant(self, *, tenant_id: str, limit: int = 50):
        return [row for row in self.rows if row.get("tenant_id") == tenant_id][:limit]


class FakeBillingRepository:
    def __init__(self) -> None:
        self.plans = [
            {
                "id": "plan_1",
                "code": "patron",
                "name": "Patron",
                "status": "active",
                "monthly_base_price_usd": 50.0,
            }
        ]
        self.subscriptions = []
        self.billing_periods = []
        self.invoices = []
        self.source_charge_types = {
            "daily_usage_rollups": "managed_spend",
            "request_ledger": "request_overage",
            "subscriptions": "base_fee",
            "manual": "manual_adjustment",
        }
        self.usage_charges = [
            {
                "id": "charge_1",
                "tenant_id": "tenant_1",
                "subscription_id": None,
                "source_table": "daily_usage_rollups",
                "source_ref": "2026-04-22:workspace_1",
                "charge_type": "managed_spend",
                "description": "Managed spend summary",
                "amount_usd": 3.5,
            }
        ]

    async def list_plans(self):
        return self.plans

    async def upsert_plan(self, **payload):
        self.plans.append(
            {
                "id": "plan_new",
                "code": payload["code"],
                "name": payload["name"],
                "status": "active",
                "monthly_base_price_usd": payload["monthly_base_price_usd"],
            }
        )
        return "plan_new"

    async def list_subscriptions(self, *, tenant_id=None):
        if tenant_id is None:
            return self.subscriptions
        return [row for row in self.subscriptions if row["tenant_id"] == tenant_id]

    async def create_subscription(self, **kwargs):
        self.subscriptions.append(
            {
                "id": "subscription_1",
                "tenant_id": kwargs["tenant_id"],
                "plan_id": kwargs["plan_id"],
                "status": kwargs["status"],
                "current_period_start": kwargs["current_period_start"],
                "current_period_end": kwargs["current_period_end"],
            }
        )
        return "subscription_1"

    async def update_subscription_status(self, *, subscription_id, status):
        subscription = next((row for row in self.subscriptions if row["id"] == subscription_id), None)
        if subscription is None:
            raise ValueError("subscription not found")
        if status not in {"trialing", "active", "past_due", "canceled"}:
            raise ValueError("invalid subscription status")
        subscription["status"] = status
        return subscription

    async def create_billing_period(self, *, tenant_id, subscription_id, period_start=None, period_end=None):
        if not self.subscriptions:
            raise ValueError("subscription not found")
        period = {
            "id": "billing_period_1",
            "tenant_id": tenant_id,
            "subscription_id": subscription_id,
            "period_start": period_start or datetime.fromisoformat("2026-04-01T00:00:00"),
            "period_end": period_end or datetime.fromisoformat("2026-05-01T00:00:00"),
            "status": "open",
            "request_count": 0,
            "upstream_cost_usd_total": 0.0,
            "realized_savings_usd_total": 0.0,
            "shadow_savings_usd_total": 0.0,
            "total_tokens_saved": 0,
            "closed_at": None,
        }
        self.billing_periods = [period]
        return "billing_period_1"

    async def list_billing_periods(self, *, tenant_id=None, subscription_id=None):
        rows = self.billing_periods
        if tenant_id is not None:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        if subscription_id is not None:
            rows = [row for row in rows if row["subscription_id"] == subscription_id]
        return rows

    async def summarize_billing_period(self, *, billing_period_id):
        period = next((row for row in self.billing_periods if row["id"] == billing_period_id), None)
        if period is None:
            raise ValueError("billing period not found")
        period["request_count"] = 12
        period["upstream_cost_usd_total"] = 60.0
        period["realized_savings_usd_total"] = 50.01
        period["shadow_savings_usd_total"] = 0.75
        period["total_tokens_saved"] = 1800
        if period["status"] == "open" and period["realized_savings_usd_total"] >= 50.0:
            period["status"] = "closing"
        return period

    async def update_billing_period_status(self, *, billing_period_id, status):
        period = next((row for row in self.billing_periods if row["id"] == billing_period_id), None)
        if period is None:
            raise ValueError("billing period not found")
        if status == "closed":
            reconciliation = await self.reconcile_billing_period(billing_period_id=billing_period_id)
            if not reconciliation["matches_realized_savings"]:
                raise ValueError("billing period reconciliation failed")
        period["status"] = status
        period["closed_at"] = datetime.fromisoformat("2026-05-01T00:00:00") if status == "closed" else None
        return period

    async def reconcile_billing_period(self, *, billing_period_id):
        period = next((row for row in self.billing_periods if row["id"] == billing_period_id), None)
        if period is None:
            raise ValueError("billing period not found")
        usage_total = sum(row["amount_usd"] for row in self.usage_charges if row.get("billing_period_id") == billing_period_id)
        return {
            "billing_period_id": billing_period_id,
            "usage_charges_total_usd": float(usage_total),
            "realized_savings_usd_total": float(period["realized_savings_usd_total"]),
            "matches_realized_savings": abs(float(usage_total) - float(period["realized_savings_usd_total"])) < 1e-9,
        }

    async def preview_billing_closeout(self, *, billing_period_id):
        period = next((row for row in self.billing_periods if row["id"] == billing_period_id), None)
        if period is None:
            raise ValueError("billing period not found")
        reconciliation = await self.reconcile_billing_period(billing_period_id=billing_period_id)
        return {
            "billing_period_id": billing_period_id,
            "status": period["status"],
            "request_count": int(period["request_count"]),
            "upstream_cost_usd_total": float(period["upstream_cost_usd_total"]),
            "realized_savings_usd_total": float(period["realized_savings_usd_total"]),
            "shadow_savings_usd_total": float(period["shadow_savings_usd_total"]),
            "total_tokens_saved": int(period.get("total_tokens_saved", 0)),
            "usage_charges_total_usd": float(reconciliation["usage_charges_total_usd"]),
            "matches_realized_savings": bool(reconciliation["matches_realized_savings"]),
            "recommended_action": "ready_to_close" if reconciliation["matches_realized_savings"] else "fix_blocking_issues_before_close",
            "blocking_issues": [] if reconciliation["matches_realized_savings"] else ["usage charges do not reconcile to realized savings"],
        }

    async def create_manual_adjustment(self, *, tenant_id, subscription_id, amount_usd, description, reason, target_billing_period_id=None):
        if target_billing_period_id is not None:
            period = next((row for row in self.billing_periods if row["id"] == target_billing_period_id), None)
            if period is None:
                raise ValueError("billing period not found")
            if period["status"] != "closed":
                raise ValueError("manual adjustments are only required for closed billing periods")
        self.usage_charges.append(
            {
                "id": "adjustment_1",
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "billing_period_id": target_billing_period_id,
                "source_table": "manual",
                "source_ref": "manual_adjustment:adjustment_1",
                "charge_type": "manual_adjustment",
                "description": description,
                "amount_usd": float(amount_usd),
            }
        )
        return {
            "adjustment_charge_id": "adjustment_1",
            "target_billing_period_id": target_billing_period_id,
            "charge_type": "manual_adjustment",
        }

    async def generate_billing_report(self, *, billing_period_id, export_format="json"):
        period = next((row for row in self.billing_periods if row["id"] == billing_period_id), None)
        if period is None:
            raise ValueError("billing period not found")
        usage_total = sum(row["amount_usd"] for row in self.usage_charges if row.get("billing_period_id") == billing_period_id)
        report = {
            "billing_period_id": billing_period_id,
            "tenant_id": period["tenant_id"],
            "subscription_id": period["subscription_id"],
            "status": period["status"],
            "period_start": period["period_start"].isoformat(),
            "period_end": period["period_end"].isoformat(),
            "request_count": int(period["request_count"]),
            "gross_cost_usd": float(period["upstream_cost_usd_total"]),
            "metera_savings_usd": float(period["realized_savings_usd_total"]),
            "shadow_savings_usd": float(period["shadow_savings_usd_total"]),
            "usage_charges_total_usd": float(usage_total),
            "total_tokens_saved": int(period.get("total_tokens_saved", 0)),
            "realized_savings_ratio": float(period["realized_savings_usd_total"]) / float(period["upstream_cost_usd_total"]),
            "matches_realized_savings": True,
            "blocking_issues": [],
            "summary_lines": [
                "Gross Cost: $60.00",
                "Metera Savings: $50.01",
                "Shadow Savings: $0.75",
                "Usage Charges Total: $50.01",
                "Intelligence Recovered (Tokens): 1,800",
                "Savings Ratio: 83.35%",
            ],
            "line_items": [
                "gross_cost_usd=60.00",
                "metera_savings_usd=50.01",
                "shadow_savings_usd=0.75",
                "usage_charges_total_usd=50.01",
                "total_tokens_saved=1800",
            ],
            "billing_window": {
                "period_start": period["period_start"].isoformat(),
                "period_end": period["period_end"].isoformat(),
                "closed_at": None,
            },
            "totals": {
                "gross_cost_usd": 60.0,
                "metera_savings_usd": 50.01,
                "shadow_savings_usd": 0.75,
                "usage_charges_total_usd": 50.01,
                "net_cost_avoided_usd": 50.01,
                "realized_savings_ratio": 0.8335,
                "total_tokens_saved": 1800.0,
            },
            "reconciliation": {
                "matches_realized_savings": True,
                "usage_charges_total_usd": 50.01,
                "realized_savings_usd_total": 50.01,
                "difference_usd": 0.0,
            },
            "narrative": [
                "Processed 12 requests in the billing window.",
                "Intelligence Recovered (Tokens) reached 1,800 across cache-served requests in this window.",
                "Reconciliation is clean for the current billing-period snapshot.",
            ],
            "export_content": '{\n  "billing_period_id": "billing_period_1",\n  "status": "closing",\n  "totals": {\n    "gross_cost_usd": 60.0\n  }\n}' if export_format == "json" else "Metera Billing Report\nBilling Period: billing_period_1\n\nStructured Totals:\ngross_cost_usd=60.00\nmetera_savings_usd=50.01\nshadow_savings_usd=0.75\nusage_charges_total_usd=50.01\ntotal_tokens_saved=1800",
            "export_filename": "billing_report_billing_period_1.json" if export_format == "json" else "billing_report_billing_period_1.txt",
            "format": export_format,
        }
        return report

    async def generate_invoice_stub(self, *, billing_period_id, export_format="json"):
        period = next((row for row in self.billing_periods if row["id"] == billing_period_id), None)
        if period is None:
            raise ValueError("billing period not found")
        invoice = {
            "id": "invoice_1",
            "tenant_id": period["tenant_id"],
            "billing_period_id": billing_period_id,
            "status": "draft",
            "subtotal_usd": float(period["upstream_cost_usd_total"]),
            "total_usd": 0.0,
            "gross_cost_usd": float(period["upstream_cost_usd_total"]),
            "metera_savings_usd": float(period["realized_savings_usd_total"]),
            "net_cost_avoided_usd": float(period["realized_savings_usd_total"]),
            "total_tokens_saved": int(period.get("total_tokens_saved", 0)),
            "realized_savings_ratio": float(period["realized_savings_usd_total"]) / float(period["upstream_cost_usd_total"]),
            "summary_lines": [
                "Gross Cost: $60.00",
                "Metera Savings: $50.01",
                "Net Cost Avoided: $50.01",
                "Intelligence Recovered (Tokens): 1,800",
                "Savings Ratio: 83.35%",
            ],
            "billing_window": {
                "period_start": period["period_start"].isoformat(),
                "period_end": period["period_end"].isoformat(),
                "closed_at": None,
            },
            "totals": {
                "gross_cost_usd": 60.0,
                "metera_savings_usd": 50.01,
                "net_cost_avoided_usd": 50.01,
                "realized_savings_ratio": 0.8335,
                "total_tokens_saved": 1800.0,
            },
            "narrative": [
                "Draft invoice stub generated from the current billing-period snapshot.",
                "Metera savings of $50.01 avoided equivalent upstream cost during this window.",
                "Intelligence Recovered (Tokens): 1,800 across cache-served requests during this billing window.",
            ],
            "proven_roi": {
                "gross_cost_usd": 60.0,
                "metera_savings_usd": 50.01,
                "net_cost_avoided_usd": 50.01,
                "realized_savings_ratio": 0.8335,
                "total_tokens_saved": 1800.0,
            },
            "format": export_format,
            "export_content": '{\n  "billing_period_id": "billing_period_1",\n  "totals": {\n    "gross_cost_usd": 60.0\n  }\n}' if export_format == "json" else "Metera Draft Invoice Stub\nBilling Period: billing_period_1\n\nStructured Totals:\ngross_cost_usd=60.00\nmetera_savings_usd=50.01\nnet_cost_avoided_usd=50.01\ntotal_tokens_saved=1800",
            "export_filename": "invoice_stub_billing_period_1.json" if export_format == "json" else "invoice_stub_billing_period_1.txt",
        }
        self.invoices = [invoice]
        return invoice

    async def _canonical_charge_type_for_source(self, source_table):
        return self.source_charge_types[source_table]

    async def list_usage_charges(self, *, tenant_id=None, limit=100):
        rows = self.usage_charges
        if tenant_id is not None:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        return rows[:limit]

    async def materialize_usage_charges_from_rollups(self, **kwargs):
        if kwargs.get("billing_period_id") == "billing_period_1":
            period = next((row for row in self.billing_periods if row["id"] == "billing_period_1"), None)
            if period and period["status"] in {"closing", "closed"}:
                raise ValueError("cannot attach usage charges to a closing or closed billing period")
        return 2

    async def materialize_usage_charges_from_ledger(self, **kwargs):
        if kwargs.get("billing_period_id") == "billing_period_1":
            period = next((row for row in self.billing_periods if row["id"] == "billing_period_1"), None)
            if period and period["status"] in {"closing", "closed"}:
                raise ValueError("cannot attach usage charges to a closing or closed billing period")
            charge_type = await self._canonical_charge_type_for_source("request_ledger")
            existing = next((row for row in self.usage_charges if row.get("source_table") == "request_ledger" and row.get("source_ref") == "req_threshold" and row.get("charge_type") == charge_type), None)
            if existing is None:
                self.usage_charges.append(
                    {
                        "id": "charge_threshold",
                        "tenant_id": kwargs["tenant_id"],
                        "subscription_id": kwargs.get("subscription_id"),
                        "billing_period_id": "billing_period_1",
                        "source_table": "request_ledger",
                        "source_ref": "req_threshold",
                        "charge_type": charge_type,
                        "description": "Threshold charge",
                        "amount_usd": 50.01,
                    }
                )
        return 4

    async def get_tenant_enforcement_state(self, *, tenant_id: str):
        subscription = next((row for row in self.subscriptions if row["tenant_id"] == tenant_id), None)
        period = next((row for row in self.billing_periods if row["tenant_id"] == tenant_id), None)
        subscription_status = subscription["status"] if subscription else None
        period_status = period["status"] if period else None
        realized = float(period.get("realized_savings_usd_total", 0.0) or 0.0) if period else 0.0
        blocked = bool(period and realized >= 50.0 and period_status in {"closing", "closed"} and subscription_status != "active")
        return {
            "tenant_id": tenant_id,
            "blocked": blocked,
            "reason": "service_suspended" if period_status == "closed" and blocked else ("patronage_required" if blocked else None),
            "threshold_usd": 50.0,
            "subscription_id": subscription.get("id") if subscription else None,
            "subscription_status": subscription_status,
            "billing_period_id": period.get("id") if period else None,
            "billing_period_status": period_status,
            "realized_savings_usd_total": realized,
        }


def build_app(with_repo: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.billing_repository = FakeBillingRepository() if with_repo else None
    app.state.commercial_event_repository = FakeCommercialEventRepository() if with_repo else None
    app.state.identity_repository = None
    app.state.policy_repository = None
    app.dependency_overrides[get_settings] = lambda: type(
        "S",
        (),
        {
            "admin_api_key": "secret",
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.9,
            "semantic_shadow_threshold": 0.8,
            "semantic_max_temperature": 0.2,
            "namespace_header": "x-metera-namespace",
        },
    )()
    return app


def test_admin_billing_prep_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    plans = client.get("/admin/control/billing/plans", headers=headers)
    create_plan = client.post(
        "/admin/control/billing/plans",
        headers=headers,
        json={
            "code": "builder",
            "name": "Builder",
            "monthly_base_price_usd": 20.0,
            "soft_cap_threshold_ratio": 0.8,
            "hard_cap_enabled": False,
            "metadata": {},
        },
    )
    create_subscription = client.post(
        "/admin/control/billing/subscriptions",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "plan_id": "plan_1",
            "status": "trialing",
            "current_period_start": "2026-04-01T00:00:00",
            "current_period_end": "2026-05-01T00:00:00",
            "trial_ends_at": "2026-04-15T00:00:00",
        },
    )
    create_period = client.post(
        "/admin/control/billing/periods",
        headers=headers,
        json={"tenant_id": "tenant_1", "subscription_id": "subscription_1"},
    )
    list_periods = client.get("/admin/control/billing/periods", headers=headers)
    materialize_ledger = client.post(
        "/admin/control/billing/materialize/ledger",
        headers=headers,
        json={"tenant_id": "tenant_1", "subscription_id": None, "billing_period_id": "billing_period_1", "rollup_date": None, "limit": 100},
    )
    summarize_period = client.post("/admin/control/billing/periods/billing_period_1/summarize", headers=headers)
    reconcile_period = client.get("/admin/control/billing/periods/billing_period_1/reconcile", headers=headers)
    closeout_preview = client.get("/admin/control/billing/periods/billing_period_1/closeout-preview", headers=headers)
    billing_report = client.get("/admin/control/billing/periods/billing_period_1/report?format=json", headers=headers)
    billing_report_text = client.get("/admin/control/billing/periods/billing_period_1/report?format=text", headers=headers)
    invoice_stub = client.post("/admin/control/billing/periods/billing_period_1/invoice-stub?format=json", headers=headers)
    invoice_stub_text = client.post("/admin/control/billing/periods/billing_period_1/invoice-stub?format=text", headers=headers)
    charges = client.get("/admin/control/billing/usage-charges", headers=headers)
    materialize_rollups = client.post(
        "/admin/control/billing/materialize/rollups",
        headers=headers,
        json={"tenant_id": "tenant_1", "subscription_id": None, "billing_period_id": "billing_period_1", "rollup_date": "2026-04-22", "limit": 100},
    )
    set_closing = client.post(
        "/admin/control/billing/periods/billing_period_1/status",
        headers=headers,
        json={"status": "closing"},
    )
    close_period = client.post("/admin/control/billing/periods/billing_period_1/close", headers=headers)
    create_adjustment = client.post(
        "/admin/control/billing/adjustments",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "subscription_id": "subscription_1",
            "amount_usd": 5.0,
            "description": "Late-arriving correction",
            "reason": "late_arrival",
            "target_billing_period_id": "billing_period_1",
        },
    )
    commercial_events = client.get("/admin/control/billing/commercial-events", headers=headers)
    scoped_commercial_events = client.get("/admin/control/billing/commercial-events?tenant_id=tenant_1", headers=headers)
    materialize_after_close = client.post(
        "/admin/control/billing/materialize/ledger",
        headers=headers,
        json={"tenant_id": "tenant_1", "subscription_id": None, "billing_period_id": "billing_period_1", "rollup_date": None, "limit": 100},
    )

    assert plans.status_code == 200
    assert plans.json()[0]["code"] == "patron"
    assert create_plan.status_code == 200
    assert create_plan.json()["code"] == "builder"
    assert create_subscription.status_code == 200
    assert create_subscription.json()["tenant_id"] == "tenant_1"
    assert create_period.status_code == 200
    assert create_period.json()["id"] == "billing_period_1"
    assert list_periods.status_code == 200
    assert list_periods.json()[0]["subscription_id"] == "subscription_1"
    assert materialize_ledger.status_code == 200
    assert materialize_ledger.json()["created_count"] == 4
    assert summarize_period.status_code == 200
    assert summarize_period.json()["request_count"] == 12
    assert summarize_period.json()["status"] == "closing"
    assert summarize_period.json()["realized_savings_usd_total"] == 50.01
    assert reconcile_period.status_code == 200
    assert reconcile_period.json()["matches_realized_savings"] is True
    assert closeout_preview.status_code == 200
    assert closeout_preview.json()["recommended_action"] == "ready_to_close"
    assert closeout_preview.json()["blocking_issues"] == []
    assert closeout_preview.json()["total_tokens_saved"] == 1800
    assert billing_report.status_code == 200
    assert billing_report.json()["billing_period_id"] == "billing_period_1"
    assert billing_report.json()["usage_charges_total_usd"] == 50.01
    assert billing_report.json()["total_tokens_saved"] == 1800
    assert billing_report.json()["matches_realized_savings"] is True
    assert billing_report.json()["export_filename"].endswith(".json")
    assert billing_report.json()["totals"]["gross_cost_usd"] == 60.0
    assert billing_report.json()["totals"]["total_tokens_saved"] == 1800.0
    assert billing_report.json()["reconciliation"]["difference_usd"] == 0.0
    assert len(billing_report.json()["narrative"]) >= 2
    assert '"status": "closing"' in billing_report.json()["export_content"]
    assert billing_report_text.status_code == 200
    assert billing_report_text.json()["export_filename"].endswith(".txt")
    assert "Metera Billing Report" in billing_report_text.json()["export_content"]
    assert "Structured Totals:" in billing_report_text.json()["export_content"]
    assert "Intelligence Recovered (Tokens): 1,800" in billing_report.json()["summary_lines"]
    assert "total_tokens_saved=1800" in billing_report_text.json()["export_content"]
    assert invoice_stub.status_code == 200
    assert invoice_stub.json()["status"] == "draft"
    assert invoice_stub.json()["gross_cost_usd"] == 60.0
    assert invoice_stub.json()["metera_savings_usd"] == 50.01
    assert invoice_stub.json()["net_cost_avoided_usd"] == 50.01
    assert invoice_stub.json()["total_tokens_saved"] == 1800
    assert invoice_stub.json()["realized_savings_ratio"] > 0.8
    assert len(invoice_stub.json()["summary_lines"]) == 5
    assert invoice_stub.json()["billing_window"]["period_start"] == "2026-04-01T00:00:00"
    assert invoice_stub.json()["totals"]["gross_cost_usd"] == 60.0
    assert invoice_stub.json()["totals"]["total_tokens_saved"] == 1800.0
    assert len(invoice_stub.json()["narrative"]) >= 2
    assert invoice_stub.json()["export_filename"].endswith(".json")
    assert '"billing_period_id": "billing_period_1"' in invoice_stub.json()["export_content"]
    assert invoice_stub_text.status_code == 200
    assert invoice_stub_text.json()["export_filename"].endswith(".txt")
    assert "Metera Draft Invoice Stub" in invoice_stub_text.json()["export_content"]
    assert "Structured Totals:" in invoice_stub_text.json()["export_content"]
    assert "Intelligence Recovered (Tokens): 1,800" in invoice_stub.json()["summary_lines"]
    assert "total_tokens_saved=1800" in invoice_stub_text.json()["export_content"]
    assert commercial_events.status_code == 200
    event_types = {row["event_type"] for row in commercial_events.json()}
    assert "patronage_required" in event_types
    assert "service_suspended" in event_types
    assert "billing_closeout_previewed" in event_types
    assert "billing_period_closed" in event_types
    assert "billing_adjustment_created" in event_types
    assert any(row["billing_period_id"] == "billing_period_1" for row in commercial_events.json())
    assert scoped_commercial_events.status_code == 200
    scoped_rows = scoped_commercial_events.json()
    assert scoped_rows
    assert all(row["tenant_id"] == "tenant_1" for row in scoped_rows)
    scoped_event_types = {row["event_type"] for row in scoped_rows}
    assert "patronage_required" in scoped_event_types
    assert "billing_period_closed" in scoped_event_types
    assert charges.status_code == 200
    assert charges.json()[0]["charge_type"] == "managed_spend"
    assert materialize_rollups.status_code == 400
    assert materialize_rollups.json()["detail"] == "cannot attach usage charges to a closing or closed billing period"
    assert set_closing.status_code == 200
    assert set_closing.json()["status"] == "closing"
    assert close_period.status_code == 200
    assert close_period.json()["status"] == "closed"
    assert create_adjustment.status_code == 200
    assert create_adjustment.json()["charge_type"] == "manual_adjustment"
    assert create_adjustment.json()["target_billing_period_id"] == "billing_period_1"
    assert materialize_after_close.status_code == 400
    assert materialize_after_close.json()["detail"] == "cannot attach usage charges to a closing or closed billing period"


def test_summarize_emits_patronage_required_but_not_service_suspended_before_close() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    client.post(
        "/admin/control/billing/subscriptions",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "plan_id": "plan_1",
            "status": "trialing",
            "current_period_start": "2026-04-01T00:00:00",
            "current_period_end": "2026-05-01T00:00:00",
            "trial_ends_at": None,
        },
    )
    client.post(
        "/admin/control/billing/periods",
        headers=headers,
        json={"tenant_id": "tenant_1", "subscription_id": "subscription_1"},
    )
    summarize = client.post(
        "/admin/control/billing/periods/billing_period_1/summarize",
        headers=headers,
        json={},
    )
    events = client.get(
        "/admin/control/billing/commercial-events?tenant_id=tenant_1&limit=10",
        headers=headers,
    )

    assert summarize.status_code == 200
    assert summarize.json()["status"] == "closing"
    event_types = {row["event_type"] for row in events.json()}
    assert "patronage_required" in event_types
    assert "service_suspended" not in event_types


def test_subscription_status_update_supports_recovery_activation() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    client.post(
        "/admin/control/billing/subscriptions",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "plan_id": "plan_1",
            "status": "trialing",
            "current_period_start": "2026-04-01T00:00:00",
            "current_period_end": "2026-05-01T00:00:00",
            "trial_ends_at": None,
        },
    )

    response = client.post(
        "/admin/control/billing/subscriptions/subscription_1/status",
        headers=headers,
        json={"status": "active"},
    )
    events = client.get(
        "/admin/control/billing/commercial-events?tenant_id=tenant_1&limit=10",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    event_types = {row["event_type"] for row in events.json()}
    assert "subscription_status_updated" in event_types


def test_admin_billing_routes_require_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/admin/control/billing/plans", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Billing repository is not available"


def test_adjustment_requires_closed_period() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    client.post(
        "/admin/control/billing/subscriptions",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "plan_id": "plan_1",
            "status": "trialing",
            "current_period_start": "2026-04-01T00:00:00",
            "current_period_end": "2026-05-01T00:00:00",
            "trial_ends_at": "2026-04-15T00:00:00",
        },
    )
    client.post(
        "/admin/control/billing/periods",
        headers=headers,
        json={"tenant_id": "tenant_1", "subscription_id": "subscription_1"},
    )

    response = client.post(
        "/admin/control/billing/adjustments",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "subscription_id": "subscription_1",
            "amount_usd": 2.0,
            "description": "Too early",
            "reason": "late_arrival",
            "target_billing_period_id": "billing_period_1",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "manual adjustments are only required for closed billing periods"

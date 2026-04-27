from app.controlplane.repositories.billing import PostgresBillingRepository


def test_invoice_text_rendering_is_customer_readable() -> None:
    repo = PostgresBillingRepository("postgresql://unused")
    payload = {
        "billing_period_id": "billing_period_1",
        "tenant_id": "tenant_1",
        "period_start": "2026-04-01T00:00:00Z",
        "period_end": "2026-05-01T00:00:00Z",
        "billing_window": {
            "period_start": "2026-04-01T00:00:00Z",
            "period_end": "2026-05-01T00:00:00Z",
        },
        "summary_lines": ["Gross Cost: $60.00", "Metera Savings: $50.01"],
        "totals": {
            "gross_cost_usd": 60.0,
            "metera_savings_usd": 50.01,
            "net_cost_avoided_usd": 50.01,
            "realized_savings_ratio": 0.8335,
            "total_tokens_saved": 1800.0,
        },
        "narrative": ["Metera avoided $50.01 of upstream model spend during this billing window."],
    }

    rendered = repo._render_invoice_text(payload)

    assert "Metera Invoice Preview" in rendered
    assert "Billing Totals" in rendered
    assert "Gross upstream cost: $60.00" in rendered
    assert "Savings ratio: 83.35%" in rendered
    assert "Total tokens saved: 1,800" in rendered
    assert "Structured Totals:" not in rendered
    assert "gross_cost_usd=" not in rendered



def test_billing_report_text_rendering_is_customer_readable() -> None:
    repo = PostgresBillingRepository("postgresql://unused")
    payload = {
        "billing_period_id": "billing_period_1",
        "tenant_id": "tenant_1",
        "subscription_id": "subscription_1",
        "status": "closing",
        "request_count": 12,
        "period_start": "2026-04-01T00:00:00Z",
        "period_end": "2026-05-01T00:00:00Z",
        "billing_window": {
            "period_start": "2026-04-01T00:00:00Z",
            "period_end": "2026-05-01T00:00:00Z",
        },
        "summary_lines": ["Gross Cost: $60.00", "Metera Savings: $50.01"],
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
        "line_items": ["Gross upstream spend offset by cached responses"],
        "narrative": ["Processed 12 requests in the billing window."],
        "blocking_issues": [],
    }

    rendered = repo._render_billing_report_text(payload)

    assert "Metera Billing Report" in rendered
    assert "Billing Totals" in rendered
    assert "Gross upstream cost: $60.00" in rendered
    assert "Usage charges total: $50.01" in rendered
    assert "Matches realized savings: True" in rendered
    assert "Charge Detail" in rendered
    assert "Structured Totals:" not in rendered
    assert "gross_cost_usd=" not in rendered

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.db import create_asyncpg_pool


def _normalize_patronage_threshold_usd(value: float) -> float:
    normalized = float(value or 0.0)
    return normalized if normalized > 0.0 else 50.0


def _format_usd_human(amount: float) -> str:
    value = float(amount or 0.0)
    abs_value = abs(value)
    if abs_value == 0.0:
        return "$0.00"
    if abs_value >= 0.01:
        return f"${value:.2f}"
    return f"${value:.6f}"


class PostgresBillingRepository:
    def __init__(self, dsn: str, *, patronage_required_threshold_usd: float = 50.0) -> None:
        self.dsn = dsn
        self.patronage_required_threshold_usd = _normalize_patronage_threshold_usd(patronage_required_threshold_usd)
        self._pool = None
        self._schema_ready = False

    async def warmup(self) -> None:
        await self._get_pool()
        await self.ensure_schema()

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    monthly_base_price_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    included_requests BIGINT NULL,
                    included_upstream_cost_usd DOUBLE PRECISION NULL,
                    included_realized_savings_usd DOUBLE PRECISION NULL,
                    soft_cap_threshold_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.8,
                    hard_cap_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL REFERENCES plans(id),
                    status TEXT NOT NULL,
                    trial_ends_at TIMESTAMPTZ NULL,
                    current_period_start TIMESTAMPTZ NOT NULL,
                    current_period_end TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_periods (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL REFERENCES subscriptions(id),
                    period_start TIMESTAMPTZ NOT NULL,
                    period_end TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    request_count BIGINT NOT NULL DEFAULT 0,
                    upstream_cost_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    realized_savings_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    shadow_savings_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    total_tokens_saved BIGINT NOT NULL DEFAULT 0,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    closed_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_charges (
                    id TEXT PRIMARY KEY,
                    billing_period_id TEXT NULL REFERENCES billing_periods(id),
                    tenant_id TEXT NOT NULL,
                    subscription_id TEXT NULL REFERENCES subscriptions(id),
                    request_id TEXT NULL,
                    rollup_date DATE NULL,
                    workspace_id TEXT NULL,
                    source_table TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    charge_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount_usd DOUBLE PRECISION NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    billing_period_id TEXT NOT NULL REFERENCES billing_periods(id),
                    external_invoice_ref TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    subtotal_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    total_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    invoice_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    issued_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant_status ON subscriptions (tenant_id, status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_billing_periods_tenant_status ON billing_periods (tenant_id, status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_billing_periods_subscription_range ON billing_periods (subscription_id, period_start, period_end)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_charges_tenant_created ON usage_charges (tenant_id, created_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_charges_source ON usage_charges (source_table, source_ref)")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_charges_source_charge_unique ON usage_charges (source_table, source_ref, charge_type)")
            await conn.execute("ALTER TABLE billing_periods ADD COLUMN IF NOT EXISTS total_tokens_saved BIGINT NOT NULL DEFAULT 0")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_charges_period_charge_type ON usage_charges (billing_period_id, charge_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_period_status ON invoices (billing_period_id, status)")
        self._schema_ready = True

    async def upsert_plan(
        self,
        *,
        code: str,
        name: str,
        monthly_base_price_usd: float,
        included_requests: int | None = None,
        included_upstream_cost_usd: float | None = None,
        included_realized_savings_usd: float | None = None,
        soft_cap_threshold_ratio: float = 0.8,
        hard_cap_enabled: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        existing = await pool.fetchrow("SELECT id FROM plans WHERE code = $1 LIMIT 1", code)
        plan_id = existing["id"] if existing else f"plan_{uuid4().hex}"
        await pool.execute(
            """
            INSERT INTO plans (
                id, code, name, status, monthly_base_price_usd, included_requests,
                included_upstream_cost_usd, included_realized_savings_usd, soft_cap_threshold_ratio,
                hard_cap_enabled, metadata, created_at, updated_at
            ) VALUES (
                $1, $2, $3, 'active', $4, $5, $6, $7, $8, $9, $10::jsonb, NOW(), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                code = EXCLUDED.code,
                name = EXCLUDED.name,
                monthly_base_price_usd = EXCLUDED.monthly_base_price_usd,
                included_requests = EXCLUDED.included_requests,
                included_upstream_cost_usd = EXCLUDED.included_upstream_cost_usd,
                included_realized_savings_usd = EXCLUDED.included_realized_savings_usd,
                soft_cap_threshold_ratio = EXCLUDED.soft_cap_threshold_ratio,
                hard_cap_enabled = EXCLUDED.hard_cap_enabled,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            plan_id,
            code,
            name,
            float(monthly_base_price_usd),
            included_requests,
            included_upstream_cost_usd,
            included_realized_savings_usd,
            float(soft_cap_threshold_ratio),
            bool(hard_cap_enabled),
            json.dumps(metadata or {}),
        )
        return plan_id

    async def create_subscription(
        self,
        *,
        tenant_id: str,
        plan_id: str,
        status: str,
        current_period_start: datetime,
        current_period_end: datetime,
        trial_ends_at: datetime | None = None,
    ) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        subscription_id = f"subscription_{uuid4().hex}"
        await pool.execute(
            """
            INSERT INTO subscriptions (
                id, tenant_id, plan_id, status, trial_ends_at, current_period_start, current_period_end, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            """,
            subscription_id,
            tenant_id,
            plan_id,
            status,
            trial_ends_at,
            current_period_start,
            current_period_end,
        )
        return subscription_id

    async def update_subscription_status(self, *, subscription_id: str, status: str) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        allowed_statuses = {"trialing", "active", "past_due", "canceled"}
        if status not in allowed_statuses:
            raise ValueError("invalid subscription status")
        row = await pool.fetchrow(
            """
            UPDATE subscriptions
            SET status = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            subscription_id,
            status,
        )
        if row is None:
            raise ValueError("subscription not found")
        return dict(row)

    async def _get_billing_period_row(self, *, billing_period_id: str) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        row = await pool.fetchrow("SELECT * FROM billing_periods WHERE id = $1 LIMIT 1", billing_period_id)
        if row is None:
            raise ValueError("billing period not found")
        return dict(row)

    async def create_billing_period(
        self,
        *,
        tenant_id: str,
        subscription_id: str,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        if period_start is None or period_end is None:
            subscription = await pool.fetchrow(
                "SELECT current_period_start, current_period_end FROM subscriptions WHERE id = $1 LIMIT 1",
                subscription_id,
            )
            if subscription is None:
                raise ValueError("subscription not found")
            period_start = period_start or subscription["current_period_start"]
            period_end = period_end or subscription["current_period_end"]
        existing = await pool.fetchrow(
            """
            SELECT id FROM billing_periods
            WHERE subscription_id = $1 AND period_start = $2 AND period_end = $3
            LIMIT 1
            """,
            subscription_id,
            period_start,
            period_end,
        )
        if existing is not None:
            return str(existing["id"])
        billing_period_id = f"billing_period_{uuid4().hex}"
        await pool.execute(
            """
            INSERT INTO billing_periods (
                id, tenant_id, subscription_id, period_start, period_end, status,
                request_count, upstream_cost_usd_total, realized_savings_usd_total, shadow_savings_usd_total,
                total_tokens_saved, metadata, closed_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, 'open', 0, 0.0, 0.0, 0.0, 0, '{}'::jsonb, NULL, NOW(), NOW())
            """,
            billing_period_id,
            tenant_id,
            subscription_id,
            period_start,
            period_end,
        )
        return billing_period_id

    async def summarize_billing_period(self, *, billing_period_id: str) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        period = await self._get_billing_period_row(billing_period_id=billing_period_id)
        if period["status"] == "closed":
            return period
        totals = await pool.fetchrow(
            """
            SELECT
                COUNT(*) AS request_count,
                COALESCE(SUM(estimated_upstream_cost_usd), 0.0) AS upstream_cost_usd_total,
                COALESCE(SUM(estimated_realized_savings_usd), 0.0) AS realized_savings_usd_total,
                COALESCE(SUM(estimated_shadow_savings_usd), 0.0) AS shadow_savings_usd_total,
                COALESCE(SUM(CASE WHEN estimated_realized_savings_usd > 0 THEN total_tokens ELSE 0 END), 0) AS total_tokens_saved
            FROM request_ledger
            WHERE tenant_id = $1
              AND observed_at >= $2
              AND observed_at < $3
            """,
            period["tenant_id"],
            period["period_start"],
            period["period_end"],
        )
        await pool.execute(
            """
            UPDATE billing_periods
            SET request_count = $2,
                upstream_cost_usd_total = $3,
                realized_savings_usd_total = $4,
                shadow_savings_usd_total = $5,
                total_tokens_saved = $6,
                updated_at = NOW()
            WHERE id = $1
            """,
            billing_period_id,
            int(totals["request_count"] or 0),
            float(totals["upstream_cost_usd_total"] or 0.0),
            float(totals["realized_savings_usd_total"] or 0.0),
            float(totals["shadow_savings_usd_total"] or 0.0),
            int(totals["total_tokens_saved"] or 0),
        )
        refreshed = dict(await pool.fetchrow("SELECT * FROM billing_periods WHERE id = $1 LIMIT 1", billing_period_id))
        if refreshed["status"] == "open" and float(refreshed["realized_savings_usd_total"] or 0.0) >= self.patronage_required_threshold_usd:
            refreshed = await self.update_billing_period_status(billing_period_id=billing_period_id, status="closing")
        return refreshed

    async def update_billing_period_status(self, *, billing_period_id: str, status: str) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        current = await self._get_billing_period_row(billing_period_id=billing_period_id)
        allowed_statuses = {"open", "closing", "closed"}
        if status not in allowed_statuses:
            raise ValueError("invalid billing period status")
        if current["status"] == "closed" and status != "closed":
            raise ValueError("closed billing period cannot be reopened")
        if status == "closed":
            reconciliation = await self.reconcile_billing_period(billing_period_id=billing_period_id)
            if not reconciliation["matches_realized_savings"]:
                raise ValueError("billing period reconciliation failed")
        closed_at = datetime.now(UTC) if status == "closed" else None
        result = await pool.fetchrow(
            """
            UPDATE billing_periods
            SET status = $2,
                closed_at = CASE WHEN $2 = 'closed' THEN $3::timestamptz ELSE NULL::timestamptz END,
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            billing_period_id,
            status,
            closed_at,
        )
        if result is None:
            raise ValueError("billing period not found")
        return dict(result)

    async def list_billing_periods(self, *, tenant_id: str | None = None, subscription_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        query = "SELECT * FROM billing_periods WHERE 1=1"
        params: list[Any] = []
        if tenant_id is not None:
            params.append(tenant_id)
            query += f" AND tenant_id = ${len(params)}"
        if subscription_id is not None:
            params.append(subscription_id)
            query += f" AND subscription_id = ${len(params)}"
        query += " ORDER BY period_start DESC, created_at DESC"
        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows]

    async def reconcile_billing_period(self, *, billing_period_id: str) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        period = await self._get_billing_period_row(billing_period_id=billing_period_id)
        totals = await pool.fetchrow(
            """
            SELECT COALESCE(SUM(amount_usd), 0.0) AS usage_charges_total_usd
            FROM usage_charges
            WHERE billing_period_id = $1
            """,
            billing_period_id,
        )
        usage_charges_total_usd = float(totals["usage_charges_total_usd"] or 0.0)
        realized_savings_usd_total = float(period["realized_savings_usd_total"] or 0.0)
        return {
            "billing_period_id": billing_period_id,
            "usage_charges_total_usd": usage_charges_total_usd,
            "realized_savings_usd_total": realized_savings_usd_total,
            "matches_realized_savings": abs(usage_charges_total_usd - realized_savings_usd_total) < 1e-9,
        }

    async def preview_billing_closeout(self, *, billing_period_id: str) -> dict[str, Any]:
        period = await self._get_billing_period_row(billing_period_id=billing_period_id)
        reconciliation = await self.reconcile_billing_period(billing_period_id=billing_period_id)
        blocking_issues: list[str] = []
        if not reconciliation["matches_realized_savings"]:
            blocking_issues.append("usage charges do not reconcile to realized savings")
        if period["status"] == "closed":
            recommended_action = "period_already_closed"
        elif blocking_issues:
            recommended_action = "fix_blocking_issues_before_close"
        elif period["status"] == "open":
            recommended_action = "summarize_or_move_to_closing"
        else:
            recommended_action = "ready_to_close"
        return {
            "billing_period_id": billing_period_id,
            "status": str(period["status"]),
            "request_count": int(period["request_count"]),
            "upstream_cost_usd_total": float(period["upstream_cost_usd_total"] or 0.0),
            "realized_savings_usd_total": float(period["realized_savings_usd_total"] or 0.0),
            "shadow_savings_usd_total": float(period["shadow_savings_usd_total"] or 0.0),
            "total_tokens_saved": int(period.get("total_tokens_saved") or 0),
            "usage_charges_total_usd": float(reconciliation["usage_charges_total_usd"]),
            "matches_realized_savings": bool(reconciliation["matches_realized_savings"]),
            "recommended_action": recommended_action,
            "blocking_issues": blocking_issues,
        }

    async def create_manual_adjustment(
        self,
        *,
        tenant_id: str,
        subscription_id: str | None,
        amount_usd: float,
        description: str,
        reason: str,
        target_billing_period_id: str | None = None,
    ) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        if target_billing_period_id is not None:
            period = await self._get_billing_period_row(billing_period_id=target_billing_period_id)
            if period["status"] != "closed":
                raise ValueError("manual adjustments are only required for closed billing periods")
        charge_type = await self._canonical_charge_type_for_source("manual")
        adjustment_charge_id = f"usage_charge_{uuid4().hex}"
        source_ref = f"manual_adjustment:{adjustment_charge_id}"
        await pool.execute(
            """
            INSERT INTO usage_charges (
                id, billing_period_id, tenant_id, subscription_id, request_id, rollup_date, workspace_id, source_table, source_ref,
                charge_type, description, amount_usd, metadata, created_at
            ) VALUES ($1, $2, $3, $4, NULL, NULL, NULL, 'manual', $5, $6, $7, $8, $9::jsonb, NOW())
            """,
            adjustment_charge_id,
            target_billing_period_id,
            tenant_id,
            subscription_id,
            source_ref,
            charge_type,
            description,
            float(amount_usd),
            json.dumps({"reason": reason, "late_arrival_adjustment": True}),
        )
        return {
            "adjustment_charge_id": adjustment_charge_id,
            "target_billing_period_id": target_billing_period_id,
            "charge_type": charge_type,
        }

    async def generate_billing_report(self, *, billing_period_id: str, export_format: str = "json") -> dict[str, Any]:
        await self.ensure_schema()
        period = await self._get_billing_period_row(billing_period_id=billing_period_id)
        reconciliation = await self.reconcile_billing_period(billing_period_id=billing_period_id)
        gross_cost_usd = float(period["upstream_cost_usd_total"] or 0.0)
        metera_savings_usd = float(period["realized_savings_usd_total"] or 0.0)
        shadow_savings_usd = float(period["shadow_savings_usd_total"] or 0.0)
        usage_charges_total_usd = float(reconciliation["usage_charges_total_usd"])
        total_tokens_saved = int(period.get("total_tokens_saved") or 0)
        realized_savings_ratio = (metera_savings_usd / gross_cost_usd) if gross_cost_usd > 0 else 0.0
        blocking_issues: list[str] = []
        if not reconciliation["matches_realized_savings"]:
            blocking_issues.append("usage charges do not reconcile to realized savings")
        line_items = [
            f"gross_cost_usd={_format_usd_human(gross_cost_usd)}",
            f"metera_savings_usd={_format_usd_human(metera_savings_usd)}",
            f"shadow_savings_usd={_format_usd_human(shadow_savings_usd)}",
            f"usage_charges_total_usd={_format_usd_human(usage_charges_total_usd)}",
            f"total_tokens_saved={total_tokens_saved}",
        ]
        narrative = [
            f"Processed {int(period['request_count'])} requests in the billing window.",
            f"Realized savings reached {_format_usd_human(metera_savings_usd)} against {_format_usd_human(gross_cost_usd)} of gross upstream cost.",
        ]
        if total_tokens_saved > 0:
            narrative.append(f"Intelligence Recovered (Tokens) reached {total_tokens_saved:,} across cache-served requests in this window.")
        if shadow_savings_usd > 0:
            narrative.append(f"Shadow savings opportunity measured {_format_usd_human(shadow_savings_usd)} beyond realized savings.")
        if blocking_issues:
            narrative.append("This report still has blocking reconciliation issues that should be resolved before final closeout.")
        else:
            narrative.append("Reconciliation is clean for the current billing-period snapshot.")
        billing_window = {
            "period_start": period["period_start"].isoformat(),
            "period_end": period["period_end"].isoformat(),
            "closed_at": period["closed_at"].isoformat() if period.get("closed_at") else None,
        }
        totals = {
            "gross_cost_usd": gross_cost_usd,
            "metera_savings_usd": metera_savings_usd,
            "shadow_savings_usd": shadow_savings_usd,
            "usage_charges_total_usd": usage_charges_total_usd,
            "net_cost_avoided_usd": metera_savings_usd,
            "realized_savings_ratio": realized_savings_ratio,
            "total_tokens_saved": float(total_tokens_saved),
        }
        reconciliation_summary = {
            "matches_realized_savings": bool(reconciliation["matches_realized_savings"]),
            "usage_charges_total_usd": usage_charges_total_usd,
            "realized_savings_usd_total": float(reconciliation["realized_savings_usd_total"]),
            "difference_usd": usage_charges_total_usd - float(reconciliation["realized_savings_usd_total"]),
        }
        report_payload = {
            "billing_period_id": billing_period_id,
            "tenant_id": period["tenant_id"],
            "subscription_id": period["subscription_id"],
            "status": period["status"],
            "period_start": period["period_start"].isoformat(),
            "period_end": period["period_end"].isoformat(),
            "request_count": int(period["request_count"]),
            "gross_cost_usd": gross_cost_usd,
            "metera_savings_usd": metera_savings_usd,
            "shadow_savings_usd": shadow_savings_usd,
            "usage_charges_total_usd": usage_charges_total_usd,
            "total_tokens_saved": total_tokens_saved,
            "realized_savings_ratio": realized_savings_ratio,
            "matches_realized_savings": bool(reconciliation["matches_realized_savings"]),
            "blocking_issues": blocking_issues,
            "summary_lines": [
                f"Gross Cost: {_format_usd_human(gross_cost_usd)}",
                f"Metera Savings: {_format_usd_human(metera_savings_usd)}",
                f"Shadow Savings: {_format_usd_human(shadow_savings_usd)}",
                f"Usage Charges Total: {_format_usd_human(usage_charges_total_usd)}",
                f"Intelligence Recovered (Tokens): {total_tokens_saved:,}",
                f"Savings Ratio: {realized_savings_ratio:.2%}",
            ],
            "line_items": line_items,
            "billing_window": billing_window,
            "totals": totals,
            "reconciliation": reconciliation_summary,
            "narrative": narrative,
            "format": export_format,
        }
        export_content = json.dumps(report_payload, indent=2) if export_format == "json" else self._render_billing_report_text(report_payload)
        export_extension = "json" if export_format == "json" else "txt"
        return {
            **report_payload,
            "export_content": export_content,
            "export_filename": f"billing_report_{billing_period_id}.{export_extension}",
        }

    async def list_invoices(self, *, tenant_id: str | None = None, billing_period_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        query = "SELECT * FROM invoices WHERE 1=1"
        params: list[Any] = []
        if tenant_id is not None:
            params.append(tenant_id)
            query += f" AND tenant_id = ${len(params)}"
        if billing_period_id is not None:
            params.append(billing_period_id)
            query += f" AND billing_period_id = ${len(params)}"
        query += " ORDER BY updated_at DESC, created_at DESC"
        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows]

    async def generate_invoice_stub(self, *, billing_period_id: str, export_format: str = "json") -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        period = await self._get_billing_period_row(billing_period_id=billing_period_id)
        gross_cost_usd = float(period["upstream_cost_usd_total"] or 0.0)
        metera_savings_usd = float(period["realized_savings_usd_total"] or 0.0)
        net_cost_avoided_usd = metera_savings_usd
        total_tokens_saved = int(period.get("total_tokens_saved") or 0)
        realized_savings_ratio = (metera_savings_usd / gross_cost_usd) if gross_cost_usd > 0 else 0.0
        billing_window = {
            "period_start": period["period_start"].isoformat(),
            "period_end": period["period_end"].isoformat(),
            "closed_at": period["closed_at"].isoformat() if period.get("closed_at") else None,
        }
        totals = {
            "gross_cost_usd": gross_cost_usd,
            "metera_savings_usd": metera_savings_usd,
            "net_cost_avoided_usd": net_cost_avoided_usd,
            "realized_savings_ratio": realized_savings_ratio,
            "total_tokens_saved": float(total_tokens_saved),
        }
        narrative = [
            "Customer-facing invoice preview generated from the current billing-period snapshot.",
            f"Metera avoided {_format_usd_human(metera_savings_usd)} of upstream model spend during this billing window.",
        ]
        if total_tokens_saved > 0:
            narrative.append(f"Intelligence Recovered (Tokens): {total_tokens_saved:,} across cache-served requests during this billing window.")
        invoice_payload = {
            "billing_period_id": billing_period_id,
            "tenant_id": period["tenant_id"],
            "gross_cost_usd": gross_cost_usd,
            "metera_savings_usd": metera_savings_usd,
            "net_cost_avoided_usd": net_cost_avoided_usd,
            "total_tokens_saved": total_tokens_saved,
            "realized_savings_ratio": realized_savings_ratio,
            "period_start": period["period_start"].isoformat(),
            "period_end": period["period_end"].isoformat(),
            "billing_window": billing_window,
            "totals": totals,
            "narrative": narrative,
            "format": export_format,
            "summary_lines": [
                f"Gross Cost: {_format_usd_human(gross_cost_usd)}",
                f"Metera Savings: {_format_usd_human(metera_savings_usd)}",
                f"Net Cost Avoided: {_format_usd_human(net_cost_avoided_usd)}",
                f"Intelligence Recovered (Tokens): {total_tokens_saved:,}",
                f"Savings Ratio: {realized_savings_ratio:.2%}",
            ],
            "proven_roi": {
                "gross_cost_usd": gross_cost_usd,
                "metera_savings_usd": metera_savings_usd,
                "net_cost_avoided_usd": net_cost_avoided_usd,
                "realized_savings_ratio": realized_savings_ratio,
                "total_tokens_saved": float(total_tokens_saved),
            },
        }
        existing = await pool.fetchrow("SELECT * FROM invoices WHERE billing_period_id = $1 LIMIT 1", billing_period_id)
        if existing is None:
            invoice_id = f"invoice_{uuid4().hex}"
            await pool.execute(
                """
                INSERT INTO invoices (
                    id, tenant_id, billing_period_id, external_invoice_ref, status, subtotal_usd, total_usd,
                    invoice_payload, issued_at, created_at, updated_at
                ) VALUES ($1, $2, $3, NULL, 'draft', $4, $5, $6::jsonb, NULL, NOW(), NOW())
                """,
                invoice_id,
                period["tenant_id"],
                billing_period_id,
                float(period["upstream_cost_usd_total"] or 0.0),
                0.0,
                json.dumps(invoice_payload),
            )
        else:
            invoice_id = existing["id"]
            await pool.execute(
                """
                UPDATE invoices
                SET subtotal_usd = $2,
                    total_usd = $3,
                    invoice_payload = $4::jsonb,
                    updated_at = NOW()
                WHERE id = $1
                """,
                invoice_id,
                float(period["upstream_cost_usd_total"] or 0.0),
                0.0,
                json.dumps(invoice_payload),
            )
        row = await pool.fetchrow("SELECT * FROM invoices WHERE id = $1 LIMIT 1", invoice_id)
        payload = json.loads(row["invoice_payload"]) if isinstance(row["invoice_payload"], str) else dict(row["invoice_payload"])
        export_content = json.dumps(payload, indent=2) if export_format == "json" else self._render_invoice_text(payload)
        export_extension = "json" if export_format == "json" else "txt"
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "billing_period_id": row["billing_period_id"],
            "status": row["status"],
            "subtotal_usd": float(row["subtotal_usd"]),
            "total_usd": float(row["total_usd"]),
            "gross_cost_usd": float(payload.get("gross_cost_usd", 0.0)),
            "metera_savings_usd": float(payload.get("metera_savings_usd", 0.0)),
            "net_cost_avoided_usd": float(payload.get("net_cost_avoided_usd", 0.0)),
            "total_tokens_saved": int(payload.get("total_tokens_saved", payload.get("totals", {}).get("total_tokens_saved", 0.0)) or 0),
            "realized_savings_ratio": float(payload.get("realized_savings_ratio", 0.0)),
            "summary_lines": list(payload.get("summary_lines", [])),
            "billing_window": dict(payload.get("billing_window", {})),
            "totals": dict(payload.get("totals", {})),
            "narrative": list(payload.get("narrative", [])),
            "proven_roi": dict(payload.get("proven_roi", {})),
            "format": str(payload.get("format", export_format)),
            "export_content": export_content,
            "export_filename": f"invoice_stub_{row['billing_period_id']}.{export_extension}",
        }

    async def _canonical_charge_type_for_source(self, source_table: str) -> str:
        mapping = {
            "daily_usage_rollups": "managed_spend",
            "request_ledger": "request_overage",
            "subscriptions": "base_fee",
            "manual": "manual_adjustment",
        }
        if source_table not in mapping:
            raise ValueError(f"unsupported billing source table: {source_table}")
        return mapping[source_table]

    async def materialize_usage_charges_from_rollups(
        self,
        *,
        tenant_id: str,
        subscription_id: str | None = None,
        rollup_date: str | None = None,
        billing_period_id: str | None = None,
    ) -> int:
        pool = await self._get_pool()
        await self.ensure_schema()
        if billing_period_id is not None:
            period = await self._get_billing_period_row(billing_period_id=billing_period_id)
            if period["status"] in {"closing", "closed"}:
                raise ValueError("cannot attach usage charges to a closing or closed billing period")
        query = """
            SELECT rollup_date, workspace_id, request_count, upstream_cost_usd_total, realized_savings_usd_total
            FROM daily_usage_rollups
            WHERE tenant_id = $1
        """
        params: list[Any] = [tenant_id]
        if rollup_date is not None:
            params.append(rollup_date)
            query += f" AND rollup_date = ${len(params)}"
        rows = await pool.fetch(query, *params)
        count = 0
        charge_type = await self._canonical_charge_type_for_source("daily_usage_rollups")
        for row in rows:
            source_ref = f"{row['rollup_date']}:{row.get('workspace_id') or 'unknown'}"
            existing = await pool.fetchrow(
                "SELECT id FROM usage_charges WHERE source_table = 'daily_usage_rollups' AND source_ref = $1 AND charge_type = $2 LIMIT 1",
                source_ref,
                charge_type,
            )
            if existing is not None:
                continue
            await pool.execute(
                """
                INSERT INTO usage_charges (
                    id, billing_period_id, tenant_id, subscription_id, request_id, rollup_date, workspace_id, source_table, source_ref,
                    charge_type, description, amount_usd, metadata, created_at
                ) VALUES ($1, $2, $3, $4, NULL, $5, $6, 'daily_usage_rollups', $7, $8, $9, $10, $11::jsonb, NOW())
                """,
                f"usage_charge_{uuid4().hex}",
                billing_period_id,
                tenant_id,
                subscription_id,
                row["rollup_date"],
                row.get("workspace_id"),
                source_ref,
                charge_type,
                f"Managed spend summary for {row['rollup_date']}",
                float(row["upstream_cost_usd_total"]),
                json.dumps(
                    {
                        "request_count": int(row["request_count"]),
                        "realized_savings_usd_total": float(row["realized_savings_usd_total"]),
                    }
                ),
            )
            count += 1
        return count

    async def materialize_usage_charges_from_ledger(
        self,
        *,
        tenant_id: str,
        subscription_id: str | None = None,
        billing_period_id: str | None = None,
        limit: int = 500,
    ) -> int:
        pool = await self._get_pool()
        await self.ensure_schema()
        period = None
        if billing_period_id is not None:
            period = await self._get_billing_period_row(billing_period_id=billing_period_id)
            if period["status"] in {"closing", "closed"}:
                raise ValueError("cannot attach usage charges to a closing or closed billing period")
        if period is None:
            rows = await pool.fetch(
                """
                SELECT request_id, observed_at, workspace_id, estimated_upstream_cost_usd, estimated_realized_savings_usd, model, cache_outcome
                FROM request_ledger
                WHERE tenant_id = $1
                ORDER BY observed_at DESC
                LIMIT $2
                """,
                tenant_id,
                limit,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT request_id, observed_at, workspace_id, estimated_upstream_cost_usd, estimated_realized_savings_usd, model, cache_outcome
                FROM request_ledger
                WHERE tenant_id = $1
                  AND observed_at >= $2
                  AND observed_at < $3
                ORDER BY observed_at DESC
                LIMIT $4
                """,
                tenant_id,
                period["period_start"],
                period["period_end"],
                limit,
            )
        count = 0
        charge_type = await self._canonical_charge_type_for_source("request_ledger")
        for row in rows:
            existing = await pool.fetchrow(
                "SELECT id FROM usage_charges WHERE source_table = 'request_ledger' AND source_ref = $1 AND charge_type = $2 LIMIT 1",
                row["request_id"],
                charge_type,
            )
            if existing is not None:
                continue
            await pool.execute(
                """
                INSERT INTO usage_charges (
                    id, billing_period_id, tenant_id, subscription_id, request_id, rollup_date, workspace_id, source_table, source_ref,
                    charge_type, description, amount_usd, metadata, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'request_ledger', $8, $9, $10, $11, $12::jsonb, NOW())
                """,
                f"usage_charge_{uuid4().hex}",
                billing_period_id,
                tenant_id,
                subscription_id,
                row["request_id"],
                row["observed_at"].date(),
                row.get("workspace_id"),
                row["request_id"],
                charge_type,
                f"Per-request realized savings record for {row['model']} ({row['cache_outcome']})",
                float(row["estimated_realized_savings_usd"]),
                json.dumps(
                    {
                        "estimated_upstream_cost_usd": float(row["estimated_upstream_cost_usd"]),
                        "estimated_realized_savings_usd": float(row["estimated_realized_savings_usd"]),
                        "model": row["model"],
                        "cache_outcome": row["cache_outcome"],
                    }
                ),
            )
            count += 1
        return count

    async def list_plans(self) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch("SELECT * FROM plans ORDER BY created_at DESC")
        return [dict(row) for row in rows]

    async def list_subscriptions(self, *, tenant_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        if tenant_id is None:
            rows = await pool.fetch("SELECT * FROM subscriptions ORDER BY created_at DESC")
        else:
            rows = await pool.fetch("SELECT * FROM subscriptions WHERE tenant_id = $1 ORDER BY created_at DESC", tenant_id)
        return [dict(row) for row in rows]

    async def list_usage_charges(self, *, tenant_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        if tenant_id is None:
            rows = await pool.fetch("SELECT * FROM usage_charges ORDER BY created_at DESC LIMIT $1", limit)
        else:
            rows = await pool.fetch("SELECT * FROM usage_charges WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2", tenant_id, limit)
        return [dict(row) for row in rows]

    async def get_tenant_enforcement_state(self, *, tenant_id: str) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()
        subscription = await pool.fetchrow(
            """
            SELECT * FROM subscriptions
            WHERE tenant_id = $1
            ORDER BY current_period_end DESC, created_at DESC
            LIMIT 1
            """,
            tenant_id,
        )
        period = await pool.fetchrow(
            """
            SELECT * FROM billing_periods
            WHERE tenant_id = $1
            ORDER BY
                CASE WHEN status IN ('open', 'closing') THEN 0 ELSE 1 END,
                period_end DESC,
                created_at DESC
            LIMIT 1
            """,
            tenant_id,
        )
        subscription_dict = dict(subscription) if subscription is not None else None
        period_dict = dict(period) if period is not None else None
        subscription_status = str(subscription_dict.get("status")) if subscription_dict is not None else None
        period_status = str(period_dict.get("status")) if period_dict is not None else None
        is_paid_subscription = subscription_status == "active"
        threshold_reached = float(period_dict.get("realized_savings_usd_total", 0.0) or 0.0) >= self.patronage_required_threshold_usd if period_dict else False
        blocked = bool(period_dict and threshold_reached and period_status in {"closing", "closed"} and not is_paid_subscription)
        if not blocked:
            reason = None
        elif period_status == "closed":
            reason = "service_suspended"
        else:
            reason = "patronage_required"
        return {
            "tenant_id": tenant_id,
            "blocked": blocked,
            "reason": reason,
            "threshold_usd": self.patronage_required_threshold_usd,
            "subscription_id": subscription_dict.get("id") if subscription_dict else None,
            "subscription_status": subscription_status,
            "billing_period_id": period_dict.get("id") if period_dict else None,
            "billing_period_status": period_status,
            "realized_savings_usd_total": float(period_dict.get("realized_savings_usd_total", 0.0) or 0.0) if period_dict else 0.0,
            "period_start": period_dict.get("period_start") if period_dict else None,
            "period_end": period_dict.get("period_end") if period_dict else None,
        }

    def _render_invoice_text(self, payload: dict[str, Any]) -> str:
        billing_window = payload.get("billing_window", {}) or {}
        totals = payload.get("totals", {}) or {}
        lines = [
            "Metera Invoice Preview",
            f"Billing Period: {payload.get('billing_period_id')}",
            f"Tenant: {payload.get('tenant_id')}",
            f"Period Start: {billing_window.get('period_start') or payload.get('period_start')}",
            f"Period End: {billing_window.get('period_end') or payload.get('period_end')}",
            "",
            "Summary",
        ]
        lines.extend(f"- {line}" for line in payload.get("summary_lines", []))
        if totals:
            lines.append("")
            lines.append("Billing Totals")
            lines.extend(
                [
                    f"- Gross upstream cost: {_format_usd_human(float(totals.get('gross_cost_usd', 0.0)))}",
                    f"- Metera savings: {_format_usd_human(float(totals.get('metera_savings_usd', 0.0)))}",
                    f"- Net cost avoided: {_format_usd_human(float(totals.get('net_cost_avoided_usd', 0.0)))}",
                    f"- Savings ratio: {float(totals.get('realized_savings_ratio', 0.0)):.2%}",
                    f"- Total tokens saved: {int(totals.get('total_tokens_saved', 0.0) or 0):,}",
                ]
            )
        if payload.get("narrative"):
            lines.append("")
            lines.append("Notes")
            lines.extend(f"- {line}" for line in payload.get("narrative", []))
        return "\n".join(lines)

    def _render_billing_report_text(self, payload: dict[str, Any]) -> str:
        billing_window = payload.get("billing_window", {}) or {}
        totals = payload.get("totals", {}) or {}
        reconciliation = payload.get("reconciliation", {}) or {}
        lines = [
            "Metera Billing Report",
            f"Billing Period: {payload.get('billing_period_id')}",
            f"Tenant: {payload.get('tenant_id')}",
            f"Subscription: {payload.get('subscription_id')}",
            f"Status: {payload.get('status')}",
            f"Period Start: {billing_window.get('period_start') or payload.get('period_start')}",
            f"Period End: {billing_window.get('period_end') or payload.get('period_end')}",
            f"Request Count: {payload.get('request_count')}",
            "",
            "Summary",
        ]
        lines.extend(f"- {line}" for line in payload.get("summary_lines", []))
        if totals:
            lines.append("")
            lines.append("Billing Totals")
            lines.extend(
                [
                    f"- Gross upstream cost: {_format_usd_human(float(totals.get('gross_cost_usd', 0.0)))}",
                    f"- Metera savings: {_format_usd_human(float(totals.get('metera_savings_usd', 0.0)))}",
                    f"- Additional shadow opportunity: {_format_usd_human(float(totals.get('shadow_savings_usd', 0.0)))}",
                    f"- Usage charges total: {_format_usd_human(float(totals.get('usage_charges_total_usd', 0.0)))}",
                    f"- Savings ratio: {float(totals.get('realized_savings_ratio', 0.0)):.2%}",
                    f"- Total tokens saved: {int(totals.get('total_tokens_saved', 0.0) or 0):,}",
                ]
            )
        if reconciliation:
            lines.append("")
            lines.append("Reconciliation")
            lines.extend(
                [
                    f"- Matches realized savings: {bool(reconciliation.get('matches_realized_savings', False))}",
                    f"- Difference: {_format_usd_human(float(reconciliation.get('difference_usd', 0.0)))}",
                ]
            )
        if payload.get("line_items"):
            lines.append("")
            lines.append("Charge Detail")
            lines.extend(f"- {item}" for item in payload.get("line_items", []))
        if payload.get("narrative"):
            lines.append("")
            lines.append("Notes")
            lines.extend(f"- {line}" for line in payload.get("narrative", []))
        if payload.get("blocking_issues"):
            lines.append("")
            lines.append("Blocking Issues")
            lines.extend(f"- {issue}" for issue in payload.get("blocking_issues", []))
        return "\n".join(lines)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await create_asyncpg_pool(self.dsn, component="billing_repository")
        return self._pool

from __future__ import annotations

from typing import Any

from app.core.db import create_asyncpg_pool


class PostgresRollupRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
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
                CREATE TABLE IF NOT EXISTS daily_usage_rollups (
                    id BIGSERIAL PRIMARY KEY,
                    rollup_date DATE NOT NULL,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    request_count BIGINT NOT NULL DEFAULT 0,
                    exact_hit_count BIGINT NOT NULL DEFAULT 0,
                    semantic_hit_count BIGINT NOT NULL DEFAULT 0,
                    miss_count BIGINT NOT NULL DEFAULT 0,
                    upstream_cost_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    realized_savings_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    shadow_savings_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (rollup_date, tenant_id, workspace_id)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_namespace_rollups (
                    id BIGSERIAL PRIMARY KEY,
                    rollup_date DATE NOT NULL,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    namespace TEXT NOT NULL,
                    request_count BIGINT NOT NULL DEFAULT 0,
                    exact_hit_count BIGINT NOT NULL DEFAULT 0,
                    semantic_hit_count BIGINT NOT NULL DEFAULT 0,
                    miss_count BIGINT NOT NULL DEFAULT 0,
                    shadow_alert_count BIGINT NOT NULL DEFAULT 0,
                    visual_request_count BIGINT NOT NULL DEFAULT 0,
                    agentic_request_count BIGINT NOT NULL DEFAULT 0,
                    identity_sensitive_request_count BIGINT NOT NULL DEFAULT 0,
                    upstream_cost_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    realized_savings_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    shadow_savings_usd_total DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute("ALTER TABLE daily_namespace_rollups DROP CONSTRAINT IF EXISTS daily_namespace_rollups_rollup_date_workspace_id_namespace_key")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_namespace_rollups_scope_unique ON daily_namespace_rollups (rollup_date, tenant_id, workspace_id, namespace)")
        self._schema_ready = True

    async def rebuild_daily_usage_rollups(self) -> int:
        pool = await self._get_pool()
        await self.ensure_schema()
        result = await pool.execute(
            """
            INSERT INTO daily_usage_rollups (
                rollup_date, tenant_id, workspace_id, request_count, exact_hit_count, semantic_hit_count,
                miss_count, upstream_cost_usd_total, realized_savings_usd_total, shadow_savings_usd_total, created_at, updated_at
            )
            SELECT
                DATE(observed_at) AS rollup_date,
                tenant_id,
                workspace_id,
                COUNT(*) AS request_count,
                COUNT(*) FILTER (WHERE cache_outcome = 'exact_hit') AS exact_hit_count,
                COUNT(*) FILTER (WHERE cache_outcome = 'semantic_hit') AS semantic_hit_count,
                COUNT(*) FILTER (WHERE cache_outcome = 'miss') AS miss_count,
                COALESCE(SUM(estimated_upstream_cost_usd), 0.0) AS upstream_cost_usd_total,
                COALESCE(SUM(estimated_realized_savings_usd), 0.0) AS realized_savings_usd_total,
                COALESCE(SUM(estimated_shadow_savings_usd), 0.0) AS shadow_savings_usd_total,
                NOW(),
                NOW()
            FROM request_ledger
            GROUP BY DATE(observed_at), tenant_id, workspace_id
            ON CONFLICT (rollup_date, tenant_id, workspace_id)
            DO UPDATE SET
                request_count = EXCLUDED.request_count,
                exact_hit_count = EXCLUDED.exact_hit_count,
                semantic_hit_count = EXCLUDED.semantic_hit_count,
                miss_count = EXCLUDED.miss_count,
                upstream_cost_usd_total = EXCLUDED.upstream_cost_usd_total,
                realized_savings_usd_total = EXCLUDED.realized_savings_usd_total,
                shadow_savings_usd_total = EXCLUDED.shadow_savings_usd_total,
                updated_at = NOW()
            """
        )
        return _extract_affected_rows(result)

    async def rebuild_daily_namespace_rollups(self) -> int:
        pool = await self._get_pool()
        await self.ensure_schema()
        result = await pool.execute(
            """
            WITH risk_counts AS (
                SELECT DATE(created_at) AS rollup_date, tenant_id, workspace_id, namespace, COUNT(*) AS shadow_alert_count
                FROM risk_events
                WHERE event_type = 'shadow_regression_alert'
                GROUP BY DATE(created_at), tenant_id, workspace_id, namespace
            )
            INSERT INTO daily_namespace_rollups (
                rollup_date, tenant_id, workspace_id, namespace, request_count, exact_hit_count, semantic_hit_count,
                miss_count, shadow_alert_count, visual_request_count, agentic_request_count, identity_sensitive_request_count,
                upstream_cost_usd_total, realized_savings_usd_total, shadow_savings_usd_total, created_at, updated_at
            )
            SELECT
                DATE(rl.observed_at) AS rollup_date,
                rl.tenant_id,
                rl.workspace_id,
                rl.namespace,
                COUNT(*) AS request_count,
                COUNT(*) FILTER (WHERE rl.cache_outcome = 'exact_hit') AS exact_hit_count,
                COUNT(*) FILTER (WHERE rl.cache_outcome = 'semantic_hit') AS semantic_hit_count,
                COUNT(*) FILTER (WHERE rl.cache_outcome = 'miss') AS miss_count,
                COALESCE(MAX(rc.shadow_alert_count), 0) AS shadow_alert_count,
                COUNT(*) FILTER (WHERE rl.has_visual_context) AS visual_request_count,
                COUNT(*) FILTER (WHERE rl.is_agentic) AS agentic_request_count,
                COUNT(*) FILTER (WHERE rl.identity_sensitive) AS identity_sensitive_request_count,
                COALESCE(SUM(rl.estimated_upstream_cost_usd), 0.0) AS upstream_cost_usd_total,
                COALESCE(SUM(rl.estimated_realized_savings_usd), 0.0) AS realized_savings_usd_total,
                COALESCE(SUM(rl.estimated_shadow_savings_usd), 0.0) AS shadow_savings_usd_total,
                NOW(),
                NOW()
            FROM request_ledger rl
            LEFT JOIN risk_counts rc
              ON rc.rollup_date = DATE(rl.observed_at)
             AND rc.tenant_id IS NOT DISTINCT FROM rl.tenant_id
             AND rc.workspace_id IS NOT DISTINCT FROM rl.workspace_id
             AND rc.namespace = rl.namespace
            GROUP BY DATE(rl.observed_at), rl.tenant_id, rl.workspace_id, rl.namespace
            ON CONFLICT (rollup_date, tenant_id, workspace_id, namespace)
            DO UPDATE SET
                request_count = EXCLUDED.request_count,
                exact_hit_count = EXCLUDED.exact_hit_count,
                semantic_hit_count = EXCLUDED.semantic_hit_count,
                miss_count = EXCLUDED.miss_count,
                shadow_alert_count = EXCLUDED.shadow_alert_count,
                visual_request_count = EXCLUDED.visual_request_count,
                agentic_request_count = EXCLUDED.agentic_request_count,
                identity_sensitive_request_count = EXCLUDED.identity_sensitive_request_count,
                upstream_cost_usd_total = EXCLUDED.upstream_cost_usd_total,
                realized_savings_usd_total = EXCLUDED.realized_savings_usd_total,
                shadow_savings_usd_total = EXCLUDED.shadow_savings_usd_total,
                updated_at = NOW()
            """
        )
        return _extract_affected_rows(result)

    async def list_daily_usage_rollups(
        self,
        *,
        limit: int = 100,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        rollup_date: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        query = "SELECT * FROM daily_usage_rollups WHERE 1=1"
        params: list[Any] = []
        if tenant_id is not None:
            params.append(tenant_id)
            query += f" AND tenant_id = ${len(params)}"
        if workspace_id is not None:
            params.append(workspace_id)
            query += f" AND workspace_id = ${len(params)}"
        if rollup_date is not None:
            params.append(rollup_date)
            query += f" AND rollup_date = ${len(params)}"
        params.append(limit)
        query += f" ORDER BY rollup_date DESC, updated_at DESC LIMIT ${len(params)}"
        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows]

    async def list_daily_namespace_rollups(
        self,
        *,
        limit: int = 100,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        namespace: str | None = None,
        rollup_date: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        query = "SELECT * FROM daily_namespace_rollups WHERE 1=1"
        params: list[Any] = []
        if tenant_id is not None:
            params.append(tenant_id)
            query += f" AND tenant_id = ${len(params)}"
        if workspace_id is not None:
            params.append(workspace_id)
            query += f" AND workspace_id = ${len(params)}"
        if namespace is not None:
            params.append(namespace)
            query += f" AND namespace = ${len(params)}"
        if rollup_date is not None:
            params.append(rollup_date)
            query += f" AND rollup_date = ${len(params)}"
        params.append(limit)
        query += f" ORDER BY rollup_date DESC, updated_at DESC LIMIT ${len(params)}"
        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await create_asyncpg_pool(self.dsn, component="rollup_repository")
        return self._pool


def _extract_affected_rows(status: str) -> int:
    parts = status.split()
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0

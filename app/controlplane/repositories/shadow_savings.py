from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import create_asyncpg_pool


class PostgresShadowSavingsRepository:
    def __init__(self, dsn: str, *, table_name: str = "shadow_savings_ledger") -> None:
        self.dsn = dsn
        self.table_name = table_name
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
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    namespace TEXT NOT NULL,
                    similarity_score DOUBLE PRECISION NOT NULL,
                    live_threshold DOUBLE PRECISION NOT NULL,
                    shadow_threshold DOUBLE PRECISION NOT NULL,
                    calculated_savings_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tenant_created ON {self.table_name} (tenant_id, created_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_namespace_created ON {self.table_name} (namespace, created_at DESC)")
        self._schema_ready = True

    async def log_shadow_savings(self, payload: dict[str, Any]) -> None:
        pool = await self._get_pool()
        await self.ensure_schema()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                request_id, tenant_id, workspace_id, namespace, similarity_score, live_threshold,
                shadow_threshold, calculated_savings_usd, payload, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
            """,
            payload["request_id"],
            payload.get("tenant_id"),
            payload.get("workspace_id"),
            payload["namespace"],
            float(payload["similarity_score"]),
            float(payload["live_threshold"]),
            float(payload["shadow_threshold"]),
            float(payload.get("calculated_savings_usd", 0.0) or 0.0),
            json.dumps(payload.get("payload") or {}),
            payload.get("created_at") or datetime.now(UTC),
        )

    async def recent_entries(self, *, limit: int = 50) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch(
            f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await create_asyncpg_pool(self.dsn, component="shadow_savings_repository")
        return self._pool

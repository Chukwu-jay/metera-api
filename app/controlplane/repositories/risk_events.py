from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import create_asyncpg_pool


class PostgresRiskEventRepository:
    def __init__(self, dsn: str, *, table_name: str = "risk_events") -> None:
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
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    reason TEXT NULL,
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tenant_created ON {self.table_name} (tenant_id, created_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_namespace_created ON {self.table_name} (namespace, created_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_event_type_created ON {self.table_name} (event_type, created_at DESC)")
        self._schema_ready = True

    async def log_event(self, payload: dict[str, Any]) -> None:
        pool = await self._get_pool()
        await self.ensure_schema()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                request_id, tenant_id, workspace_id, namespace, event_type, severity, reason, payload, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
            """,
            payload["request_id"],
            payload.get("tenant_id"),
            payload.get("workspace_id"),
            payload["namespace"],
            payload["event_type"],
            payload["severity"],
            payload.get("reason"),
            json.dumps(payload.get("payload") or {}),
            payload.get("created_at") or datetime.now(UTC),
        )

    async def recent_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
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
            self._pool = await create_asyncpg_pool(self.dsn, component="risk_event_repository")
        return self._pool

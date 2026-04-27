from __future__ import annotations

import json
from datetime import UTC, datetime
from collections.abc import Sequence
from typing import Any

from app.core.db import create_asyncpg_pool


class PostgresCommercialEventRepository:
    def __init__(self, dsn: str, *, table_name: str = "commercial_events") -> None:
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
                    event_id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    subscription_id TEXT NULL,
                    billing_period_id TEXT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NULL,
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tenant_created ON {self.table_name} (tenant_id, created_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_period_created ON {self.table_name} (billing_period_id, created_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type_created ON {self.table_name} (event_type, created_at DESC)")
        self._schema_ready = True

    async def log_event(self, payload: dict[str, Any]) -> None:
        pool = await self._get_pool()
        await self.ensure_schema()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                event_id, tenant_id, workspace_id, subscription_id, billing_period_id,
                event_type, status, reason, payload, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
            ON CONFLICT (event_id) DO NOTHING
            """,
            payload["event_id"],
            payload.get("tenant_id"),
            payload.get("workspace_id"),
            payload.get("subscription_id"),
            payload.get("billing_period_id"),
            payload["event_type"],
            payload["status"],
            payload.get("reason"),
            json.dumps(payload.get("payload") or {}),
            payload.get("created_at") or datetime.now(UTC),
        )

    async def recent_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch(f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT $1", limit)
        return [dict(row) for row in rows]

    async def list_events_for_tenant(self, *, tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch(
            f"SELECT * FROM {self.table_name} WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2",
            tenant_id,
            limit,
        )
        return [dict(row) for row in rows]

    async def latest_event_for_tenant(
        self,
        *,
        tenant_id: str,
        event_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        pool = await self._get_pool()
        await self.ensure_schema()
        query = f"SELECT * FROM {self.table_name} WHERE tenant_id = $1"
        params: list[Any] = [tenant_id]
        if event_types:
            params.append(list(event_types))
            query += f" AND event_type = ANY(${len(params)}::text[])"
        if statuses:
            params.append(list(statuses))
            query += f" AND status = ANY(${len(params)}::text[])"
        query += " ORDER BY created_at DESC, id DESC LIMIT 1"
        row = await pool.fetchrow(query, *params)
        return dict(row) if row is not None else None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await create_asyncpg_pool(self.dsn, component="commercial_event_repository")
        return self._pool

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import create_asyncpg_pool


class PostgresRequestEventRepository:
    def __init__(self, dsn: str, *, table_name: str = "request_events") -> None:
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
                    request_id TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    api_key_id TEXT NULL,
                    namespace TEXT NOT NULL,
                    request_path TEXT NOT NULL,
                    model TEXT NOT NULL,
                    cache_outcome TEXT NOT NULL,
                    semantic_bypass_reason TEXT NULL,
                    policy_mode TEXT NULL,
                    request_stream BOOLEAN NOT NULL DEFAULT FALSE,
                    estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    estimated_savings_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    timings_ms JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tenant_workspace_created ON {self.table_name} (tenant_id, workspace_id, created_at DESC)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_namespace_created ON {self.table_name} (namespace, created_at DESC)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_cache_outcome_created ON {self.table_name} (cache_outcome, created_at DESC)"
            )
        self._schema_ready = True

    async def log_event(self, payload: dict[str, Any]) -> None:
        pool = await self._get_pool()
        await self.ensure_schema()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                request_id,
                tenant_id,
                workspace_id,
                api_key_id,
                namespace,
                request_path,
                model,
                cache_outcome,
                semantic_bypass_reason,
                policy_mode,
                request_stream,
                estimated_cost_usd,
                estimated_savings_usd,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                timings_ms,
                metadata,
                created_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17::jsonb, $18::jsonb, $19
            )
            ON CONFLICT (request_id) DO NOTHING
            """,
            payload["request_id"],
            payload.get("tenant_id"),
            payload.get("workspace_id"),
            payload.get("api_key_id"),
            payload["namespace"],
            payload.get("request_path", "/v1/chat/completions"),
            payload["model"],
            payload["cache_outcome"],
            payload.get("semantic_bypass_reason"),
            payload.get("policy_mode"),
            bool(payload.get("request_stream", False)),
            float(payload.get("estimated_cost_usd", 0.0) or 0.0),
            float(payload.get("estimated_savings_usd", 0.0) or 0.0),
            int(payload.get("prompt_tokens", 0) or 0),
            int(payload.get("completion_tokens", 0) or 0),
            int(payload.get("total_tokens", 0) or 0),
            json.dumps(payload.get("timings_ms") or {}),
            json.dumps(payload.get("metadata") or {}),
            payload.get("created_at") or datetime.now(UTC),
        )

    async def recent_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch(
            f"""
            SELECT request_id, tenant_id, workspace_id, api_key_id, namespace, request_path, model, cache_outcome,
                   semantic_bypass_reason, policy_mode, request_stream, estimated_cost_usd, estimated_savings_usd,
                   prompt_tokens, completion_tokens, total_tokens, timings_ms, metadata, created_at
            FROM {self.table_name}
            ORDER BY created_at DESC
            LIMIT $1
            """,
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
            self._pool = await create_asyncpg_pool(self.dsn, component="request_event_repository")
        return self._pool

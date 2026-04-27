from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import create_asyncpg_pool


class PostgresRequestLedgerRepository:
    def __init__(self, dsn: str, *, table_name: str = "request_ledger") -> None:
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
                    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    environment_id TEXT NULL,
                    api_key_id TEXT NULL,
                    namespace TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NULL,
                    cache_outcome TEXT NOT NULL,
                    semantic_bypass_reason TEXT NULL,
                    effective_policy_version_id TEXT NULL,
                    effective_policy_mode TEXT NULL,
                    has_visual_context BOOLEAN NOT NULL DEFAULT FALSE,
                    has_dom_context BOOLEAN NOT NULL DEFAULT FALSE,
                    is_agentic BOOLEAN NOT NULL DEFAULT FALSE,
                    identity_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_upstream_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    estimated_realized_savings_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    estimated_shadow_savings_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    request_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    profile_build_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    semantic_lookup_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    compatibility_validation_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    upstream_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
                )
                """
            )
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tenant_observed ON {self.table_name} (tenant_id, observed_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_workspace_observed ON {self.table_name} (workspace_id, observed_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_namespace_observed ON {self.table_name} (namespace, observed_at DESC)")
            await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_cache_outcome_observed ON {self.table_name} (cache_outcome, observed_at DESC)")
        self._schema_ready = True

    async def log_request(self, payload: dict[str, Any]) -> None:
        pool = await self._get_pool()
        await self.ensure_schema()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                request_id, observed_at, tenant_id, workspace_id, environment_id, api_key_id,
                namespace, model, provider, cache_outcome, semantic_bypass_reason,
                effective_policy_version_id, effective_policy_mode,
                has_visual_context, has_dom_context, is_agentic, identity_sensitive,
                prompt_tokens, completion_tokens, total_tokens,
                estimated_upstream_cost_usd, estimated_realized_savings_usd, estimated_shadow_savings_usd,
                request_latency_ms, profile_build_ms, semantic_lookup_ms, compatibility_validation_ms, upstream_ms,
                metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13,
                $14, $15, $16, $17,
                $18, $19, $20,
                $21, $22, $23,
                $24, $25, $26, $27, $28,
                $29::jsonb
            )
            ON CONFLICT (request_id) DO NOTHING
            """,
            payload["request_id"],
            payload.get("observed_at") or datetime.now(UTC),
            payload.get("tenant_id"),
            payload.get("workspace_id"),
            payload.get("environment_id"),
            payload.get("api_key_id"),
            payload["namespace"],
            payload["model"],
            payload.get("provider"),
            payload["cache_outcome"],
            payload.get("semantic_bypass_reason"),
            payload.get("effective_policy_version_id"),
            payload.get("effective_policy_mode"),
            bool(payload.get("has_visual_context", False)),
            bool(payload.get("has_dom_context", False)),
            bool(payload.get("is_agentic", False)),
            bool(payload.get("identity_sensitive", False)),
            int(payload.get("prompt_tokens", 0) or 0),
            int(payload.get("completion_tokens", 0) or 0),
            int(payload.get("total_tokens", 0) or 0),
            float(payload.get("estimated_upstream_cost_usd", 0.0) or 0.0),
            float(payload.get("estimated_realized_savings_usd", 0.0) or 0.0),
            float(payload.get("estimated_shadow_savings_usd", 0.0) or 0.0),
            float(payload.get("request_latency_ms", 0.0) or 0.0),
            float(payload.get("profile_build_ms", 0.0) or 0.0),
            float(payload.get("semantic_lookup_ms", 0.0) or 0.0),
            float(payload.get("compatibility_validation_ms", 0.0) or 0.0),
            float(payload.get("upstream_ms", 0.0) or 0.0),
            json.dumps(payload.get("metadata") or {}),
        )

    async def recent_requests(self, *, limit: int = 50) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch(
            f"SELECT * FROM {self.table_name} ORDER BY observed_at DESC LIMIT $1",
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
            self._pool = await create_asyncpg_pool(self.dsn, component="request_ledger_repository")
        return self._pool

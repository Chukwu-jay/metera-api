from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None


class PostgresShadowAnalyticsStore:
    def __init__(self, dsn: str, *, table_name: str = "semantic_shadow_analytics") -> None:
        self.dsn = dsn
        self.table_name = table_name
        self._pool = None
        self._schema_ready = False

    async def warmup(self) -> None:
        await self._get_pool()

    async def log_shadow_hit(
        self,
        *,
        request_id: str,
        namespace: str,
        model: str,
        prompt_text: str,
        similarity_score: float,
        calculated_savings_usd: float,
        live_threshold: float,
        shadow_threshold: float,
    ) -> None:
        pool = await self._get_pool()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                request_id,
                namespace,
                model,
                prompt_text,
                similarity_score,
                calculated_savings_usd,
                live_threshold,
                shadow_threshold
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            request_id,
            namespace,
            model,
            prompt_text,
            similarity_score,
            calculated_savings_usd,
            live_threshold,
            shadow_threshold,
        )

    async def purge_expired(self, *, retention_days: int = 14) -> int:
        pool = await self._get_pool()
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        result = await pool.execute(
            f"DELETE FROM {self.table_name} WHERE created_at <= $1",
            cutoff,
        )
        return int(result.split()[-1])

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if asyncpg is None:
            raise RuntimeError("shadow analytics store requires the optional 'asyncpg' dependency")
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.dsn)
        if not self._schema_ready:
            await self._ensure_schema()
            self._schema_ready = True
        return self._pool

    async def _ensure_schema(self) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    similarity_score DOUBLE PRECISION NOT NULL,
                    calculated_savings_usd DOUBLE PRECISION NOT NULL,
                    live_threshold DOUBLE PRECISION NOT NULL,
                    shadow_threshold DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_request_id ON {self.table_name} (request_id)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at ON {self.table_name} (created_at)"
            )


def decode_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return dict(value)

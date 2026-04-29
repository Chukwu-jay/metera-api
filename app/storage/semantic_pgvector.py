from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover - exercised only when optional dependency is missing
    asyncpg = None

from app.storage.semantic_base import SemanticRecord, SemanticStoreMatch


class PgvectorSemanticStore:
    def __init__(self, dsn: str, *, table_name: str = "semantic_cache_entries") -> None:
        self.dsn = dsn
        self.table_name = table_name
        self._pool = None
        self._schema_ready = False

    async def add(self, record: SemanticRecord) -> None:
        pool = await self._get_pool()
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (
                namespace,
                tenant_id,
                workspace_id,
                model,
                model_family,
                text,
                embedding,
                response_payload,
                created_at,
                expires_at,
                metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8::jsonb, $9, $10, $11::jsonb)
            """,
            record.namespace,
            record.tenant_id,
            record.workspace_id,
            record.model,
            record.model_family,
            record.text,
            _encode_vector(record.vector),
            json.dumps(record.response_payload),
            _normalize_datetime(record.created_at),
            _normalize_datetime(record.expires_at),
            json.dumps(record.metadata),
        )

    async def find_best_match(
        self,
        *,
        namespace: str,
        tenant_id: str | None,
        workspace_id: str | None,
        model: str,
        model_family: str,
        vector: list[float],
        similarity_threshold: float,
        now: datetime,
        created_before: datetime | None = None,
    ) -> SemanticStoreMatch | None:
        pool = await self._get_pool()
        min_cosine_distance = 1.0 - similarity_threshold
        created_before_clause = "AND created_at < $9" if created_before is not None else ""
        query = f"""
            SELECT
                namespace,
                tenant_id,
                workspace_id,
                model,
                model_family,
                text,
                embedding,
                response_payload,
                created_at,
                expires_at,
                metadata,
                (1 - (embedding <=> $7::vector)) AS similarity
            FROM {self.table_name}
            WHERE namespace = $1
              AND tenant_id IS NOT DISTINCT FROM $2
              AND workspace_id IS NOT DISTINCT FROM $3
              AND model_family = $4
              AND (expires_at IS NULL OR expires_at > $5)
              AND (model = $6 OR model_family = $4)
              AND (embedding <=> $7::vector) <= $8
              {created_before_clause}
            ORDER BY embedding <=> $7::vector ASC, created_at DESC
            LIMIT 1
            """
        params = [
            namespace,
            tenant_id,
            workspace_id,
            model_family,
            _normalize_datetime(now),
            model,
            _encode_vector(vector),
            min_cosine_distance,
        ]
        if created_before is not None:
            params.append(_normalize_datetime(created_before))
        row = await pool.fetchrow(query, *params)
        if row is None:
            return None
        return SemanticStoreMatch(record=_row_to_record(row), similarity=float(row["similarity"]))

    async def invalidate_namespace(self, namespace: str) -> int:
        pool = await self._get_pool()
        result = await pool.execute(
            f"DELETE FROM {self.table_name} WHERE namespace = $1",
            namespace,
        )
        return int(result.split()[-1])

    async def prune_expired(self, *, now: datetime) -> int:
        pool = await self._get_pool()
        result = await pool.execute(
            f"DELETE FROM {self.table_name} WHERE expires_at IS NOT NULL AND expires_at <= $1",
            _normalize_datetime(now),
        )
        return int(result.split()[-1])

    async def warmup(self) -> None:
        await self._get_pool()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if asyncpg is None:
            raise RuntimeError("pgvector backend requires the optional 'asyncpg' dependency")
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.dsn)
        if not self._schema_ready:
            await self._ensure_schema()
            self._schema_ready = True
        return self._pool

    async def _ensure_schema(self) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    model TEXT NOT NULL,
                    model_family TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector NOT NULL,
                    response_payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    expires_at TIMESTAMPTZ NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
                )
                """
            )
            await conn.execute(
                f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS tenant_id TEXT NULL"
            )
            await conn.execute(
                f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS workspace_id TEXT NULL"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_scope_family ON {self.table_name} (tenant_id, workspace_id, namespace, model_family)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_namespace_family ON {self.table_name} (namespace, model_family)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_expires_at ON {self.table_name} (expires_at)"
            )


def _encode_vector(vector: list[float]) -> str:
    return "[" + ", ".join(str(value) for value in vector) + "]"


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _row_to_record(row: Any) -> SemanticRecord:
    return SemanticRecord(
        namespace=row["namespace"],
        tenant_id=row.get("tenant_id"),
        workspace_id=row.get("workspace_id"),
        model=row["model"],
        model_family=row["model_family"],
        text=row["text"],
        vector=_decode_vector(row["embedding"]),
        response_payload=_decode_json_object(row["response_payload"]),
        created_at=_normalize_datetime(row["created_at"]),
        expires_at=_normalize_datetime(row["expires_at"]),
        metadata=_decode_json_object(row["metadata"]),
    )


def _decode_vector(value: Any) -> list[float]:
    if isinstance(value, str):
        stripped = value.strip().removeprefix("[").removesuffix("]")
        if not stripped:
            return []
        return [float(part.strip()) for part in stripped.split(",") if part.strip()]
    return [float(part) for part in value]



def _decode_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return dict(value)

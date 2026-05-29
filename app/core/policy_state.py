from __future__ import annotations

import json
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None


DEFAULT_POLICY_STATE: dict[str, Any] = {
    "dlp_enabled": None,
    "dlp_scrub_level": None,
    "semantic_enabled": None,
    "semantic_hardening_preset": None,
    "semantic_threshold": None,
    "semantic_shadow_threshold": None,
    "semantic_max_temperature": None,
}

PRODUCTION_POLICY_DEFAULTS: dict[str, Any] = {
    "dlp_enabled": True,
    "dlp_scrub_level": "technical",
    "semantic_enabled": True,
    "semantic_hardening_preset": "conservative",
    "semantic_threshold": 0.9,
    "semantic_shadow_threshold": 0.8,
    "semantic_max_temperature": 0.2,
}


class InMemoryPolicyStore:
    def __init__(self) -> None:
        self._state = dict(DEFAULT_POLICY_STATE)

    async def get_overrides(self) -> dict[str, Any]:
        return dict(self._state)

    async def update_overrides(self, updates: dict[str, Any]) -> dict[str, Any]:
        for key, value in updates.items():
            if key in self._state and value is not None:
                self._state[key] = value
        return dict(self._state)

    async def warmup(self) -> None:
        return None

    async def close(self) -> None:
        return None


class PostgresPolicyStore:
    def __init__(self, dsn: str, *, table_name: str = "admin_policy_overrides") -> None:
        self.dsn = dsn
        self.table_name = table_name
        self._pool = None
        self._schema_ready = False

    async def get_overrides(self) -> dict[str, Any]:
        pool = await self._get_pool()
        row = await pool.fetchrow(
            f"SELECT overrides, semantic_shadow_threshold FROM {self.table_name} WHERE policy_name = $1",
            "default",
        )
        if row is None:
            return dict(DEFAULT_POLICY_STATE)
        payload = _decode_json_object(row["overrides"])
        if row["semantic_shadow_threshold"] is not None:
            payload["semantic_shadow_threshold"] = float(row["semantic_shadow_threshold"])
        return {**dict(DEFAULT_POLICY_STATE), **payload}

    async def update_overrides(self, updates: dict[str, Any]) -> dict[str, Any]:
        pool = await self._get_pool()
        current = await self.get_overrides()
        for key, value in updates.items():
            if key in current and value is not None:
                current[key] = value
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (policy_name, overrides, semantic_shadow_threshold)
            VALUES ($1, $2::jsonb, $3)
            ON CONFLICT (policy_name)
            DO UPDATE SET
                overrides = EXCLUDED.overrides,
                semantic_shadow_threshold = EXCLUDED.semantic_shadow_threshold,
                updated_at = NOW()
            """,
            "default",
            json.dumps(current),
            float(current.get("semantic_shadow_threshold", PRODUCTION_POLICY_DEFAULTS["semantic_shadow_threshold"])),
        )
        return current

    async def warmup(self) -> None:
        await self._get_pool()
        await self.ensure_default_policy_row()

    async def ensure_default_policy_row(self, *, force_production_defaults: bool = False) -> dict[str, Any]:
        pool = await self._get_pool()
        current = await self.get_overrides()
        merged = dict(current)
        for key, value in PRODUCTION_POLICY_DEFAULTS.items():
            if force_production_defaults or merged.get(key) is None:
                merged[key] = value
        await pool.execute(
            f"""
            INSERT INTO {self.table_name} (policy_name, overrides, semantic_shadow_threshold)
            VALUES ($1, $2::jsonb, $3)
            ON CONFLICT (policy_name)
            DO UPDATE SET
                overrides = EXCLUDED.overrides,
                semantic_shadow_threshold = EXCLUDED.semantic_shadow_threshold,
                updated_at = NOW()
            """,
            "default",
            json.dumps(merged),
            float(merged.get("semantic_shadow_threshold", PRODUCTION_POLICY_DEFAULTS["semantic_shadow_threshold"])),
        )
        return merged

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if asyncpg is None:
            raise RuntimeError("postgres policy store requires the optional 'asyncpg' dependency")
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
                    policy_name TEXT PRIMARY KEY,
                    overrides JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    semantic_shadow_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS semantic_shadow_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_updated_at ON {self.table_name} (updated_at)"
            )


async def get_policy_state(app) -> dict[str, Any]:
    store = getattr(app.state, "policy_store", None)
    if store is None:
        store = InMemoryPolicyStore()
        app.state.policy_store = store
    return await store.get_overrides()


async def update_policy_state(app, updates: dict[str, Any]) -> dict[str, Any]:
    store = getattr(app.state, "policy_store", None)
    if store is None:
        store = InMemoryPolicyStore()
        app.state.policy_store = store
    return await store.update_overrides(updates)



def _decode_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return dict(value)

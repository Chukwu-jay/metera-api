from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.db import create_asyncpg_pool

from app.controlplane.models.policy import EffectivePolicy


class PostgresPolicyRepository:
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
                CREATE TABLE IF NOT EXISTS policy_versions (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_ref_id TEXT NULL,
                    version_number INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    dlp_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    dlp_scrub_level TEXT NOT NULL DEFAULT 'technical',
                    semantic_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    semantic_threshold DOUBLE PRECISION NOT NULL,
                    semantic_shadow_threshold DOUBLE PRECISION NOT NULL,
                    semantic_max_temperature DOUBLE PRECISION NOT NULL,
                    identity_guard_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    identity_strict_mode_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    identity_partitioning_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    multimodal_hard_alignment_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    policy_timing_breakdown_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    strict_namespace_prefixes JSONB NOT NULL DEFAULT '[]'::jsonb,
                    high_risk_namespace_prefixes JSONB NOT NULL DEFAULT '[]'::jsonb,
                    extension_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_by TEXT NULL,
                    change_reason TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (scope_type, scope_ref_id, version_number)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_assignments (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    environment_id TEXT NULL,
                    scope_type TEXT NOT NULL,
                    policy_version_id TEXT NOT NULL REFERENCES policy_versions(id),
                    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    effective_to TIMESTAMPTZ NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS namespace_policy_overrides (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    environment_id TEXT NULL,
                    namespace TEXT NOT NULL,
                    policy_version_id TEXT NOT NULL REFERENCES policy_versions(id),
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_change_log (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NULL,
                    workspace_id TEXT NULL,
                    namespace TEXT NULL,
                    previous_policy_version_id TEXT NULL,
                    new_policy_version_id TEXT NOT NULL REFERENCES policy_versions(id),
                    change_actor_type TEXT NOT NULL,
                    change_actor_id TEXT NULL,
                    change_reason TEXT NULL,
                    source TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_assignments_scope ON policy_assignments (scope_type, tenant_id, workspace_id, environment_id, status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_namespace_policy_overrides_scope ON namespace_policy_overrides (workspace_id, environment_id, namespace, status)")
        self._schema_ready = True

    async def ensure_global_policy(self, *, defaults: dict[str, Any]) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        row = await pool.fetchrow(
            "SELECT id FROM policy_versions WHERE scope_type = 'global' AND scope_ref_id IS NULL AND version_number = 1 LIMIT 1"
        )
        if row is not None:
            version_id = row["id"]
        else:
            version_id = f"policy_global_{uuid4().hex}"
            await pool.execute(
                """
                INSERT INTO policy_versions (
                    id, scope_type, scope_ref_id, version_number, dlp_enabled, dlp_scrub_level,
                    semantic_enabled, semantic_threshold, semantic_shadow_threshold, semantic_max_temperature,
                    identity_guard_enabled, identity_strict_mode_enabled, identity_partitioning_enabled,
                    multimodal_hard_alignment_enabled, policy_timing_breakdown_enabled,
                    strict_namespace_prefixes, high_risk_namespace_prefixes, extension_fields, created_by, change_reason
                )
                VALUES ($1, 'global', NULL, 1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14::jsonb, '{}'::jsonb, 'system', 'bootstrap')
                """,
                version_id,
                bool(defaults["dlp_enabled"]),
                defaults["dlp_scrub_level"],
                bool(defaults["semantic_enabled"]),
                float(defaults["semantic_threshold"]),
                float(defaults["semantic_shadow_threshold"]),
                float(defaults["semantic_max_temperature"]),
                bool(defaults["identity_guard_enabled"]),
                bool(defaults["identity_strict_mode_enabled"]),
                bool(defaults["identity_partitioning_enabled"]),
                bool(defaults["multimodal_hard_alignment_enabled"]),
                bool(defaults["policy_timing_breakdown_enabled"]),
                json.dumps(defaults.get("strict_namespace_prefixes", [])),
                json.dumps(defaults.get("high_risk_namespace_prefixes", [])),
            )
        assignment = await pool.fetchrow(
            "SELECT id FROM policy_assignments WHERE scope_type = 'global' AND status = 'active' LIMIT 1"
        )
        if assignment is None:
            await pool.execute(
                """
                INSERT INTO policy_assignments (id, tenant_id, workspace_id, environment_id, scope_type, policy_version_id, status)
                VALUES ($1, NULL, NULL, NULL, 'global', $2, 'active')
                """,
                f"assignment_global_{uuid4().hex}",
                version_id,
            )
        return version_id

    async def resolve_effective_policy(
        self,
        *,
        tenant_id: str | None,
        workspace_id: str | None,
        environment_id: str | None,
        namespace: str,
    ) -> EffectivePolicy | None:
        pool = await self._get_pool()
        await self.ensure_schema()
        now = datetime.now(UTC)
        namespace_row = None
        if workspace_id:
            namespace_row = await pool.fetchrow(
                """
                SELECT pv.*, npo.namespace AS matched_namespace, npo.workspace_id AS matched_workspace_id, npo.environment_id AS matched_environment_id
                FROM namespace_policy_overrides npo
                INNER JOIN policy_versions pv ON pv.id = npo.policy_version_id
                WHERE npo.workspace_id = $1
                  AND (npo.environment_id IS NULL OR npo.environment_id = $2)
                  AND npo.status = 'active'
                  AND $3 LIKE REPLACE(npo.namespace, '*', '%')
                ORDER BY LENGTH(npo.namespace) DESC
                LIMIT 1
                """,
                workspace_id,
                environment_id,
                namespace,
            )
        if namespace_row is not None:
            return _row_to_effective_policy(namespace_row, source_scope="namespace", source_ref_id=namespace_row["matched_workspace_id"])

        row = await pool.fetchrow(
            """
            SELECT pv.*, pa.scope_type AS assignment_scope_type, pa.workspace_id AS assignment_workspace_id, pa.tenant_id AS assignment_tenant_id
            FROM policy_assignments pa
            INNER JOIN policy_versions pv ON pv.id = pa.policy_version_id
            WHERE pa.status = 'active'
              AND pa.effective_from <= $1
              AND (pa.effective_to IS NULL OR pa.effective_to > $1)
              AND (
                    (pa.scope_type = 'workspace' AND pa.workspace_id = $2)
                 OR (pa.scope_type = 'tenant' AND pa.tenant_id = $3)
                 OR (pa.scope_type = 'global')
              )
            ORDER BY CASE pa.scope_type WHEN 'workspace' THEN 3 WHEN 'tenant' THEN 2 WHEN 'global' THEN 1 ELSE 0 END DESC,
                     pa.created_at DESC
            LIMIT 1
            """,
            now,
            workspace_id,
            tenant_id,
        )
        if row is None:
            return None
        source_ref_id = row["assignment_workspace_id"] or row["assignment_tenant_id"]
        return _row_to_effective_policy(row, source_scope=row["assignment_scope_type"], source_ref_id=source_ref_id)

    async def list_policy_versions(self, *, scope_type: str | None = None, scope_ref_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        query = "SELECT * FROM policy_versions WHERE 1=1"
        params: list[Any] = []
        if scope_type:
            params.append(scope_type)
            query += f" AND scope_type = ${len(params)}"
        if scope_ref_id is not None:
            params.append(scope_ref_id)
            query += f" AND scope_ref_id = ${len(params)}"
        query += " ORDER BY created_at DESC"
        rows = await pool.fetch(query, *params)
        return [dict(row) for row in rows]

    async def create_policy_version(
        self,
        *,
        scope_type: str,
        scope_ref_id: str | None,
        policy: dict[str, Any],
        created_by: str = "admin_api",
        change_reason: str | None = None,
    ) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        row = await pool.fetchrow(
            "SELECT COALESCE(MAX(version_number), 0) AS current_version FROM policy_versions WHERE scope_type = $1 AND scope_ref_id IS NOT DISTINCT FROM $2",
            scope_type,
            scope_ref_id,
        )
        version_number = int(row["current_version"] or 0) + 1
        version_id = f"policy_{uuid4().hex}"
        await pool.execute(
            """
            INSERT INTO policy_versions (
                id, scope_type, scope_ref_id, version_number, dlp_enabled, dlp_scrub_level,
                semantic_enabled, semantic_threshold, semantic_shadow_threshold, semantic_max_temperature,
                identity_guard_enabled, identity_strict_mode_enabled, identity_partitioning_enabled,
                multimodal_hard_alignment_enabled, policy_timing_breakdown_enabled,
                strict_namespace_prefixes, high_risk_namespace_prefixes, extension_fields, created_by, change_reason
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb, $17::jsonb, $18::jsonb, $19, $20)
            """,
            version_id,
            scope_type,
            scope_ref_id,
            version_number,
            bool(policy["dlp_enabled"]),
            policy["dlp_scrub_level"],
            bool(policy["semantic_enabled"]),
            float(policy["semantic_threshold"]),
            float(policy["semantic_shadow_threshold"]),
            float(policy["semantic_max_temperature"]),
            bool(policy.get("identity_guard_enabled", False)),
            bool(policy.get("identity_strict_mode_enabled", False)),
            bool(policy.get("identity_partitioning_enabled", False)),
            bool(policy.get("multimodal_hard_alignment_enabled", False)),
            bool(policy.get("policy_timing_breakdown_enabled", False)),
            json.dumps(policy.get("strict_namespace_prefixes", [])),
            json.dumps(policy.get("high_risk_namespace_prefixes", [])),
            json.dumps(policy.get("extension_fields", {})),
            created_by,
            change_reason,
        )
        return version_id

    async def assign_policy(
        self,
        *,
        scope_type: str,
        policy_version_id: str,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        environment_id: str | None = None,
        actor_id: str = "admin_api",
        change_reason: str | None = None,
    ) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        previous = await pool.fetchrow(
            """
            SELECT id, policy_version_id FROM policy_assignments
            WHERE scope_type = $1
              AND tenant_id IS NOT DISTINCT FROM $2
              AND workspace_id IS NOT DISTINCT FROM $3
              AND environment_id IS NOT DISTINCT FROM $4
              AND status = 'active'
            LIMIT 1
            """,
            scope_type,
            tenant_id,
            workspace_id,
            environment_id,
        )
        if previous is not None:
            await pool.execute(
                "UPDATE policy_assignments SET status = 'inactive', effective_to = NOW() WHERE id = $1",
                previous["id"],
            )
        assignment_id = f"assignment_{uuid4().hex}"
        await pool.execute(
            """
            INSERT INTO policy_assignments (id, tenant_id, workspace_id, environment_id, scope_type, policy_version_id, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'active')
            """,
            assignment_id,
            tenant_id,
            workspace_id,
            environment_id,
            scope_type,
            policy_version_id,
        )
        await self._log_policy_change(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            namespace=None,
            previous_policy_version_id=previous["policy_version_id"] if previous else None,
            new_policy_version_id=policy_version_id,
            change_actor_type="platform_admin",
            change_actor_id=actor_id,
            change_reason=change_reason,
            source="api",
        )
        return assignment_id

    async def set_namespace_override(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        environment_id: str | None,
        namespace: str,
        policy_version_id: str,
        actor_id: str = "admin_api",
        change_reason: str | None = None,
    ) -> str:
        pool = await self._get_pool()
        await self.ensure_schema()
        previous = await pool.fetchrow(
            """
            SELECT id, policy_version_id FROM namespace_policy_overrides
            WHERE workspace_id = $1
              AND environment_id IS NOT DISTINCT FROM $2
              AND namespace = $3
              AND status = 'active'
            LIMIT 1
            """,
            workspace_id,
            environment_id,
            namespace,
        )
        if previous is not None:
            await pool.execute(
                "UPDATE namespace_policy_overrides SET status = 'inactive', updated_at = NOW() WHERE id = $1",
                previous["id"],
            )
        override_id = f"namespace_override_{uuid4().hex}"
        await pool.execute(
            """
            INSERT INTO namespace_policy_overrides (id, tenant_id, workspace_id, environment_id, namespace, policy_version_id, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'active')
            """,
            override_id,
            tenant_id,
            workspace_id,
            environment_id,
            namespace,
            policy_version_id,
        )
        await self._log_policy_change(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            namespace=namespace,
            previous_policy_version_id=previous["policy_version_id"] if previous else None,
            new_policy_version_id=policy_version_id,
            change_actor_type="platform_admin",
            change_actor_id=actor_id,
            change_reason=change_reason,
            source="api",
        )
        return override_id

    async def list_policy_assignments(self) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch("SELECT * FROM policy_assignments ORDER BY created_at DESC")
        return [dict(row) for row in rows]

    async def list_namespace_overrides(self, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        if workspace_id:
            rows = await pool.fetch(
                "SELECT * FROM namespace_policy_overrides WHERE workspace_id = $1 ORDER BY updated_at DESC",
                workspace_id,
            )
        else:
            rows = await pool.fetch("SELECT * FROM namespace_policy_overrides ORDER BY updated_at DESC")
        return [dict(row) for row in rows]

    async def list_policy_change_log(self, *, limit: int = 100) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch("SELECT * FROM policy_change_log ORDER BY created_at DESC LIMIT $1", limit)
        return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _log_policy_change(
        self,
        *,
        tenant_id: str | None,
        workspace_id: str | None,
        namespace: str | None,
        previous_policy_version_id: str | None,
        new_policy_version_id: str,
        change_actor_type: str,
        change_actor_id: str | None,
        change_reason: str | None,
        source: str,
    ) -> None:
        pool = await self._get_pool()
        await pool.execute(
            """
            INSERT INTO policy_change_log (
                id, tenant_id, workspace_id, namespace, previous_policy_version_id,
                new_policy_version_id, change_actor_type, change_actor_id, change_reason, source
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            f"policy_change_{uuid4().hex}",
            tenant_id,
            workspace_id,
            namespace,
            previous_policy_version_id,
            new_policy_version_id,
            change_actor_type,
            change_actor_id,
            change_reason,
            source,
        )

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await create_asyncpg_pool(self.dsn, component="policy_repository")
        return self._pool


def _row_to_effective_policy(row, *, source_scope: str, source_ref_id: str | None) -> EffectivePolicy:
    strict_prefixes = _decode_json_list(row.get("strict_namespace_prefixes"))
    high_risk_prefixes = _decode_json_list(row.get("high_risk_namespace_prefixes"))
    return EffectivePolicy(
        policy_version_id=row["id"],
        policy_mode=_infer_policy_mode(strict_prefixes, high_risk_prefixes),
        dlp_enabled=bool(row["dlp_enabled"]),
        dlp_scrub_level=row["dlp_scrub_level"],
        semantic_enabled=bool(row["semantic_enabled"]),
        semantic_threshold=float(row["semantic_threshold"]),
        semantic_shadow_threshold=float(row["semantic_shadow_threshold"]),
        semantic_max_temperature=float(row["semantic_max_temperature"]),
        identity_guard_enabled=bool(row["identity_guard_enabled"]),
        identity_strict_mode_enabled=bool(row["identity_strict_mode_enabled"]),
        identity_partitioning_enabled=bool(row["identity_partitioning_enabled"]),
        multimodal_hard_alignment_enabled=bool(row["multimodal_hard_alignment_enabled"]),
        policy_timing_breakdown_enabled=bool(row["policy_timing_breakdown_enabled"]),
        strict_namespace_prefixes=strict_prefixes,
        high_risk_namespace_prefixes=high_risk_prefixes,
        source_scope=source_scope,
        source_ref_id=source_ref_id,
        extension_fields=_decode_json_object(row.get("extension_fields")),
    )


def _infer_policy_mode(strict_prefixes: list[str], high_risk_prefixes: list[str]) -> str:
    if strict_prefixes:
        return "hard"
    if high_risk_prefixes:
        return "soft"
    return "soft"


def _decode_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return dict(value)


def _decode_json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        loaded = json.loads(value)
        return [str(item) for item in loaded] if isinstance(loaded, list) else []
    return [str(item) for item in value]

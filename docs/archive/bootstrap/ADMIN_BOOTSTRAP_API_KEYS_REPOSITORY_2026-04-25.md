# Admin Bootstrap API Keys Repository Block — 2026-04-25

This is a **paste-ready repository implementation block** for:
- `create_tenant(...)`
- `create_workspace(...)`
- `issue_api_key(...)`
- `bootstrap_tenant_environment(...)`

Target file:
- `app/controlplane/repositories/api_keys.py`

This is written to fit the current repository structure and existing identity model.

---

## Required imports to add near the top of `api_keys.py`

```python
import secrets
import uuid
```

If you want typed asyncpg exception handling, also add:

```python
import asyncpg
```

Your file already imports `json`, `datetime`, `sha256`, and `Any`.

It should also import the existing capability helpers:

```python
from app.core.tenant_authorization import derive_tenant_role, normalize_tenant_capabilities
```

---

## Paste-ready block

```python
class IdentityConflictError(ValueError):
    pass


class IdentityNotFoundError(ValueError):
    pass


class IdentityValidationError(ValueError):
    pass


class PostgresApiKeyRepository:
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
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    default_environment_id TEXT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (tenant_id, slug)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS environments (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (workspace_id, name)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    environment_id TEXT NULL REFERENCES environments(id),
                    key_prefix TEXT NOT NULL UNIQUE,
                    key_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    last_used_at TIMESTAMPTZ NULL,
                    expires_at TIMESTAMPTZ NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    revoked_at TIMESTAMPTZ NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_key_lifecycle_log (
                    id BIGSERIAL PRIMARY KEY,
                    api_key_id TEXT NOT NULL REFERENCES api_keys(id),
                    tenant_id TEXT NOT NULL REFERENCES tenants(id),
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    event_type TEXT NOT NULL,
                    actor_type TEXT NOT NULL,
                    actor_id TEXT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_workspace_status ON api_keys (workspace_id, status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_status ON api_keys (tenant_id, status)")
        self._schema_ready = True

    async def seed_static_identity(
        self,
        *,
        tenant_id: str,
        tenant_slug: str,
        workspace_id: str,
        workspace_slug: str,
        environment_id: str | None,
        environment_name: str | None,
        api_key_id: str,
        api_key_prefix: str,
        api_key_display_name: str,
        api_key_plaintext: str,
    ) -> None:
        pool = await self._get_pool()
        await self.ensure_schema()
        key_hash = sha256(api_key_plaintext.encode("utf-8")).hexdigest()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO tenants (id, slug, name, status, metadata)
                    VALUES ($1, $2, $3, 'active', $4::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        slug = EXCLUDED.slug,
                        name = EXCLUDED.name,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    tenant_id,
                    tenant_slug,
                    tenant_slug.replace("-", " ").title(),
                    json.dumps({"seeded_by": "controlplane_identity"}),
                )
                await conn.execute(
                    """
                    INSERT INTO workspaces (id, tenant_id, slug, name, status, metadata)
                    VALUES ($1, $2, $3, $4, 'active', $5::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        tenant_id = EXCLUDED.tenant_id,
                        slug = EXCLUDED.slug,
                        name = EXCLUDED.name,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    workspace_id,
                    tenant_id,
                    workspace_slug,
                    workspace_slug.replace("-", " ").title(),
                    json.dumps({"seeded_by": "controlplane_identity"}),
                )
                if environment_id and environment_name:
                    await conn.execute(
                        """
                        INSERT INTO environments (id, workspace_id, name, status, metadata)
                        VALUES ($1, $2, $3, 'active', $4::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                            workspace_id = EXCLUDED.workspace_id,
                            name = EXCLUDED.name,
                            status = EXCLUDED.status,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        """,
                        environment_id,
                        workspace_id,
                        environment_name,
                        json.dumps({"seeded_by": "controlplane_identity"}),
                    )
                    await conn.execute(
                        "UPDATE workspaces SET default_environment_id = $2, updated_at = NOW() WHERE id = $1",
                        workspace_id,
                        environment_id,
                    )
                await conn.execute(
                    """
                    INSERT INTO api_keys (
                        id, tenant_id, workspace_id, environment_id, key_prefix, key_hash, display_name, status, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        tenant_id = EXCLUDED.tenant_id,
                        workspace_id = EXCLUDED.workspace_id,
                        environment_id = EXCLUDED.environment_id,
                        key_prefix = EXCLUDED.key_prefix,
                        key_hash = EXCLUDED.key_hash,
                        display_name = EXCLUDED.display_name,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW(),
                        revoked_at = NULL
                    """,
                    api_key_id,
                    tenant_id,
                    workspace_id,
                    environment_id,
                    api_key_prefix,
                    key_hash,
                    api_key_display_name,
                    json.dumps({"seeded_by": "controlplane_identity", "tenant_role": "tenant_admin"}),
                )
                await conn.execute(
                    """
                    INSERT INTO api_key_lifecycle_log (api_key_id, tenant_id, workspace_id, event_type, actor_type, actor_id, payload)
                    VALUES ($1, $2, $3, 'created', 'system', 'controlplane_seed', $4::jsonb)
                    """,
                    api_key_id,
                    tenant_id,
                    workspace_id,
                    json.dumps({"key_prefix": api_key_prefix}),
                )

    async def create_tenant(
        self,
        *,
        slug: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()

        tenant_id = _generate_tenant_id()
        normalized_metadata = _normalize_metadata(metadata)

        existing = await pool.fetchrow(
            "SELECT id FROM tenants WHERE slug = $1 LIMIT 1",
            slug,
        )
        if existing is not None:
            raise IdentityConflictError(f"Tenant slug '{slug}' already exists")

        row = await pool.fetchrow(
            """
            INSERT INTO tenants (id, slug, name, status, metadata)
            VALUES ($1, $2, $3, 'active', $4::jsonb)
            RETURNING id, slug, name, status, metadata, created_at, updated_at
            """,
            tenant_id,
            slug,
            name,
            json.dumps(normalized_metadata),
        )
        return dict(row)

    async def create_workspace(
        self,
        *,
        tenant_id: str,
        slug: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()

        tenant_row = await pool.fetchrow(
            "SELECT id FROM tenants WHERE id = $1 LIMIT 1",
            tenant_id,
        )
        if tenant_row is None:
            raise IdentityNotFoundError("Tenant not found")

        existing = await pool.fetchrow(
            "SELECT id FROM workspaces WHERE tenant_id = $1 AND slug = $2 LIMIT 1",
            tenant_id,
            slug,
        )
        if existing is not None:
            raise IdentityConflictError(f"Workspace slug '{slug}' already exists for tenant '{tenant_id}'")

        workspace_id = _generate_workspace_id()
        normalized_metadata = _normalize_metadata(metadata)

        row = await pool.fetchrow(
            """
            INSERT INTO workspaces (id, tenant_id, slug, name, status, default_environment_id, metadata)
            VALUES ($1, $2, $3, $4, 'active', NULL, $5::jsonb)
            RETURNING id, tenant_id, slug, name, status, default_environment_id, metadata, created_at, updated_at
            """,
            workspace_id,
            tenant_id,
            slug,
            name,
            json.dumps(normalized_metadata),
        )
        return dict(row)

    async def issue_api_key(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        display_name: str,
        tenant_role: str = "tenant_admin",
        tenant_capabilities: tuple[str, ...] | list[str] | set[str] | None = None,
        environment_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor_id: str = "admin_api",
    ) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()

        workspace_row = await pool.fetchrow(
            """
            SELECT id, tenant_id
            FROM workspaces
            WHERE id = $1
            LIMIT 1
            """,
            workspace_id,
        )
        if workspace_row is None:
            raise IdentityNotFoundError("Workspace not found")
        if str(workspace_row["tenant_id"]) != tenant_id:
            raise IdentityValidationError("Workspace does not belong to tenant")

        if environment_id is not None:
            environment_row = await pool.fetchrow(
                """
                SELECT id, workspace_id
                FROM environments
                WHERE id = $1
                LIMIT 1
                """,
                environment_id,
            )
            if environment_row is None:
                raise IdentityNotFoundError("Environment not found")
            if str(environment_row["workspace_id"]) != workspace_id:
                raise IdentityValidationError("Environment does not belong to workspace")

        effective_role = derive_tenant_role(
            tenant_role=tenant_role,
            tenant_capabilities=tenant_capabilities,
        )
        effective_capabilities = normalize_tenant_capabilities(
            role=effective_role,
            tenant_capabilities=tenant_capabilities,
        )

        plaintext_api_key = _generate_plaintext_api_key()
        key_id = _generate_api_key_id()
        key_prefix = _derive_key_prefix(plaintext_api_key)
        key_hash = sha256(plaintext_api_key.encode("utf-8")).hexdigest()

        stored_metadata = _normalize_metadata(metadata)
        stored_metadata["tenant_role"] = effective_role
        stored_metadata["tenant_capabilities"] = list(effective_capabilities)

        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO api_keys (
                        id, tenant_id, workspace_id, environment_id, key_prefix, key_hash, display_name, status, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8::jsonb)
                    RETURNING id, tenant_id, workspace_id, environment_id, key_prefix, display_name, status, metadata, created_at, updated_at, revoked_at
                    """,
                    key_id,
                    tenant_id,
                    workspace_id,
                    environment_id,
                    key_prefix,
                    key_hash,
                    display_name,
                    json.dumps(stored_metadata),
                )

                await conn.execute(
                    """
                    INSERT INTO api_key_lifecycle_log (
                        api_key_id, tenant_id, workspace_id, event_type, actor_type, actor_id, payload
                    )
                    VALUES ($1, $2, $3, 'created', 'platform_admin', $4, $5::jsonb)
                    """,
                    key_id,
                    tenant_id,
                    workspace_id,
                    actor_id,
                    json.dumps({"key_prefix": key_prefix}),
                )

        result = dict(row)
        result["plaintext_api_key"] = plaintext_api_key
        result["tenant_role"] = effective_role
        result["tenant_capabilities"] = list(effective_capabilities)
        return result

    async def bootstrap_tenant_environment(
        self,
        *,
        tenant_slug: str,
        tenant_name: str,
        workspace_slug: str,
        workspace_name: str,
        api_key_display_name: str,
        tenant_role: str = "tenant_admin",
        tenant_capabilities: tuple[str, ...] | list[str] | set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        actor_id: str = "admin_api",
    ) -> dict[str, Any]:
        pool = await self._get_pool()
        await self.ensure_schema()

        existing_tenant = await pool.fetchrow(
            "SELECT id FROM tenants WHERE slug = $1 LIMIT 1",
            tenant_slug,
        )
        if existing_tenant is not None:
            raise IdentityConflictError(f"Tenant slug '{tenant_slug}' already exists")

        normalized_metadata = _normalize_metadata(metadata)

        tenant = await self.create_tenant(
            slug=tenant_slug,
            name=tenant_name,
            metadata={**normalized_metadata, "source": normalized_metadata.get("source", "beta_onboarding")},
        )
        workspace = await self.create_workspace(
            tenant_id=tenant["id"],
            slug=workspace_slug,
            name=workspace_name,
            metadata={**normalized_metadata, "source": normalized_metadata.get("source", "beta_onboarding")},
        )
        api_key = await self.issue_api_key(
            tenant_id=tenant["id"],
            workspace_id=workspace["id"],
            display_name=api_key_display_name,
            tenant_role=tenant_role,
            tenant_capabilities=tenant_capabilities,
            metadata={**normalized_metadata, "source": normalized_metadata.get("source", "beta_onboarding")},
            actor_id=actor_id,
        )

        return {
            "tenant": tenant,
            "workspace": workspace,
            "api_key": api_key,
        }

    async def resolve_key(self, presented_key: str | None) -> ResolvedKeyContext | None:
        if not presented_key:
            return None
        pool = await self._get_pool()
        await self.ensure_schema()
        key_hash = sha256(presented_key.encode("utf-8")).hexdigest()
        row = await pool.fetchrow(
            """
            SELECT
                ak.id AS api_key_id,
                ak.key_prefix,
                ak.display_name,
                ak.environment_id,
                ak.workspace_id,
                ak.tenant_id,
                ak.metadata AS api_key_metadata,
                t.slug AS tenant_slug,
                w.slug AS workspace_slug,
                e.name AS environment_name
            FROM api_keys ak
            INNER JOIN tenants t ON t.id = ak.tenant_id
            INNER JOIN workspaces w ON w.id = ak.workspace_id
            LEFT JOIN environments e ON e.id = ak.environment_id
            WHERE ak.key_hash = $1
              AND ak.status = 'active'
              AND (ak.expires_at IS NULL OR ak.expires_at > $2)
              AND ak.revoked_at IS NULL
            LIMIT 1
            """,
            key_hash,
            datetime.now(UTC),
        )
        if row is None:
            return None
        await pool.execute(
            "UPDATE api_keys SET last_used_at = NOW(), updated_at = NOW() WHERE id = $1",
            row["api_key_id"],
        )
        metadata = _decode_json_object(row["api_key_metadata"])
        tenant_role = str(metadata.get("tenant_role") or "tenant_reader")
        tenant_capabilities = tuple(
            str(item)
            for item in metadata.get("tenant_capabilities", [])
            if str(item).strip()
        )
        return ResolvedKeyContext(
            tenant_id=row["tenant_id"],
            tenant_slug=row["tenant_slug"],
            workspace_id=row["workspace_id"],
            workspace_slug=row["workspace_slug"],
            environment_id=row["environment_id"],
            environment_name=row["environment_name"],
            api_key_id=row["api_key_id"],
            api_key_prefix=row["key_prefix"],
            api_key_display_name=row["display_name"],
            tenant_role=tenant_role,
            tenant_capabilities=tenant_capabilities,
            key_source="postgres",
        )

    async def list_tenants(self) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        rows = await pool.fetch(
            """
            SELECT id, slug, name, status, metadata, created_at, updated_at
            FROM tenants
            ORDER BY created_at ASC
            """
        )
        return [dict(row) for row in rows]

    async def list_workspaces(self, *, tenant_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        if tenant_id:
            rows = await pool.fetch(
                """
                SELECT id, tenant_id, slug, name, status, default_environment_id, metadata, created_at, updated_at
                FROM workspaces
                WHERE tenant_id = $1
                ORDER BY created_at ASC
                """,
                tenant_id,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT id, tenant_id, slug, name, status, default_environment_id, metadata, created_at, updated_at
                FROM workspaces
                ORDER BY created_at ASC
                """
            )
        return [dict(row) for row in rows]

    async def list_api_keys(self, *, workspace_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        await self.ensure_schema()
        if workspace_id:
            rows = await pool.fetch(
                """
                SELECT id, tenant_id, workspace_id, environment_id, key_prefix, display_name, status, last_used_at, expires_at, metadata, created_at, updated_at, revoked_at
                FROM api_keys
                WHERE workspace_id = $1
                ORDER BY created_at ASC
                """,
                workspace_id,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT id, tenant_id, workspace_id, environment_id, key_prefix, display_name, status, last_used_at, expires_at, metadata, created_at, updated_at, revoked_at
                FROM api_keys
                ORDER BY created_at ASC
                """
            )
        return [dict(row) for row in rows]

    async def revoke_api_key(self, *, api_key_id: str, actor_id: str = "admin") -> bool:
        pool = await self._get_pool()
        await self.ensure_schema()
        row = await pool.fetchrow(
            "SELECT id, tenant_id, workspace_id FROM api_keys WHERE id = $1 LIMIT 1",
            api_key_id,
        )
        if row is None:
            return False
        await pool.execute(
            """
            UPDATE api_keys
            SET status = 'revoked', revoked_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            api_key_id,
        )
        await pool.execute(
            """
            INSERT INTO api_key_lifecycle_log (api_key_id, tenant_id, workspace_id, event_type, actor_type, actor_id, payload)
            VALUES ($1, $2, $3, 'revoked', 'platform_admin', $4, $5::jsonb)
            """,
            api_key_id,
            row["tenant_id"],
            row["workspace_id"],
            actor_id,
            json.dumps({"reason": "admin_revocation"}),
        )
        return True

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._schema_ready = False

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await create_asyncpg_pool(self.dsn, component="api_key_repository")
        return self._pool


def _generate_tenant_id() -> str:
    return f"tenant_{uuid.uuid4().hex}"



def _generate_workspace_id() -> str:
    return f"ws_{uuid.uuid4().hex}"



def _generate_api_key_id() -> str:
    return f"mk_{uuid.uuid4().hex}"



def _generate_plaintext_api_key() -> str:
    return f"metera_live_{secrets.token_urlsafe(24)}"



def _derive_key_prefix(plaintext_api_key: str) -> str:
    suffix = plaintext_api_key.removeprefix("metera_live_")[:8]
    return f"mk_live_{suffix}"



def _normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return dict(metadata or {})



def _decode_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return dict(value)
```

---

## What this block includes

It includes the required logic for:
- `create_tenant`
- `create_workspace`
- `issue_api_key`
- `bootstrap_tenant_environment`

And preserves the existing repository behavior for:
- `seed_static_identity`
- `resolve_key`
- list routes
- revoke

---

## Important implementation notes

### 1. This block duplicates the full class intentionally
That makes it easier to paste as a coherent replacement block instead of trying to splice isolated methods into the middle of the class.

### 2. Convenience bootstrap is fail-on-conflict
If the tenant slug already exists, it raises:
- `IdentityConflictError`

That matches the earlier lease-first / safe-first decision.

### 3. Environment remains optional
The bootstrap and API key issuance flow do **not** require environment creation.
That is intentional.

### 4. Metadata carries auth semantics
Issued keys persist:
- `tenant_role`
- `tenant_capabilities`

That keeps the runtime aligned with the existing identity resolution path.

---

## Required surrounding imports recap

Make sure `api_keys.py` has these imports available:

```python
from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from app.core.db import create_asyncpg_pool
from app.core.tenant_authorization import derive_tenant_role, normalize_tenant_capabilities
from app.controlplane.auth.key_resolver import ResolvedKeyContext
```

If you decide to catch low-level asyncpg uniqueness exceptions explicitly later, add `import asyncpg` and wrap the insert calls accordingly. For now, the implementation uses pre-checks, which is fine for the first cut.

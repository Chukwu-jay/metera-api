from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TenantRecord:
    id: str
    slug: str
    name: str
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class WorkspaceRecord:
    id: str
    tenant_id: str
    slug: str
    name: str
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    default_environment_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class EnvironmentRecord:
    id: str
    workspace_id: str
    name: str
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class ApiKeyRecord:
    id: str
    tenant_id: str
    workspace_id: str
    environment_id: str | None
    key_prefix: str
    key_hash: str
    display_name: str
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

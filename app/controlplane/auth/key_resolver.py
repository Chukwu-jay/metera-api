from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest


@dataclass(slots=True)
class ResolvedKeyContext:
    tenant_id: str
    tenant_slug: str
    workspace_id: str
    workspace_slug: str
    environment_id: str | None
    environment_name: str | None
    api_key_id: str
    api_key_prefix: str
    api_key_display_name: str
    tenant_role: str = "tenant_admin"
    tenant_capabilities: tuple[str, ...] = ()
    key_source: str = "static"


class StaticKeyResolver:
    """Compatibility-first key resolver for controlled rollout.

    This is an interim identity spine that lets Metera thread tenant/workspace/key
    identity through the runtime before the full control-plane database model lands.
    """

    def __init__(
        self,
        *,
        api_key: str,
        tenant_id: str,
        tenant_slug: str,
        workspace_id: str,
        workspace_slug: str,
        environment_id: str | None = None,
        environment_name: str | None = None,
        api_key_id: str = "mk_dev_default",
        api_key_prefix: str = "mk_dev",
        api_key_display_name: str = "Development Key",
        tenant_role: str = "tenant_admin",
        tenant_capabilities: tuple[str, ...] = (),
    ) -> None:
        self._api_key_hash = sha256(api_key.encode("utf-8")).hexdigest()
        self._resolved = ResolvedKeyContext(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            workspace_id=workspace_id,
            workspace_slug=workspace_slug,
            environment_id=environment_id,
            environment_name=environment_name,
            api_key_id=api_key_id,
            api_key_prefix=api_key_prefix,
            api_key_display_name=api_key_display_name,
            tenant_role=tenant_role,
            tenant_capabilities=tenant_capabilities,
        )

    async def resolve(self, presented_key: str | None) -> ResolvedKeyContext | None:
        if not presented_key:
            return None
        presented_hash = sha256(presented_key.encode("utf-8")).hexdigest()
        if not compare_digest(presented_hash, self._api_key_hash):
            return None
        return self._resolved

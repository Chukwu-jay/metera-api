from dataclasses import dataclass


@dataclass(slots=True)
class ProxyContext:
    namespace: str
    bearer_token: str | None = None
    request_id: str | None = None
    tenant_id: str | None = None
    tenant_slug: str | None = None
    workspace_id: str | None = None
    workspace_slug: str | None = None
    environment_id: str | None = None
    environment_name: str | None = None
    api_key_id: str | None = None
    api_key_prefix: str | None = None
    api_key_display_name: str | None = None
    tenant_role: str | None = None
    tenant_capabilities: tuple[str, ...] = ()

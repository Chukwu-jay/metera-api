from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_identity_admin import router
from app.core.config import get_settings


class FakeIdentityRepository:
    async def list_tenants(self):
        return [{"id": "tenant_1", "slug": "tenant-one", "name": "Tenant One", "status": "active"}]

    async def create_tenant(self, *, slug, name, metadata):
        return {"id": "tenant_created", "slug": slug, "name": name, "status": "active", "metadata": metadata}

    async def list_workspaces(self, *, tenant_id=None):
        return [{"id": "workspace_1", "tenant_id": tenant_id or "tenant_1", "slug": "main", "name": "Main", "status": "active", "default_environment_id": None}]

    async def create_workspace(self, *, tenant_id, slug, name, metadata):
        return {
            "id": "workspace_created",
            "tenant_id": tenant_id,
            "slug": slug,
            "name": name,
            "status": "active",
            "default_environment_id": None,
            "metadata": metadata,
        }

    async def list_api_keys(self, *, workspace_id=None):
        return [{"id": "key_1", "tenant_id": "tenant_1", "workspace_id": workspace_id or "workspace_1", "environment_id": None, "key_prefix": "metera_", "display_name": "Primary", "status": "active", "revoked_at": None}]

    async def issue_api_key(self, *, tenant_id, workspace_id, display_name, tenant_role, tenant_capabilities, environment_id, metadata, actor_id):
        return {
            "id": "key_created",
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "environment_id": environment_id,
            "key_prefix": "metera_live_",
            "display_name": display_name,
            "status": "active",
            "plaintext_api_key": "metera_live_secret_key",
            "tenant_role": tenant_role,
            "tenant_capabilities": list(tenant_capabilities),
            "metadata": metadata,
        }

    async def bootstrap_tenant_environment(self, *, tenant_slug, tenant_name, workspace_slug, workspace_name, api_key_display_name, tenant_role, tenant_capabilities, metadata, actor_id):
        return {
            "tenant": {"id": "tenant_bootstrap", "slug": tenant_slug, "name": tenant_name, "status": "active"},
            "workspace": {
                "id": "workspace_bootstrap",
                "tenant_id": "tenant_bootstrap",
                "slug": workspace_slug,
                "name": workspace_name,
                "status": "active",
                "default_environment_id": None,
            },
            "api_key": {
                "id": "key_bootstrap",
                "tenant_id": "tenant_bootstrap",
                "workspace_id": "workspace_bootstrap",
                "environment_id": None,
                "key_prefix": "metera_boot_",
                "display_name": api_key_display_name,
                "status": "active",
                "plaintext_api_key": "metera_bootstrap_secret_key",
                "tenant_role": tenant_role,
                "tenant_capabilities": list(tenant_capabilities),
            },
        }

    async def revoke_api_key(self, *, api_key_id, actor_id):
        return api_key_id == "key_1"


def build_app(with_repo: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.identity_repository = FakeIdentityRepository() if with_repo else None
    app.state.identity_resolver = object() if with_repo else None
    app.state.controlplane_identity_enabled = with_repo
    app.state.identity_mode = "repository" if with_repo else "disabled"
    app.state.services = type("Services", (), {"identity_repository": app.state.identity_repository, "identity_resolver": app.state.identity_resolver})()
    app.dependency_overrides[get_settings] = lambda: type("S", (), {"admin_api_key": "secret"})()
    return app


def test_identity_admin_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    status_response = client.get("/admin/identity/status", headers=headers)
    tenants = client.get("/admin/control/tenants", headers=headers)
    created_tenant = client.post(
        "/admin/control/tenants",
        headers=headers,
        json={"slug": "tenant-two", "name": "Tenant Two", "metadata": {"source": "test"}},
    )
    workspaces = client.get("/admin/control/workspaces", headers=headers)
    created_workspace = client.post(
        "/admin/control/workspaces",
        headers=headers,
        json={"tenant_id": "tenant_1", "slug": "ops", "name": "Ops", "metadata": {"source": "test"}},
    )
    api_keys = client.get("/admin/control/api-keys", headers=headers)
    issued_key = client.post(
        "/admin/control/api-keys",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "workspace_id": "workspace_1",
            "display_name": "Primary Live Key",
            "tenant_role": "tenant_admin",
            "tenant_capabilities": ["billing:read", "billing:history:read"],
            "metadata": {"source": "test"},
        },
    )
    bootstrap = client.post(
        "/admin/control/bootstrap/tenant-environment",
        headers=headers,
        json={
            "tenant": {"slug": "acme", "name": "Acme", "metadata": {"tier": "beta"}},
            "workspace": {"slug": "prod", "name": "Production", "metadata": {"region": "us"}},
            "api_key": {
                "display_name": "Acme Production Key",
                "tenant_role": "tenant_admin",
                "tenant_capabilities": ["billing:read", "billing:scope:read"],
                "metadata": {"issued_by": "test"},
            },
        },
    )
    revoke = client.post("/admin/control/api-keys/key_1/revoke", headers=headers)

    assert status_response.status_code == 200
    assert status_response.json()["identity_enabled"] is True

    assert tenants.status_code == 200
    assert tenants.json()[0]["slug"] == "tenant-one"
    assert created_tenant.status_code == 201
    assert created_tenant.json()["slug"] == "tenant-two"

    assert workspaces.status_code == 200
    assert workspaces.json()[0]["slug"] == "main"
    assert created_workspace.status_code == 201
    assert created_workspace.json()["slug"] == "ops"

    assert api_keys.status_code == 200
    assert api_keys.json()[0]["display_name"] == "Primary"
    assert issued_key.status_code == 201
    assert issued_key.json()["plaintext_api_key"] == "metera_live_secret_key"
    assert issued_key.json()["tenant_capabilities"] == ["billing:read", "billing:history:read"]

    assert bootstrap.status_code == 201
    bootstrap_body = bootstrap.json()
    assert bootstrap_body["tenant"]["slug"] == "acme"
    assert bootstrap_body["workspace"]["slug"] == "prod"
    assert bootstrap_body["api_key"]["plaintext_api_key"] == "metera_bootstrap_secret_key"
    assert bootstrap_body["bootstrap"]["namespace_header"] == "x-metera-namespace"
    assert bootstrap_body["bootstrap"]["recommended_namespace"] == "acme-prod"
    assert bootstrap_body["bootstrap"]["chat_completions_url"] == "/v1/chat/completions"

    assert revoke.status_code == 200
    assert revoke.json()["revoked"] is True


def test_identity_admin_routes_require_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/admin/control/tenants", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Identity repository is not available"

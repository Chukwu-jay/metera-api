from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_admin import router
from app.core.config import get_settings


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.revoked: list[str] = []

    async def list_tenants(self):
        return [
            {"id": "tenant_1", "slug": "acme", "name": "Acme", "status": "active"},
        ]

    async def list_workspaces(self, *, tenant_id: str | None = None):
        rows = [
            {
                "id": "workspace_1",
                "tenant_id": "tenant_1",
                "slug": "default",
                "name": "Default",
                "status": "active",
                "default_environment_id": "env_1",
            }
        ]
        if tenant_id:
            return [row for row in rows if row["tenant_id"] == tenant_id]
        return rows

    async def list_api_keys(self, *, workspace_id: str | None = None):
        rows = [
            {
                "id": "key_1",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "environment_id": "env_1",
                "key_prefix": "mk_live",
                "display_name": "Primary",
                "status": "active",
                "revoked_at": None,
            }
        ]
        if workspace_id:
            return [row for row in rows if row["workspace_id"] == workspace_id]
        return rows

    async def revoke_api_key(self, *, api_key_id: str, actor_id: str = "admin") -> bool:
        if api_key_id != "key_1":
            return False
        self.revoked.append(api_key_id)
        return True


def build_app(with_repo: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.controlplane_identity_enabled = True
    app.state.identity_mode = "repository"
    app.state.identity_resolver = object()
    app.state.identity_repository = FakeIdentityRepository() if with_repo else None
    app.dependency_overrides[get_settings] = lambda: type(
        "S",
        (),
        {
            "admin_api_key": "secret",
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.9,
            "semantic_shadow_threshold": 0.8,
            "semantic_max_temperature": 0.2,
            "namespace_header": "x-metera-namespace",
        },
    )()
    return app


def test_admin_identity_status_reports_rollout_state() -> None:
    client = TestClient(build_app())
    response = client.get("/admin/identity/status", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["identity_enabled"] is True
    assert body["identity_mode"] == "repository"
    assert body["repository_available"] is True
    assert body["resolver_configured"] is True


def test_admin_control_identity_listing_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    tenants = client.get("/admin/control/tenants", headers=headers)
    workspaces = client.get("/admin/control/workspaces", headers=headers)
    api_keys = client.get("/admin/control/api-keys", headers=headers)

    assert tenants.status_code == 200
    assert tenants.json()[0]["slug"] == "acme"
    assert workspaces.status_code == 200
    assert workspaces.json()[0]["tenant_id"] == "tenant_1"
    assert api_keys.status_code == 200
    assert api_keys.json()[0]["key_prefix"] == "mk_live"


def test_admin_control_revoke_api_key() -> None:
    app = build_app()
    client = TestClient(app)
    response = client.post("/admin/control/api-keys/key_1/revoke", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 200
    assert response.json()["revoked"] is True


def test_admin_control_identity_routes_require_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/admin/control/tenants", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Identity repository is not available"

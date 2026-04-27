from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_admin import router
from app.core.config import get_settings


class FakePolicyRepository:
    def __init__(self) -> None:
        self.created_versions: list[dict] = []
        self.assignments: list[dict] = []
        self.namespace_overrides: list[dict] = []

    async def list_policy_versions(self, *, scope_type: str | None = None, scope_ref_id: str | None = None):
        rows = [
            {
                "id": "policy_1",
                "scope_type": "global",
                "scope_ref_id": None,
                "version_number": 1,
                "semantic_threshold": 0.9,
                "semantic_shadow_threshold": 0.8,
                "semantic_max_temperature": 0.2,
                "created_by": "system",
                "change_reason": "bootstrap",
            }
        ]
        if scope_type:
            rows = [row for row in rows if row["scope_type"] == scope_type]
        if scope_ref_id is not None:
            rows = [row for row in rows if row["scope_ref_id"] == scope_ref_id]
        return rows

    async def create_policy_version(self, *, scope_type, scope_ref_id, policy, created_by="admin_api", change_reason=None):
        self.created_versions.append({
            "scope_type": scope_type,
            "scope_ref_id": scope_ref_id,
            "policy": policy,
            "created_by": created_by,
            "change_reason": change_reason,
        })
        return "policy_created"

    async def list_policy_assignments(self):
        return [
            {
                "id": "assignment_1",
                "scope_type": "workspace",
                "policy_version_id": "policy_1",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "environment_id": None,
                "status": "active",
            }
        ]

    async def assign_policy(self, *, scope_type, policy_version_id, tenant_id=None, workspace_id=None, environment_id=None, actor_id="admin_api", change_reason=None):
        self.assignments.append({
            "scope_type": scope_type,
            "policy_version_id": policy_version_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "environment_id": environment_id,
            "actor_id": actor_id,
            "change_reason": change_reason,
        })
        return "assignment_created"

    async def list_namespace_overrides(self, *, workspace_id: str | None = None):
        rows = [
            {
                "id": "override_1",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "environment_id": None,
                "namespace": "faq-billing",
                "policy_version_id": "policy_2",
                "status": "active",
            }
        ]
        if workspace_id:
            rows = [row for row in rows if row["workspace_id"] == workspace_id]
        return rows

    async def set_namespace_override(self, *, tenant_id, workspace_id, environment_id, namespace, policy_version_id, actor_id="admin_api", change_reason=None):
        self.namespace_overrides.append({
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "environment_id": environment_id,
            "namespace": namespace,
            "policy_version_id": policy_version_id,
            "actor_id": actor_id,
            "change_reason": change_reason,
        })
        return "override_created"

    async def list_policy_change_log(self, *, limit: int = 100):
        return [
            {
                "id": "change_1",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "namespace": "faq-billing",
                "previous_policy_version_id": "policy_1",
                "new_policy_version_id": "policy_2",
                "change_actor_type": "platform_admin",
                "change_actor_id": "admin_api",
                "change_reason": "tighten browser lane",
                "source": "api",
            }
        ]


def build_app(with_repo: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.identity_repository = None
    app.state.policy_repository = FakePolicyRepository() if with_repo else None
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


def test_admin_scoped_policy_listing_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    versions = client.get("/admin/control/policy/versions", headers=headers)
    assignments = client.get("/admin/control/policy/assignments", headers=headers)
    overrides = client.get("/admin/control/policy/namespace-overrides", headers=headers)
    change_log = client.get("/admin/control/policy/change-log", headers=headers)

    assert versions.status_code == 200
    assert versions.json()[0]["id"] == "policy_1"
    assert assignments.status_code == 200
    assert assignments.json()[0]["scope_type"] == "workspace"
    assert overrides.status_code == 200
    assert overrides.json()[0]["namespace"] == "faq-billing"
    assert change_log.status_code == 200
    assert change_log.json()[0]["new_policy_version_id"] == "policy_2"


def test_admin_scoped_policy_mutation_routes() -> None:
    app = build_app()
    client = TestClient(app)
    headers = {"x-metera-admin-key": "secret"}

    create_response = client.post(
        "/admin/control/policy/versions",
        headers=headers,
        json={
            "scope_type": "workspace",
            "scope_ref_id": "workspace_1",
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.93,
            "semantic_shadow_threshold": 0.83,
            "semantic_max_temperature": 0.2,
            "identity_guard_enabled": True,
            "identity_strict_mode_enabled": True,
            "identity_partitioning_enabled": True,
            "multimodal_hard_alignment_enabled": True,
            "policy_timing_breakdown_enabled": True,
            "strict_namespace_prefixes": ["browser-"],
            "high_risk_namespace_prefixes": ["faq-billing"],
            "extension_fields": {},
            "change_reason": "workspace tightening",
        },
    )
    assign_response = client.post(
        "/admin/control/policy/assignments",
        headers=headers,
        json={
            "scope_type": "workspace",
            "policy_version_id": "policy_created",
            "tenant_id": "tenant_1",
            "workspace_id": "workspace_1",
            "change_reason": "activate workspace policy",
        },
    )
    override_response = client.post(
        "/admin/control/policy/namespace-overrides",
        headers=headers,
        json={
            "tenant_id": "tenant_1",
            "workspace_id": "workspace_1",
            "namespace": "faq-billing",
            "policy_version_id": "policy_created",
            "change_reason": "namespace hardening",
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["policy_version_id"] == "policy_created"
    assert assign_response.status_code == 200
    assert assign_response.json()["assignment_id"] == "assignment_created"
    assert override_response.status_code == 200
    assert override_response.json()["override_id"] == "override_created"


def test_admin_scoped_policy_routes_require_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/admin/control/policy/versions", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Policy repository is not available"

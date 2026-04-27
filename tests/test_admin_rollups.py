from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_rollups_admin import router
from app.core.config import get_settings


class FakeRollupRepository:
    async def rebuild_daily_usage_rollups(self):
        return 3

    async def rebuild_daily_namespace_rollups(self):
        return 5

    async def list_daily_usage_rollups(self, *, limit: int = 100, tenant_id=None, workspace_id=None, rollup_date=None):
        rows = [
            {
                "rollup_date": __import__("datetime").date(2026, 4, 21),
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "request_count": 10,
                "exact_hit_count": 2,
                "semantic_hit_count": 3,
                "miss_count": 5,
                "upstream_cost_usd_total": 1.25,
                "realized_savings_usd_total": 0.75,
                "shadow_savings_usd_total": 0.15,
            }
        ]
        if tenant_id:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        if workspace_id:
            rows = [row for row in rows if row["workspace_id"] == workspace_id]
        if rollup_date:
            rows = [row for row in rows if row["rollup_date"].isoformat() == rollup_date]
        return rows[:limit]

    async def list_daily_namespace_rollups(self, *, limit: int = 100, tenant_id=None, workspace_id=None, namespace=None, rollup_date=None):
        rows = [
            {
                "rollup_date": __import__("datetime").date(2026, 4, 21),
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "namespace": "faq-billing",
                "request_count": 4,
                "exact_hit_count": 1,
                "semantic_hit_count": 1,
                "miss_count": 2,
                "shadow_alert_count": 1,
                "visual_request_count": 0,
                "agentic_request_count": 1,
                "identity_sensitive_request_count": 1,
                "upstream_cost_usd_total": 0.5,
                "realized_savings_usd_total": 0.25,
                "shadow_savings_usd_total": 0.05,
            }
        ]
        if tenant_id:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        if workspace_id:
            rows = [row for row in rows if row["workspace_id"] == workspace_id]
        if namespace:
            rows = [row for row in rows if row["namespace"] == namespace]
        if rollup_date:
            rows = [row for row in rows if row["rollup_date"].isoformat() == rollup_date]
        return rows[:limit]


def build_app(with_repo: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.rollup_repository = FakeRollupRepository() if with_repo else None
    app.state.identity_repository = None
    app.state.policy_repository = None
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


def test_admin_rollup_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    rebuild_usage = client.post("/admin/control/rollups/rebuild/usage", headers=headers)
    rebuild_namespace = client.post("/admin/control/rollups/rebuild/namespaces", headers=headers)
    usage = client.get("/admin/control/rollups/usage", headers=headers)
    namespaces = client.get("/admin/control/rollups/namespaces", headers=headers)

    assert rebuild_usage.status_code == 200
    assert rebuild_usage.json()["affected_rows"] == 3
    assert rebuild_namespace.status_code == 200
    assert rebuild_namespace.json()["affected_rows"] == 5
    assert usage.status_code == 200
    assert usage.json()[0]["request_count"] == 10
    assert namespaces.status_code == 200
    assert namespaces.json()[0]["namespace"] == "faq-billing"


def test_admin_rollup_routes_require_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/admin/control/rollups/usage", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Rollup repository is not available"

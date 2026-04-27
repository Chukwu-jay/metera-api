from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_observability_admin import router
from app.core.config import get_settings


class FakeLedgerRepository:
    async def recent_requests(self, *, limit: int = 50):
        return [
            {
                "request_id": "req_1",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "namespace": "tenant-a",
                "model": "gpt-4o-mini",
                "cache_outcome": "miss",
                "effective_policy_version_id": "policy_1",
                "effective_policy_mode": "soft",
                "estimated_upstream_cost_usd": 0.01,
                "estimated_realized_savings_usd": 0.0,
            }
        ]


class FakeRequestEventRepository:
    async def recent_events(self, *, limit: int = 50):
        return [
            {
                "request_id": "req_1",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "namespace": "tenant-a",
                "model": "gpt-4o-mini",
                "cache_outcome": "miss",
                "policy_mode": "soft",
                "estimated_cost_usd": 0.01,
                "estimated_savings_usd": 0.0,
            }
        ]


class FakeRiskEventRepository:
    async def recent_events(self, *, limit: int = 50):
        return [
            {
                "request_id": "req_2",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "namespace": "faq-billing",
                "event_type": "shadow_regression_alert",
                "severity": "warning",
                "reason": "semantic_candidate_rejected",
            }
        ]


class FakeShadowSavingsRepository:
    async def recent_entries(self, *, limit: int = 50):
        return [
            {
                "request_id": "req_3",
                "tenant_id": "tenant_1",
                "workspace_id": "workspace_1",
                "namespace": "tenant-a",
                "similarity_score": 0.9,
                "live_threshold": 0.95,
                "shadow_threshold": 0.8,
                "calculated_savings_usd": 0.02,
            }
        ]


def build_app(with_repos: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.identity_repository = None
    app.state.policy_repository = None
    app.state.request_ledger_repository = FakeLedgerRepository() if with_repos else None
    app.state.request_event_repository = FakeRequestEventRepository() if with_repos else None
    app.state.risk_event_repository = FakeRiskEventRepository() if with_repos else None
    app.state.shadow_savings_repository = FakeShadowSavingsRepository() if with_repos else None
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


def test_admin_ledger_and_event_inspection_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    ledger = client.get("/admin/control/request-ledger", headers=headers)
    events = client.get("/admin/control/request-events", headers=headers)
    risks = client.get("/admin/control/risk-events", headers=headers)
    shadow = client.get("/admin/control/shadow-savings", headers=headers)

    assert ledger.status_code == 200
    assert ledger.json()[0]["request_id"] == "req_1"
    assert events.status_code == 200
    assert events.json()[0]["cache_outcome"] == "miss"
    assert risks.status_code == 200
    assert risks.json()[0]["event_type"] == "shadow_regression_alert"
    assert shadow.status_code == 200
    assert shadow.json()[0]["calculated_savings_usd"] == 0.02


def test_admin_ledger_routes_require_repositories() -> None:
    client = TestClient(build_app(with_repos=False))
    response = client.get("/admin/control/request-ledger", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Request ledger repository is not available"

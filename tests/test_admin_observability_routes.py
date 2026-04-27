from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_observability_admin import router
from app.core.config import get_settings


class FakeRequestLedgerRepository:
    async def recent_requests(self, limit=50):
        return [{"request_id": "req_1", "tenant_id": "tenant_1", "workspace_id": "workspace_1", "namespace": "default", "model": "gpt-4o-mini", "cache_outcome": "miss", "effective_policy_version_id": "policy_1", "effective_policy_mode": "soft", "estimated_upstream_cost_usd": 0.5, "estimated_realized_savings_usd": 0.1}]


class FakeRequestEventRepository:
    async def recent_events(self, limit=50):
        return [{"request_id": "req_1", "tenant_id": "tenant_1", "workspace_id": "workspace_1", "namespace": "default", "model": "gpt-4o-mini", "cache_outcome": "miss", "policy_mode": "soft", "estimated_cost_usd": 0.5, "estimated_savings_usd": 0.1}]


class FakeRiskEventRepository:
    async def recent_events(self, limit=50):
        return [{"request_id": "req_1", "tenant_id": "tenant_1", "workspace_id": "workspace_1", "namespace": "default", "event_type": "shadow_regression_alert", "severity": "warning", "reason": "semantic_candidate_rejected"}]


class FakeShadowSavingsRepository:
    async def recent_entries(self, limit=50):
        return [{"request_id": "req_1", "tenant_id": "tenant_1", "workspace_id": "workspace_1", "namespace": "default", "similarity_score": 0.82, "live_threshold": 0.9, "shadow_threshold": 0.8, "calculated_savings_usd": 0.2}]


def build_app(with_repos: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    services = type(
        "Services",
        (),
        {
            "request_ledger_repository": FakeRequestLedgerRepository() if with_repos else None,
            "request_event_repository": FakeRequestEventRepository() if with_repos else None,
            "risk_event_repository": FakeRiskEventRepository() if with_repos else None,
            "shadow_savings_repository": FakeShadowSavingsRepository() if with_repos else None,
        },
    )()
    app.state.services = services
    app.dependency_overrides[get_settings] = lambda: type("S", (), {"admin_api_key": "secret"})()
    return app


def test_observability_admin_routes() -> None:
    client = TestClient(build_app())
    headers = {"x-metera-admin-key": "secret"}

    ledger = client.get("/admin/control/request-ledger", headers=headers)
    events = client.get("/admin/control/request-events", headers=headers)
    risks = client.get("/admin/control/risk-events", headers=headers)
    shadow = client.get("/admin/control/shadow-savings", headers=headers)

    assert ledger.status_code == 200
    assert ledger.json()[0]["request_id"] == "req_1"
    assert events.status_code == 200
    assert events.json()[0]["policy_mode"] == "soft"
    assert risks.status_code == 200
    assert risks.json()[0]["event_type"] == "shadow_regression_alert"
    assert shadow.status_code == 200
    assert shadow.json()[0]["similarity_score"] == 0.82


def test_observability_admin_routes_require_repositories() -> None:
    client = TestClient(build_app(with_repos=False))
    response = client.get("/admin/control/request-ledger", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Request ledger repository is not available"

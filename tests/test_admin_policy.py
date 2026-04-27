from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_admin import router
from app.core.config import get_settings
from app.core.policy_state import InMemoryPolicyStore


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.policy_store = InMemoryPolicyStore()
    return app


def test_admin_policy_get_returns_effective_settings() -> None:
    app = build_app()
    app.dependency_overrides[get_settings] = lambda: type(
        "S",
        (),
        {
            "admin_api_key": "secret",
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.97,
            "semantic_max_temperature": 0.2,
        },
    )()
    client = TestClient(app)

    response = client.get("/admin/policy", headers={"x-metera-admin-key": "secret"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["dlp_enabled"] is True
    assert body["semantic_threshold"] == 0.97
    assert body["overrides_active"]["semantic_threshold"] is False


def test_admin_policy_post_applies_persisted_overrides() -> None:
    app = build_app()
    app.dependency_overrides[get_settings] = lambda: type(
        "S",
        (),
        {
            "admin_api_key": "secret",
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.97,
            "semantic_max_temperature": 0.2,
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/admin/policy",
        headers={"x-metera-admin-key": "secret"},
        json={"dlp_enabled": False, "semantic_threshold": 0.91},
    )
    follow_up = client.get("/admin/policy", headers={"x-metera-admin-key": "secret"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["dlp_enabled"] is False
    assert body["semantic_threshold"] == 0.91
    assert body["overrides_active"]["dlp_enabled"] is True
    assert body["overrides_active"]["semantic_threshold"] is True
    assert follow_up.json()["dlp_enabled"] is False
    assert follow_up.json()["semantic_threshold"] == 0.91

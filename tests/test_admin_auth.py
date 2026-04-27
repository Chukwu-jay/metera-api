from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_admin import router
from app.core.config import get_settings


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_admin_routes_require_configured_api_key() -> None:
    client = TestClient(build_app())
    response = client.post("/admin/detectors/dry-run", json={"text": "hello"})
    assert response.status_code == 503


def test_admin_routes_reject_missing_or_invalid_key() -> None:
    app = build_app()
    app.dependency_overrides[get_settings] = lambda: type(
        "S",
        (),
        {
            "admin_api_key": "secret",
            "dlp_scrub_level": "off",
            "dlp_custom_detectors_json": None,
            "dlp_custom_detectors_yaml_path": None,
            "dlp_analyzer_mode": "regex",
            "dlp_detect_email": None,
            "dlp_detect_phone": None,
            "dlp_detect_ip": None,
            "dlp_detect_secrets": None,
        },
    )()
    client = TestClient(app)

    missing = client.post("/admin/detectors/dry-run", json={"text": "hello"})
    invalid = client.post("/admin/detectors/dry-run", headers={"x-metera-admin-key": "wrong"}, json={"text": "hello"})
    valid = client.post("/admin/detectors/dry-run", headers={"x-metera-admin-key": "secret"}, json={"text": "hello"})
    valid_bearer = client.post(
        "/admin/detectors/dry-run",
        headers={"authorization": "Bearer secret"},
        json={"text": "hello"},
    )
    invalid_bearer = client.post(
        "/admin/detectors/dry-run",
        headers={"authorization": "Bearer wrong"},
        json={"text": "hello"},
    )

    app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200
    assert valid_bearer.status_code == 200
    assert invalid_bearer.status_code == 401

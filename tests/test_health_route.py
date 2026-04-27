from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_health import router


def test_health_route_returns_cache_object() -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.deployment_profile = "pilot-local"
    app.state.posture_strict_startup = True
    app.state.posture_errors = []
    app.state.posture_warnings = ["warning-a"]
    app.state.posture_expected = {"identity_mode": "repository"}
    app.state.posture_observed = {"controlplane_identity_enabled": True}
    app.state.identity_mode = "repository"
    app.state.controlplane_identity_enabled = True
    app.state.cache_backend_requested = "redis"
    app.state.cache_backend_active = "memory"
    app.state.cache_fallback_active = True
    app.state.cache_warning = "Redis unavailable, fell back to memory"
    app.state.last_redis_fallback_utc = "2026-04-16T03:59:00Z"
    app.state.scrub_mode = "strict"
    app.state.active_custom_detectors = ["INTERNAL_DB_PASSWORD", "INTERNAL_SESSION_TOKEN"]
    app.state.custom_detector_json_enabled = True
    app.state.custom_detector_yaml_path = "./config/detectors.yaml"
    app.state.semantic_enabled = True
    app.state.semantic_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    app.state.semantic_backend = "fallback"
    app.state.semantic_fallback_active = True
    app.state.semantic_max_temperature = 0.2
    app.state.semantic_store_requested = "pgvector"
    app.state.semantic_store_active = "memory"
    app.state.semantic_store_fallback_active = True
    app.state.semantic_store_warning = "pgvector semantic store unavailable, fell back to memory: ConnectionError"
    app.state.last_semantic_store_fallback_utc = "2026-04-16T04:01:00Z"
    app.state.semantic_store_dsn = "postgresql://postgres:secret@db.internal:5432/metera"
    app.state.redis_url = "redis://:secret@redis.internal:6379/0"

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    body_text = response.text
    assert body["status"] == "ok"
    assert body["readiness"]["ready"] is False
    assert "exact cache is running on fallback backend" in body["readiness"]["issues"]
    assert body["posture"]["deployment_profile"] == "pilot-local"
    assert body["posture"]["strict_startup"] is True
    assert body["posture"]["warnings"] == ["warning-a"]
    assert body["posture"]["runtime_identity_mode"] == "repository"
    assert body["cache"]["requested_backend"] == "redis"
    assert body["cache"]["active_backend"] == "memory"
    assert body["cache"]["fallback_active"] is True
    assert "Redis unavailable" in body["cache"]["warning"]
    assert body["cache"]["last_redis_fallback_utc"] == "2026-04-16T03:59:00Z"
    assert body["scrub_mode"] == "strict"
    assert body["active_custom_detectors"] == ["INTERNAL_DB_PASSWORD", "INTERNAL_SESSION_TOKEN"]
    assert body["semantic"]["enabled"] is True
    assert body["semantic"]["backend"] == "fallback"
    assert body["semantic"]["fallback_active"] is True
    assert body["semantic"]["store"]["requested_backend"] == "pgvector"
    assert body["semantic"]["store"]["active_backend"] == "memory"
    assert body["semantic"]["store"]["fallback_active"] is True
    assert "pgvector semantic store unavailable" in body["semantic"]["store"]["warning"]
    assert body["semantic"]["store"]["last_fallback_utc"] == "2026-04-16T04:01:00Z"
    assert "postgresql://" not in body_text
    assert "redis://" not in body_text
    assert "db.internal" not in body_text
    assert "redis.internal" not in body_text

    ready_response = client.get("/ready")
    assert ready_response.status_code == 503
    assert ready_response.json()["status"] == "not_ready"

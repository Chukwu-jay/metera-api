from fastapi import APIRouter, Request, Response, status

from app.core.posture import evaluate_runtime_readiness

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    ready, readiness_issues = evaluate_runtime_readiness(request.app.state)
    return {
        "status": "ok",
        "readiness": {
            "ready": ready,
            "issues": readiness_issues,
        },
        "posture": {
            "deployment_profile": getattr(request.app.state, "deployment_profile", "dev"),
            "strict_startup": getattr(request.app.state, "posture_strict_startup", False),
            "errors": getattr(request.app.state, "posture_errors", []),
            "warnings": getattr(request.app.state, "posture_warnings", []),
            "expected": getattr(request.app.state, "posture_expected", {}),
            "observed": getattr(request.app.state, "posture_observed", {}),
            "runtime_identity_mode": getattr(request.app.state, "identity_mode", None),
        },
        "cache": {
            "requested_backend": getattr(request.app.state, "cache_backend_requested", "memory"),
            "active_backend": getattr(request.app.state, "cache_backend_active", "memory"),
            "fallback_active": getattr(request.app.state, "cache_fallback_active", False),
            "warning": getattr(request.app.state, "cache_warning", None),
            "last_redis_fallback_utc": getattr(request.app.state, "last_redis_fallback_utc", None),
        },
        "semantic": {
            "enabled": getattr(request.app.state, "semantic_enabled", True),
            "model_name": getattr(request.app.state, "semantic_model_name", None),
            "backend": getattr(request.app.state, "semantic_backend", "unknown"),
            "fallback_active": getattr(request.app.state, "semantic_fallback_active", False),
            "max_temperature": getattr(request.app.state, "semantic_max_temperature", 0.2),
            "store": {
                "requested_backend": getattr(request.app.state, "semantic_store_requested", "memory"),
                "active_backend": getattr(request.app.state, "semantic_store_active", "memory"),
                "fallback_active": getattr(request.app.state, "semantic_store_fallback_active", False),
                "warning": getattr(request.app.state, "semantic_store_warning", None),
                "last_fallback_utc": getattr(request.app.state, "last_semantic_store_fallback_utc", None),
            },
        },
        "scrub_mode": getattr(request.app.state, "scrub_mode", "technical"),
        "active_custom_detectors": getattr(request.app.state, "active_custom_detectors", []),
        "custom_detector_sources": {
            "json_enabled": getattr(request.app.state, "custom_detector_json_enabled", False),
            "yaml_path": getattr(request.app.state, "custom_detector_yaml_path", None),
        },
    }


@router.get("/ready")
def ready(request: Request, response: Response) -> dict:
    ready_state, issues = evaluate_runtime_readiness(request.app.state)
    if not ready_state:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_state else "not_ready",
        "deployment_profile": getattr(request.app.state, "deployment_profile", "dev"),
        "issues": issues,
        "identity_mode": getattr(request.app.state, "identity_mode", None),
        "cache_backend": getattr(request.app.state, "cache_backend_active", "memory"),
        "semantic_store_backend": getattr(request.app.state, "semantic_store_active", "memory"),
    }

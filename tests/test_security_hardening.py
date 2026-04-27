from fastapi import FastAPI, Request
from pydantic import ValidationError

from app.core.logging import build_request_log_context
from app.models.api import ChatCompletionRequest, ChatMessage, DetectorDryRunRequest


def test_chat_request_rejects_too_many_messages() -> None:
    messages = [ChatMessage(role="user", content="hello") for _ in range(65)]
    try:
        ChatCompletionRequest(model="gpt-4o-mini", messages=messages)
    except ValidationError:
        return
    raise AssertionError("expected validation error for too many messages")



def test_detector_dry_run_rejects_large_payload() -> None:
    oversized = "x" * 20001
    try:
        DetectorDryRunRequest(text=oversized)
    except ValidationError:
        return
    raise AssertionError("expected validation error for oversized dry-run payload")



def test_request_log_context_never_logs_secret_header_values() -> None:
    app = FastAPI()
    app.state.scrub_mode = "technical"
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [
            (b"authorization", b"Bearer super-secret-token"),
            (b"x-metera-admin-key", b"dev-admin-key"),
            (b"x-metera-namespace", b"tenant-a"),
            (b"content-type", b"application/json"),
        ],
        "app": app,
    }
    request = Request(scope)

    context = build_request_log_context(request=request, status_code=200, duration_ms=12.34)

    assert context["namespace"] == "tenant-a"
    assert context["safe_headers"]["content-type"] == "application/json"
    assert context["sensitive_headers_present"]["authorization"] is True
    assert context["sensitive_headers_present"]["x-metera-admin-key"] is True
    assert "super-secret-token" not in str(context)
    assert "dev-admin-key" not in str(context)

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.logging import build_request_log_context, log_request_response


def test_request_log_context_is_scrub_aware() -> None:
    app = FastAPI()
    app.state.scrub_mode = "technical"
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [
            (b"authorization", b"Bearer super-secret-token"),
            (b"x-metera-namespace", b"tenant-a"),
        ],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
        "app": app,
    }
    request = Request(scope)
    context = build_request_log_context(request=request, status_code=200, duration_ms=12.34)

    assert context["path"] == "/health"
    assert context["namespace"] == "tenant-a"
    assert context["authorization_present"] is True
    assert context["scrub_mode"] == "technical"
    assert "super-secret-token" not in str(context)


def test_logging_middleware_allows_request_flow() -> None:
    app = FastAPI()
    app.state.scrub_mode = "strict"
    app.middleware("http")(log_request_response)

    @app.get("/health")
    def health():
        return Response(content="ok", status_code=200)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.text == "ok"

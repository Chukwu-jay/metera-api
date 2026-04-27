from fastapi.testclient import TestClient

from app.cache.exact_cache import ExactCache
from app.core.dependencies import get_exact_cache
from app.main import app
from app.models.api import ChatCompletionResponse, Choice, ChoiceMessage
from app.services.proxy_service import ProxyService
from app.storage.memory import InMemoryKVStore


class StreamingProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="non-stream-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="ok"))],
        )

    async def create_chat_completion_stream(self, *, request, bearer_token=None):
        async def _stream():
            yield b"data: {\"id\":\"chunk-1\"}\n\n"
            yield b"data: [DONE]\n\n"

        return _stream()


class StreamingProxyService(ProxyService):
    def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
        super().__init__(settings=settings, provider=provider or StreamingProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)


def test_streaming_chat_route_returns_sse(monkeypatch) -> None:
    app.dependency_overrides[get_exact_cache] = lambda: ExactCache(InMemoryKVStore())
    monkeypatch.setattr("app.api.routes_chat.ProxyService", StreamingProxyService)

    client = TestClient(app)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"x-metera-namespace": "tenant-stream"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello stream"}],
            "stream": True,
        },
    ) as response:
        body = b"".join(response.iter_bytes())

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert b"chunk-1" in body
    assert b"[DONE]" in body

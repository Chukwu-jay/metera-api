from fastapi.testclient import TestClient

from app.cache.exact_cache import ExactCache
from app.core.config import get_settings
from app.core.dependencies import get_exact_cache
from app.main import app
from app.models.api import ChatCompletionResponse, Choice, ChoiceMessage
from app.services.proxy_service import ProxyService
from app.storage.memory import InMemoryKVStore


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="smoke-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="smoke ok"))],
        )


class SmokeProxyService(ProxyService):
    def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
        super().__init__(settings=settings, provider=provider or FakeProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)


def test_chat_passthrough_smoke(monkeypatch) -> None:
    settings = get_settings()
    app.dependency_overrides[get_exact_cache] = lambda: ExactCache(InMemoryKVStore())
    monkeypatch.setattr("app.api.routes_chat.ProxyService", SmokeProxyService)

    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        headers={"x-metera-namespace": "tenant-smoke"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Greetings smoke"}],
            "stream": False,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "gpt-4o-mini"
    assert body["choices"][0]["message"]["content"] == "smoke ok"
    assert body["metera"]["namespace"] == "tenant-smoke"

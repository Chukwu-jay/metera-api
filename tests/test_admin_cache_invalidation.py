from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_admin import router
from app.cache.exact_cache import ExactCache
from app.core.dependencies import get_exact_cache
from app.models.api import ChatCompletionResponse, Choice, ChoiceMessage
from app.services.proxy_service import ProxyService
from app.storage.memory import InMemoryKVStore


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id="fake-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="ok"))],
        )

    async def create_chat_completion_stream(self, *, request, bearer_token=None):
        async def _stream():
            yield b"data: [DONE]\n\n"

        return _stream()


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.exact_cache = ExactCache(InMemoryKVStore())
    return app


def test_admin_cache_invalidation_rejects_cross_namespace_request(monkeypatch) -> None:
    app = build_test_app()

    class TestProxyService(ProxyService):
        def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
            super().__init__(settings=settings, provider=provider or FakeProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)

    monkeypatch.setattr("app.api.routes_admin.ProxyService", TestProxyService)

    client = TestClient(app)
    response = client.post(
        "/admin/cache/invalidate",
        headers={"x-metera-namespace": "tenant-a"},
        json={"namespace": "tenant-b"},
    )

    assert response.status_code == 403


def test_admin_cache_invalidation_rejects_invalid_namespace(monkeypatch) -> None:
    app = build_test_app()

    class TestProxyService(ProxyService):
        def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
            super().__init__(settings=settings, provider=provider or FakeProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)

    monkeypatch.setattr("app.api.routes_admin.ProxyService", TestProxyService)

    client = TestClient(app)
    response = client.post(
        "/admin/cache/invalidate",
        headers={"x-metera-namespace": "tenant-a"},
        json={"namespace": "tenant/a"},
    )

    assert response.status_code == 400


def test_admin_cache_invalidation_returns_namespace_scoped_counts(monkeypatch) -> None:
    app = build_test_app()

    class TestProxyService(ProxyService):
        def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
            super().__init__(settings=settings, provider=provider or FakeProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)

    monkeypatch.setattr("app.api.routes_admin.ProxyService", TestProxyService)

    client = TestClient(app)
    response = client.post(
        "/admin/cache/invalidate",
        headers={"x-metera-namespace": "tenant-a"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["namespace"] == "tenant-a"
    assert "exact_cache_deleted" in response.json()
    assert "semantic_cache_deleted" in response.json()

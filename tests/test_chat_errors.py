from fastapi.testclient import TestClient

from app.cache.exact_cache import ExactCache
from app.core.dependencies import get_exact_cache
from app.main import app
from app.providers.errors import UpstreamProviderError
from app.services.proxy_service import ProxyService
from app.storage.memory import InMemoryKVStore


class ErrorProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        raise UpstreamProviderError(message="Upstream provider timed out", status_code=504, retryable=True)


class ErrorProxyService(ProxyService):
    def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
        super().__init__(settings=settings, provider=provider or ErrorProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)


def test_chat_route_normalizes_upstream_error(monkeypatch) -> None:
    app.dependency_overrides[get_exact_cache] = lambda: ExactCache(InMemoryKVStore())
    monkeypatch.setattr("app.api.routes_chat.ProxyService", ErrorProxyService)

    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        headers={"x-metera-namespace": "tenant-a"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 504
    assert response.json()["detail"]["message"] == "Upstream provider timed out"
    assert response.json()["detail"]["retryable"] is True

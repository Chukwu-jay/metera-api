from fastapi.testclient import TestClient

from app.cache.exact_cache import ExactCache
from app.core.dependencies import get_exact_cache, get_proxy_service
from app.main import app
from app.models.api import ChatCompletionResponse, Choice, ChoiceMessage
from app.services.proxy_service import ProxyService
from app.storage.memory import InMemoryKVStore


class FakeProvider:
    def __init__(self) -> None:
        self.last_bearer_token = None

    async def create_chat_completion(self, *, request, bearer_token=None):
        self.last_bearer_token = bearer_token
        return ChatCompletionResponse(
            id="identity-1",
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content="identity ok"))],
        )


class IdentityProxyService(ProxyService):
    def __init__(self, settings, provider=None, exact_cache=None, semantic_cache=None) -> None:
        super().__init__(settings=settings, provider=provider or FakeProvider(), exact_cache=exact_cache, semantic_cache=semantic_cache)


class ResolverHit:
    tenant_id = "tenant_123"
    tenant_slug = "acme"
    workspace_id = "workspace_456"
    workspace_slug = "prod-assistant"
    environment_id = "env_789"
    environment_name = "prod"
    api_key_id = "key_abc"
    api_key_prefix = "mk_live"
    api_key_display_name = "Primary Key"


class FakeResolver:
    def __init__(self, resolved):
        self._resolved = resolved

    async def resolve(self, presented_key: str | None):
        if presented_key == "good-key":
            return self._resolved
        return None


def _settings(*, controlplane_identity_enabled: bool = False):
    return type(
        "S",
        (),
        {
            "upstream_base_url": "https://example.com",
            "upstream_api_key": None,
            "upstream_timeout_seconds": 5.0,
            "default_exact_ttl_seconds": 60,
            "semantic_enabled": False,
            "namespace_header": "x-metera-namespace",
            "controlplane_identity_enabled": controlplane_identity_enabled,
        },
    )()


def _install_identity_test_service(*, controlplane_identity_enabled: bool = False) -> FakeProvider:
    exact_cache = ExactCache(InMemoryKVStore())
    provider = FakeProvider()
    app.dependency_overrides[get_exact_cache] = lambda: exact_cache
    app.dependency_overrides[get_proxy_service] = lambda: IdentityProxyService(settings=_settings(controlplane_identity_enabled=controlplane_identity_enabled), provider=provider, exact_cache=exact_cache)
    return provider


def test_chat_route_preserves_legacy_behavior_when_identity_disabled() -> None:
    provider = _install_identity_test_service(controlplane_identity_enabled=False)

    client = TestClient(app)
    original_enabled = getattr(app.state, "controlplane_identity_enabled", False)
    original_resolver = getattr(app.state, "identity_resolver", None)
    app.state.controlplane_identity_enabled = False
    app.state.identity_resolver = None

    response = client.post(
        "/v1/chat/completions",
        headers={"x-metera-namespace": "tenant-a"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello legacy"}],
        },
    )

    app.state.controlplane_identity_enabled = original_enabled
    app.state.identity_resolver = original_resolver
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["metera"]["namespace"] == "tenant-a"
    assert body["metera"].get("tenant_id") is None
    assert provider.last_bearer_token is None


def test_chat_route_requires_valid_workspace_key_when_identity_enabled() -> None:
    _install_identity_test_service(controlplane_identity_enabled=True)

    client = TestClient(app)
    original_enabled = getattr(app.state, "controlplane_identity_enabled", False)
    original_resolver = getattr(app.state, "identity_resolver", None)
    app.state.controlplane_identity_enabled = True
    app.state.identity_resolver = FakeResolver(ResolverHit())

    response = client.post(
        "/v1/chat/completions",
        headers={
            "x-metera-namespace": "tenant-a",
            "authorization": "Bearer bad-key",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello secured"}],
        },
    )

    app.state.controlplane_identity_enabled = original_enabled
    app.state.identity_resolver = original_resolver
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid workspace API key"


def test_chat_route_attaches_identity_metadata_when_enabled() -> None:
    provider = _install_identity_test_service(controlplane_identity_enabled=True)

    client = TestClient(app)
    original_enabled = getattr(app.state, "controlplane_identity_enabled", False)
    original_resolver = getattr(app.state, "identity_resolver", None)
    app.state.controlplane_identity_enabled = True
    app.state.identity_resolver = FakeResolver(ResolverHit())

    response = client.post(
        "/v1/chat/completions",
        headers={
            "x-metera-namespace": "tenant-a",
            "authorization": "Bearer good-key",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello secured"}],
        },
    )

    app.state.controlplane_identity_enabled = original_enabled
    app.state.identity_resolver = original_resolver
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["metera"]["namespace"] == "tenant-a"
    assert body["metera"]["tenant_id"] == "tenant_123"
    assert body["metera"]["workspace_id"] == "workspace_456"
    assert body["metera"]["api_key_id"] == "key_abc"
    assert provider.last_bearer_token is None


def test_chat_route_derives_namespace_when_header_missing_and_identity_enabled() -> None:
    _install_identity_test_service(controlplane_identity_enabled=True)

    client = TestClient(app)
    original_enabled = getattr(app.state, "controlplane_identity_enabled", False)
    original_resolver = getattr(app.state, "identity_resolver", None)
    app.state.controlplane_identity_enabled = True
    app.state.identity_resolver = FakeResolver(ResolverHit())

    response = client.post(
        "/v1/chat/completions",
        headers={
            "authorization": "Bearer good-key",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello derived namespace"}],
        },
    )

    app.state.controlplane_identity_enabled = original_enabled
    app.state.identity_resolver = original_resolver
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["metera"]["namespace"] == "acme-prod-assistant"
    assert body["metera"]["tenant_id"] == "tenant_123"
    assert body["metera"]["workspace_id"] == "workspace_456"

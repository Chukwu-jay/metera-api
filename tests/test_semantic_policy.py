from app.models.api import ChatCompletionRequest, ChatMessage
from app.services.proxy_service import _semantic_reuse_allowed


def test_semantic_reuse_disabled_by_setting() -> None:
    settings = type("S", (), {"semantic_enabled": False, "semantic_max_temperature": 0.2})()
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hello")])
    allowed, reason = _semantic_reuse_allowed(request=request, settings=settings)
    assert allowed is False
    assert reason == "semantic_disabled"


def test_semantic_reuse_disabled_for_streaming() -> None:
    settings = type("S", (), {"semantic_enabled": True, "semantic_max_temperature": 0.2})()
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hello")], stream=True)
    allowed, reason = _semantic_reuse_allowed(request=request, settings=settings)
    assert allowed is False
    assert reason == "streaming_request"


def test_semantic_reuse_disabled_for_high_temperature() -> None:
    settings = type("S", (), {"semantic_enabled": True, "semantic_max_temperature": 0.2})()
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hello")], temperature=0.9)
    allowed, reason = _semantic_reuse_allowed(request=request, settings=settings)
    assert allowed is False
    assert reason == "temperature_above_threshold"

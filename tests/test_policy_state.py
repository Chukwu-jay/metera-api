import json

from app.core.policy_state import DEFAULT_POLICY_STATE, PRODUCTION_POLICY_DEFAULTS, _decode_json_object
from app.services.proxy_service import _semantic_reuse_allowed
from app.core.config import Settings
from app.models.api import ChatCompletionRequest, ChatMessage


def test_policy_defaults_include_shadow_threshold() -> None:
    assert DEFAULT_POLICY_STATE["semantic_shadow_threshold"] is None
    assert PRODUCTION_POLICY_DEFAULTS["semantic_threshold"] == 0.9
    assert PRODUCTION_POLICY_DEFAULTS["semantic_shadow_threshold"] == 0.8



def test_policy_decode_json_object_accepts_string_payload() -> None:
    payload = {"semantic_threshold": 0.9, "semantic_shadow_threshold": 0.8}
    assert _decode_json_object(json.dumps(payload)) == payload



def test_semantic_reuse_allowed_respects_policy_overrides() -> None:
    settings = Settings()
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.0,
        stream=False,
    )
    allowed, reason = _semantic_reuse_allowed(
        request=request,
        settings=settings,
        overrides={"semantic_enabled": False, "semantic_max_temperature": 0.2},
    )
    assert allowed is False
    assert reason == "semantic_disabled"



def test_semantic_reuse_allowed_respects_override_temperature() -> None:
    settings = Settings()
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="hello")],
        temperature=0.3,
        stream=False,
    )
    allowed, reason = _semantic_reuse_allowed(
        request=request,
        settings=settings,
        overrides={"semantic_enabled": True, "semantic_max_temperature": 0.25},
    )
    assert allowed is False
    assert reason == "temperature_above_threshold"

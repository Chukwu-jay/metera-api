import asyncio
from types import SimpleNamespace

from app.models.api import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, Choice, ChoiceMessage
from app.models.domain import ProxyContext
from app.services.proxy_service import ProxyService


class FakeProvider:
    async def create_chat_completion(self, *, request, bearer_token=None):
        return ChatCompletionResponse(
            id='upstream-1',
            model=request.model,
            choices=[Choice(message=ChoiceMessage(content='upstream response'))],
        )


class StubSemanticHit:
    def __init__(self, payload, metadata, similarity=0.99):
        self.payload = payload
        self.metadata = metadata
        self.similarity = similarity


class StubSemanticCache:
    def __init__(self, hit=None):
        self.hit = hit
        self.store = type('Store', (), {'invalidate_namespace': staticmethod(lambda namespace: 0)})()

    async def find_match(self, **kwargs):
        return self.hit

    async def add_entry(self, **kwargs):
        return None


class StubShadowStore:
    def __init__(self):
        self.calls = []

    async def log_shadow_regression_alert(self, **kwargs):
        self.calls.append(kwargs)


async def main():
    settings = SimpleNamespace(
        upstream_base_url='https://example.com',
        upstream_api_key=None,
        upstream_timeout_seconds=5.0,
        upstream_max_retries=1,
        default_exact_ttl_seconds=60,
        default_semantic_ttl_seconds=60,
        semantic_threshold=0.95,
        semantic_shadow_threshold=0.8,
        semantic_max_temperature=0.2,
        semantic_enabled=True,
        dual_mode_enabled=True,
        semantic_model_name='fake-local',
        semantic_disabled_namespace_prefixes='browser-,agent-,workflow-',
        dlp_enabled=False,
        dlp_scrub_level='off',
        dlp_analyzer_mode='regex',
        dlp_detect_email=None,
        dlp_detect_phone=None,
        dlp_detect_ip=None,
        dlp_detect_secrets=None,
        dlp_custom_detectors_json=None,
        dlp_custom_detectors_yaml_path=None,
    )
    hit_payload = ChatCompletionResponse(
        id='cached-1',
        model='gpt-4o-mini',
        choices=[Choice(message=ChoiceMessage(content='cached response'))],
    ).model_dump()
    semantic_cache = StubSemanticCache(
        hit=StubSemanticHit(
            payload=hit_payload,
            metadata={
                'intent': 'chat_generic',
                'module': None,
                'entity_fingerprint': 'wrong',
                'has_visual_context': False,
                'has_dom_context': False,
                'is_agentic': False,
            },
        )
    )
    shadow_store = StubShadowStore()
    service = ProxyService(settings=settings, provider=FakeProvider(), semantic_cache=semantic_cache, shadow_analytics_store=shadow_store)
    request = ChatCompletionRequest(model='gpt-4o-mini', messages=[ChatMessage(role='user', content='What is the refund status for invoice INV-1002 for Acme South?')])
    response = await service.handle_chat_completion(request=request, context=ProxyContext(namespace='faq-billing'))
    print({'cache': response.metera.get('cache'), 'bypass': response.metera.get('semantic_bypass_reason'), 'shadow_calls': len(shadow_store.calls), 'shadow_reason': shadow_store.calls[0]['rejection_reason'] if shadow_store.calls else None})


asyncio.run(main())

import pytest

from app.models.api import ChatCompletionRequest, ChatMessage
from app.providers.errors import UpstreamProviderError
from app.providers.openai_compatible import OpenAICompatibleProvider


class TimeoutProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(base_url="https://example.com", timeout_seconds=0.1, max_retries=1)
        self.calls = 0

    async def create_chat_completion(self, *, request, bearer_token=None):
        self.calls += 1
        if self.calls < 2:
            raise UpstreamProviderError(message="Upstream provider timed out", status_code=504, retryable=True)
        raise UpstreamProviderError(message="Upstream provider timed out", status_code=504, retryable=False)


class ClientErrorProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(base_url="https://example.com", timeout_seconds=0.1, max_retries=1)

    async def create_chat_completion(self, *, request, bearer_token=None):
        raise UpstreamProviderError(message="Upstream provider request error: 400", status_code=502, retryable=False)


@pytest.mark.asyncio
async def test_upstream_provider_error_carries_retryability() -> None:
    provider = ClientErrorProvider()
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")])

    with pytest.raises(UpstreamProviderError) as exc:
        await provider.create_chat_completion(request=request)

    assert exc.value.status_code == 502
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_retryable_upstream_provider_error_is_distinct() -> None:
    provider = TimeoutProvider()
    request = ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")])

    with pytest.raises(UpstreamProviderError) as exc:
        await provider.create_chat_completion(request=request)

    assert exc.value.status_code == 504

from typing import AsyncIterator, Protocol

from app.models.api import ChatCompletionRequest, ChatCompletionResponse


class ChatProvider(Protocol):
    async def create_chat_completion(
        self,
        *,
        request: ChatCompletionRequest,
        bearer_token: str | None = None,
    ) -> ChatCompletionResponse: ...

    async def create_chat_completion_stream(
        self,
        *,
        request: ChatCompletionRequest,
        bearer_token: str | None = None,
    ) -> AsyncIterator[bytes]: ...

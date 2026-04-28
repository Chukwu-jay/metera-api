from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

MAX_ERROR_BODY_CHARS = 1000

from app.models.api import ChatCompletionRequest, ChatCompletionResponse
from app.providers.errors import UpstreamProviderError


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def create_chat_completion(
        self,
        *,
        request: ChatCompletionRequest,
        bearer_token: str | None = None,
    ) -> ChatCompletionResponse:
        headers = self._build_headers(bearer_token)
        attempts = self.max_retries + 1
        last_error: UpstreamProviderError | None = None

        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        json=request.model_dump(exclude_none=True),
                        headers=headers,
                    )
                if response.status_code >= 500:
                    raise UpstreamProviderError(
                        message=_build_upstream_error_message("server", response),
                        status_code=502,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise UpstreamProviderError(
                        message=_build_upstream_error_message("request", response),
                        status_code=502,
                        retryable=False,
                    )
                payload: dict[str, Any] = response.json()
                return ChatCompletionResponse.model_validate(payload)
            except httpx.TimeoutException:
                last_error = UpstreamProviderError(message="Upstream provider timed out", status_code=504, retryable=True)
            except httpx.HTTPError as exc:
                last_error = UpstreamProviderError(message=f"Upstream provider transport error: {exc.__class__.__name__}", status_code=502, retryable=True)
            except UpstreamProviderError as exc:
                last_error = exc

            if last_error is not None and (not last_error.retryable or attempt == attempts - 1):
                raise last_error

        raise UpstreamProviderError(message="Upstream provider request failed", status_code=502, retryable=False)

    async def create_chat_completion_stream(
        self,
        *,
        request: ChatCompletionRequest,
        bearer_token: str | None = None,
    ) -> AsyncIterator[bytes]:
        headers = self._build_headers(bearer_token)
        client = httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            outbound = client.build_request(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=request.model_dump(exclude_none=True),
                headers=headers,
            )
            response = await client.send(outbound, stream=True)
            if response.status_code >= 500:
                error_body = await response.aread()
                await response.aclose()
                raise UpstreamProviderError(
                    message=_build_upstream_error_message("server", response, body_bytes=error_body),
                    status_code=502,
                    retryable=True,
                )
            if response.status_code >= 400:
                error_body = await response.aread()
                await response.aclose()
                raise UpstreamProviderError(
                    message=_build_upstream_error_message("request", response, body_bytes=error_body),
                    status_code=502,
                    retryable=False,
                )

            async def _iterator() -> AsyncIterator[bytes]:
                try:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
                finally:
                    await response.aclose()
                    await client.aclose()

            return _iterator()
        except httpx.TimeoutException as exc:
            await client.aclose()
            raise UpstreamProviderError(message="Upstream provider timed out", status_code=504, retryable=True) from exc
        except httpx.HTTPError as exc:
            await client.aclose()
            raise UpstreamProviderError(message=f"Upstream provider transport error: {exc.__class__.__name__}", status_code=502, retryable=True) from exc
        except Exception:
            await client.aclose()
            raise

    def _build_headers(self, bearer_token: str | None) -> dict[str, str]:
        token = bearer_token or self.api_key
        headers = {"content-type": "application/json"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        return headers


def _build_upstream_error_message(kind: str, response: httpx.Response, body_bytes: bytes | None = None) -> str:
    body_text = _extract_error_body_text(response, body_bytes=body_bytes)
    suffix = f" body={body_text}" if body_text else ""
    return f"Upstream provider {kind} error: {response.status_code}{suffix}"


def _extract_error_body_text(response: httpx.Response, body_bytes: bytes | None = None) -> str:
    raw = body_bytes if body_bytes is not None else response.content
    if not raw:
        return ""
    try:
        text = raw.decode(response.encoding or "utf-8", errors="replace").strip()
    except Exception:
        text = raw.decode("utf-8", errors="replace").strip()
    if len(text) > MAX_ERROR_BODY_CHARS:
        text = text[:MAX_ERROR_BODY_CHARS] + "..."
    return text

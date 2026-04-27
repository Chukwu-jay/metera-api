from __future__ import annotations


class UpstreamProviderError(Exception):
    def __init__(self, *, message: str, status_code: int = 502, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable

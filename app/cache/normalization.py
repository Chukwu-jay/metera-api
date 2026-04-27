from __future__ import annotations

import hashlib
import json

from app.models.api import ChatCompletionRequest


def canonicalize_request(request: ChatCompletionRequest) -> str:
    payload = {
        "model": request.model,
        "messages": [{"role": message.role, "content": message.content} for message in request.messages],
        "temperature": request.temperature,
        "stream": request.stream,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_exact_hash(*, namespace: str, endpoint: str, normalized_text: str) -> str:
    value = f"{namespace}:{endpoint}:{normalized_text}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_exact_cache_key(*, namespace: str, exact_hash: str) -> str:
    return f"{namespace}:{exact_hash}"

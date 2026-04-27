from __future__ import annotations

import logging
from time import perf_counter

from fastapi import Request

logger = logging.getLogger("metera.request")
SAFE_REQUEST_HEADERS = frozenset({"x-metera-namespace", "content-type", "user-agent"})
SENSITIVE_HEADERS = frozenset({"authorization", "x-metera-admin-key", "proxy-authorization", "cookie", "set-cookie"})



def build_request_log_context(*, request: Request, status_code: int, duration_ms: float) -> dict[str, object]:
    namespace = request.headers.get("x-metera-namespace") or "default"
    return {
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "namespace": namespace,
        "safe_headers": {
            key: request.headers.get(key)
            for key in SAFE_REQUEST_HEADERS
            if request.headers.get(key)
        },
        "sensitive_headers_present": {
            key: bool(request.headers.get(key))
            for key in SENSITIVE_HEADERS
            if request.headers.get(key) is not None
        },
        "scrub_mode": getattr(request.app.state, "scrub_mode", "technical"),
    }


async def log_request_response(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started) * 1000.0
    logger.info("metera_request", extra={"metera": build_request_log_context(request=request, status_code=response.status_code, duration_ms=duration_ms)})
    return response

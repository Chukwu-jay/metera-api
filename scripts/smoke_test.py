from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000")
NAMESPACE = os.getenv("METERA_NAMESPACE", "smoke-test")
API_KEY = os.getenv("METERA_API_KEY") or os.getenv("METERA_CONTROLPLANE_STATIC_API_KEY")
WAIT_TIMEOUT_SECONDS = float(os.getenv("METERA_SMOKE_WAIT_TIMEOUT_SECONDS", "120"))
WAIT_INTERVAL_SECONDS = float(os.getenv("METERA_SMOKE_WAIT_INTERVAL_SECONDS", "2"))


def main() -> int:
    health = _wait_for_health(timeout_seconds=WAIT_TIMEOUT_SECONDS, interval_seconds=WAIT_INTERVAL_SECONDS)
    if health is None:
        print(f"FAIL: /health did not become ready within {WAIT_TIMEOUT_SECONDS:.0f}s")
        return 1
    if health.get("status") != "ok":
        print("FAIL: /health did not return ok")
        return 1

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello from smoke test"}],
        "stream": False,
    }
    response = _post_json(
        f"{BASE_URL}/v1/chat/completions",
        payload,
        headers=_auth_headers({"x-metera-namespace": NAMESPACE}),
    )
    if response.get("model") != "gpt-4o-mini":
        print("FAIL: unexpected chat response model")
        return 1
    if "choices" not in response:
        print("FAIL: chat response missing choices")
        return 1

    stats = _get_json(f"{BASE_URL}/stats/summary")
    if "requests" not in stats:
        print("FAIL: /stats/summary missing requests block")
        return 1

    print("PASS: Metera smoke test completed")
    print(json.dumps({"health": health["status"], "namespace": NAMESPACE}, indent=2))
    return 0


def _wait_for_health(*, timeout_seconds: float, interval_seconds: float) -> dict | None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            health = _get_json(f"{BASE_URL}/health")
            if health.get("status") == "ok":
                return health
        except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError) as exc:
            last_error = exc
        time.sleep(interval_seconds)
    if last_error is not None:
        print(f"Last healthcheck error: {last_error}", file=sys.stderr)
    return None


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _auth_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(headers or {})
    if API_KEY:
        merged["authorization"] = f"Bearer {API_KEY}"
    return merged


if __name__ == "__main__":
    raise SystemExit(main())

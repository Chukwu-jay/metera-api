from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000")
NAMESPACE = os.getenv("METERA_NAMESPACE", f"semantic-demo-{uuid.uuid4().hex[:8]}")
WAIT_TIMEOUT_SECONDS = float(os.getenv("METERA_SMOKE_WAIT_TIMEOUT_SECONDS", "120"))
WAIT_INTERVAL_SECONDS = float(os.getenv("METERA_SMOKE_WAIT_INTERVAL_SECONDS", "2"))


def main() -> int:
    health = _wait_for_health(timeout_seconds=WAIT_TIMEOUT_SECONDS, interval_seconds=WAIT_INTERVAL_SECONDS)
    if health is None or health.get("status") != "ok":
        print("FAIL: app did not become healthy")
        return 1

    original_prompt = (
        "A homeowner in Ontario is stuck with the most annoying part of winter driveway cleanup. "
        "After the city plow clears the road, a heavy ridge of packed snow still blocks the mouth of the driveway, "
        "and there is stubborn snow jammed around parked cars near the garage. "
        "The person does not want a tractor or a giant commercial blower. "
        "They want a compact autonomous snow-clearing robot that can reliably finish the messy last twenty percent: "
        "the curb berm, the edges of the driveway, and the hard-to-reach snow around vehicles. "
        "Explain the practical job to be done and why that leftover cleanup is such a painful homeowner problem."
    )
    paraphrased_prompt = (
        "An Ontario homeowner keeps running into the same winter driveway problem. "
        "The street gets plowed, but a dense pile of packed snow is left across the driveway entrance, "
        "and more snow stays trapped around parked cars beside the garage. "
        "They are not asking for a tractor-sized machine or a commercial snow system. "
        "What they want is a small self-driving snow robot that consistently handles the frustrating final twenty percent: "
        "the berm at the curb, the driveway edges, and the snow that is awkward to remove around vehicles. "
        "Explain the real job to be done and why homeowners hate this leftover cleanup so much."
    )

    first = _post_json(
        f"{BASE_URL}/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": original_prompt}],
            "stream": False,
            "temperature": 0.0,
        },
        headers={"x-metera-namespace": NAMESPACE},
    )
    second = _post_json(
        f"{BASE_URL}/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": paraphrased_prompt}],
            "stream": False,
            "temperature": 0.0,
        },
        headers={"x-metera-namespace": NAMESPACE},
    )

    if first.get("metera", {}).get("cache") != "miss":
        print("FAIL: first request was expected to be a miss")
        print(json.dumps(first, indent=2))
        return 1
    if second.get("metera", {}).get("cache") != "semantic_hit":
        print("FAIL: second request was expected to be a semantic hit")
        print(json.dumps(second, indent=2))
        return 1

    print("PASS: semantic demo proved semantic hit after paraphrased miss")
    print(
        json.dumps(
            {
                "namespace": NAMESPACE,
                "first_cache": first.get("metera", {}).get("cache"),
                "second_cache": second.get("metera", {}).get("cache"),
                "second_similarity": second.get("metera", {}).get("semantic_similarity"),
                "request_id": second.get("metera", {}).get("request_id"),
            },
            indent=2,
        )
    )
    return 0


def _wait_for_health(*, timeout_seconds: float, interval_seconds: float) -> dict | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            health = _get_json(f"{BASE_URL}/health")
            if health.get("status") == "ok":
                return health
        except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError):
            pass
        time.sleep(interval_seconds)
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


if __name__ == "__main__":
    raise SystemExit(main())

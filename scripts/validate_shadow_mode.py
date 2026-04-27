from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid

BASE_URL = os.getenv("METERA_BASE_URL", "http://127.0.0.1:8000")
NAMESPACE = os.getenv("METERA_NAMESPACE", f"shadow-demo-{uuid.uuid4().hex[:8]}")
ADMIN_KEY = os.getenv("METERA_ADMIN_API_KEY", "dev-admin-key")
DB_DSN = os.getenv("METERA_POLICY_STORE_DSN", "postgresql://postgres:postgres@localhost:5432/metera")


def main() -> int:
    _post_json(
        f"{BASE_URL}/admin/policy",
        {"semantic_threshold": 0.9, "semantic_shadow_threshold": 0.82},
        headers={"x-metera-admin-key": ADMIN_KEY},
    )

    first_prompt = (
        "Describe this same customer problem in different wording and with a different framing. "
        "In a Canadian suburb, the street is plowed but the homeowner still faces the hardest cleanup afterward: a thick windrow at the end of the driveway, piles of pushed snow near the sidewalk, and frozen buildup surrounding parked vehicles that makes getting out in the morning frustrating and time consuming. "
        "The customer is imagining a self-driving residential snow robot, not a full-size loader, because the real need is precise and repeatable cleanup in tight household spaces. "
        "They want relief from repetitive winter labor, especially the part that happens after the main plowing is done. "
        "Summarize the underlying task, the functional requirements, and the emotional frustration behind the request."
    )
    second_prompt = (
        "Rephrase the same scenario again while preserving the meaning. "
        "The user is a homeowner who does not mind that the road gets cleared by the city, but they hate the leftover mess that remains on private property: the packed ridge at the curb cut, the snow banks that block the driveway entrance, and the stubborn accumulation around parked cars that is difficult to reach with a shovel or a traditional snowblower. "
        "They are interested in an autonomous driveway robot because the problem is not just moving snow in general, it is handling the annoying final twenty percent of cleanup that is most inconsistent, most tiring, and most likely to be ignored until it becomes a bigger inconvenience. "
        "Explain the practical use case and why a purpose-built household robot could be compelling here."
    )

    first = _chat(first_prompt)
    second = _chat(second_prompt)

    if first.get("metera", {}).get("cache") != "miss":
        print("FAIL: first request should be a miss that indexes a semantic candidate")
        print(json.dumps(first, indent=2))
        return 1
    if second.get("metera", {}).get("cache") != "miss":
        print("FAIL: second request should still miss at the live threshold 0.9")
        print(json.dumps(second, indent=2))
        return 1

    request_id = second.get("metera", {}).get("request_id")
    if not request_id:
        print("FAIL: second request did not return request_id metadata")
        return 1

    analytics_row = _wait_for_shadow_log(request_id=request_id, timeout_seconds=20)
    if analytics_row is None:
        print("FAIL: no shadow analytics row was recorded")
        return 1

    similarity = float(analytics_row["similarity_score"])
    if not (0.82 <= similarity < 0.9):
        print("FAIL: shadow similarity was outside the expected range")
        print(json.dumps(analytics_row, indent=2))
        return 1

    print("PASS: live miss recorded shadow hit analytics")
    print(
        json.dumps(
            {
                "namespace": NAMESPACE,
                "request_id": request_id,
                "second_cache": second.get("metera", {}).get("cache"),
                "shadow_similarity": similarity,
                "calculated_savings_usd": analytics_row["calculated_savings_usd"],
            },
            indent=2,
        )
    )
    return 0


def _chat(prompt: str) -> dict:
    return _post_json(
        f"{BASE_URL}/v1/chat/completions",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.0,
        },
        headers={"x-metera-namespace": NAMESPACE},
    )


def _wait_for_shadow_log(*, request_id: str, timeout_seconds: int) -> dict | None:
    import subprocess

    deadline = time.monotonic() + timeout_seconds
    sql = (
        "SELECT request_id, similarity_score, calculated_savings_usd "
        "FROM semantic_shadow_analytics "
        f"WHERE request_id = '{request_id}' ORDER BY created_at DESC LIMIT 1;"
    )
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "metera-pgvector",
                "psql",
                "-U",
                "postgres",
                "-d",
                "metera",
                "-At",
                "-F",
                "|",
                "-c",
                sql,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        line = result.stdout.strip()
        if line:
            parts = line.split("|")
            if len(parts) == 3:
                return {
                    "request_id": parts[0],
                    "similarity_score": float(parts[1]),
                    "calculated_savings_usd": float(parts[2]),
                }
        time.sleep(1)
    return None


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

from __future__ import annotations

import sys

from scripts import demo_semantic_hit


def test_demo_semantic_hit_defaults_to_hardened_shadow_expectation(monkeypatch, capsys):
    responses = [
        {"metera": {"cache": "miss"}},
        {
            "metera": {
                "cache": "miss",
                "semantic_bypass_reason": "shadow_regression_alert",
                "request_id": "req_123",
            }
        },
    ]

    monkeypatch.setattr(sys, "argv", ["demo_semantic_hit.py"])
    monkeypatch.setattr(demo_semantic_hit, "_wait_for_health", lambda **_: {"status": "ok"})
    monkeypatch.setattr(demo_semantic_hit, "_post_json", lambda *_, **__: responses.pop(0))

    assert demo_semantic_hit.main() == 0
    assert "hardened posture blocks live paraphrase reuse" in capsys.readouterr().out


def test_demo_semantic_hit_can_expect_live_hit_for_permissive_policy(monkeypatch, capsys):
    responses = [
        {"metera": {"cache": "miss"}},
        {
            "metera": {
                "cache": "semantic_hit",
                "semantic_similarity": 0.94,
                "request_id": "req_456",
            }
        },
    ]

    monkeypatch.setattr(sys, "argv", ["demo_semantic_hit.py", "--expect-live-hit"])
    monkeypatch.setattr(demo_semantic_hit, "_wait_for_health", lambda **_: {"status": "ok"})
    monkeypatch.setattr(demo_semantic_hit, "_post_json", lambda *_, **__: responses.pop(0))

    assert demo_semantic_hit.main() == 0
    assert "live semantic reuse" in capsys.readouterr().out


def test_demo_semantic_hit_fails_when_hardened_policy_serves_live_hit(monkeypatch):
    responses = [
        {"metera": {"cache": "miss"}},
        {"metera": {"cache": "semantic_hit"}},
    ]

    monkeypatch.setattr(sys, "argv", ["demo_semantic_hit.py"])
    monkeypatch.setattr(demo_semantic_hit, "_wait_for_health", lambda **_: {"status": "ok"})
    monkeypatch.setattr(demo_semantic_hit, "_post_json", lambda *_, **__: responses.pop(0))

    assert demo_semantic_hit.main() == 1

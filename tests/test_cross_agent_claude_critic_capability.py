from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_claude_capability_plan_is_one_call_tool_free_and_hash_pinned() -> None:
    plan = _object(EXPERIMENT / "claude-critic-capability-001-plan.json")
    series_002 = _object(EXPERIMENT / "critic-transport-series-002-plan.json")
    candidate = next(
        item
        for item in series_002["candidates"]
        if item["candidate_id"] == "refactor-baseline-v1"
    )

    assert plan["status"] == "ready"
    assert plan["call_budget"]["maximum_calls"] == 1
    assert plan["call_budget"]["automatic_retries"] == 0
    assert plan["provider_controls"]["tool_mode"] == "none"
    assert plan["provider_controls"]["network_access"] is False
    assert plan["candidate"]["candidate_workspace_tree_sha256"] == candidate[
        "candidate_workspace_tree_sha256"
    ]


def test_claude_auth_checkpoint_is_sanitized() -> None:
    checkpoint = _object(
        EXPERIMENT
        / "runs"
        / "claude-critic-capability-001"
        / "auth-checkpoint-before-01.json"
    )
    rendered = json.dumps(checkpoint)

    assert checkpoint["logged_in"] is True
    assert checkpoint["subscription_type"] == "pro"
    assert "email" not in rendered.lower()
    assert "org" not in rendered.lower()

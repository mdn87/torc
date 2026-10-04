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

    assert plan["status"] == "blocked_by_organization_policy"
    assert plan["call_budget"]["maximum_calls"] == 1
    assert plan["call_budget"]["automatic_retries"] == 0
    assert plan["provider_controls"]["tool_mode"] == "none"
    assert plan["provider_controls"]["network_access"] is False
    assert plan["candidate"]["candidate_workspace_tree_sha256"] == candidate[
        "candidate_workspace_tree_sha256"
    ]
    assert plan["outcome"]["attempts"] == 1
    assert plan["outcome"]["inference_calls"] == 0
    assert plan["outcome"]["retry_allowed"] is False


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


def test_claude_policy_rejection_preserves_zero_usage() -> None:
    run_dir = (
        EXPERIMENT
        / "runs"
        / "claude-critic-capability-001"
        / "01-refactor-compact"
    )
    disposition = _object(run_dir / "disposition.json")
    worker = _object(run_dir / "phases" / "01-critic" / "worker-run.json")

    assert disposition["reason_code"] == "oauth_not_allowed_for_organization"
    assert disposition["model_inference_occurred"] is False
    assert disposition["retry_allowed"] is False
    assert worker["exit_status"] == 1
    assert worker["usage"]["input_tokens"] == 0
    assert worker["usage"]["output_tokens"] == 0

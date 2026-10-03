from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_replay as replay  # noqa: E402
import workflow_runner as workflow  # noqa: E402

SOURCE_RUN = (
    EXPERIMENT
    / "runs"
    / "smoke-001"
    / "22-design-cutover-codex-artifact-review-compact"
)


def _record() -> dict[str, Any]:
    return {
        "provider": "codex",
        "role": "critic",
        "tool_mode": "none",
        "session": {
            "mode": "fresh-ephemeral",
            "requested_id": None,
            "observed_id": "critic-session",
        },
        "usage": {
            "schema_version": 1,
            "source": "test",
            "supplied": False,
            "input_tokens": None,
            "cached_input_tokens": None,
            "cache_write_input_tokens": None,
            "reasoning_output_tokens": None,
            "output_tokens": None,
            "reported_fields": [],
            "unreported_fields": [],
            "provider_usage": {},
        },
        "timing": {
            "startup_ms": 1.0,
            "time_to_first_output_ms": 2.0,
            "completion_ms": 3.0,
        },
    }


def test_replay_plan_is_one_call_and_does_not_create_output(tmp_path: Path) -> None:
    plan = replay.replay_plan(
        manifest=workflow.load_manifest(),
        fixture_id="design-cutover-plan",
        source_run=SOURCE_RUN,
        critic_provider="codex",
        critic_context=workflow.FULL_CRITIC_CONTEXT,
    )

    assert plan["model_call_count"] == 1
    assert plan["source_run_id"] == SOURCE_RUN.name
    assert plan["critic_context"] == workflow.FULL_CRITIC_CONTEXT
    assert list(tmp_path.iterdir()) == []


def test_replay_reconstructs_exact_candidate_and_calls_only_critic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(workflow, "_apparatus_revision", lambda: "d" * 40)

    def fake_worker(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True)
        event = {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": json.dumps(
                    {"schema_version": 1, "verdict": "approve", "findings": []}
                ),
            },
        }
        (kwargs["output_dir"] / "stdout.jsonl").write_text(
            json.dumps(event) + "\n", encoding="utf-8"
        )
        return _record()

    monkeypatch.setattr(workflow, "_run_worker", fake_worker)
    result = replay.run_critic_replay(
        manifest=workflow.load_manifest(),
        fixture_id="design-cutover-plan",
        source_run=SOURCE_RUN,
        critic_provider="codex",
        critic_context=workflow.FULL_CRITIC_CONTEXT,
        run_dir=tmp_path / "replay",
    )

    assert len(calls) == 1
    assert calls[0]["role"] == "critic"
    assert "Choose and plan a tenant-store cutover" in calls[0]["prompt"]
    assert result["accepted_final"] is True
    assert result["replay_source_run_id"] == SOURCE_RUN.name
    source = json.loads(
        (tmp_path / "replay" / "source-primary-ref.json").read_text(encoding="utf-8")
    )
    score = json.loads(
        (tmp_path / "replay" / "score-candidate.json").read_text(encoding="utf-8")
    )
    assert score["workspace_tree_sha256"] == source["workspace_tree_sha256"]

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import codex_native_capability as capability  # noqa: E402


def test_capability_probe_is_model_free_ephemeral_and_tool_restricted() -> None:
    probe = capability.build_probe()

    assert probe["execute"] is False
    assert probe["thread_start"]["ephemeral"] is True
    assert probe["thread_start"]["sandbox"] == "read-only"
    assert probe["turn_start"]["sandboxPolicy"] == {
        "type": "readOnly",
        "networkAccess": False,
    }
    assert probe["thread_start"]["environments"] == []
    assert probe["turn_start"]["environments"] == []
    features = probe["thread_start"]["config"]["features"]
    assert features["multi_agent"] is True
    assert all(features[name] is False for name in capability._DISABLED_FEATURES)
    assert probe["thread_start"]["config"]["mcp_servers"] == {}


def test_capability_probe_freezes_one_low_effort_sol_child() -> None:
    probe = capability.build_probe()
    agents = probe["thread_start"]["config"]["agents"]
    prompt = probe["turn_start"]["input"][0]["text"]

    assert probe["thread_start"]["model"] == "gpt-6-sol"
    assert probe["turn_start"]["model"] == "gpt-6-sol"
    assert probe["turn_start"]["effort"] == "low"
    assert agents == {
        "enabled": True,
        "max_concurrent_threads_per_session": 1,
        "default_subagent_model": "gpt-6-sol",
        "default_subagent_reasoning_effort": "low",
    }
    assert "spawn_agent exactly once" in prompt
    assert "fork_turns 'none'" in prompt
    assert "reasoning_effort 'low'" in prompt


def test_capability_probe_uses_pinned_compact_candidate_without_oracle() -> None:
    probe = capability.build_probe()
    prompt = probe["turn_start"]["input"][0]["text"]

    assert "def legacy_route" in prompt
    assert "ARCHITECTURE.md" not in prompt
    assert "oracle.json" not in prompt
    assert "required_defect_areas" not in prompt
    assert probe["critic_payload_bytes"] < probe["root_prompt_bytes"]
    assert len(probe["critic_payload_sha256"]) == 64
    assert len(probe["root_prompt_sha256"]) == 64


def test_capability_probe_launch_disables_surfaces_and_enables_multi_agent() -> None:
    launch = capability.build_probe()["launch"]
    disabled = {
        launch[index + 1]
        for index, value in enumerate(launch[:-1])
        if value == "--disable"
    }

    assert set(capability._DISABLED_FEATURES) <= disabled
    assert launch[launch.index("--enable") + 1] == "multi_agent"
    assert "agents.max_concurrent_threads_per_session=1" in launch
    assert "--strict-config" in launch


def test_capability_plan_matches_current_usage_proceed_evidence() -> None:
    plan = json.loads(
        (EXPERIMENT / "codex-native-capability-001-plan.json").read_text(
            encoding="utf-8"
        )
    )
    checkpoint = json.loads(
        (
            EXPERIMENT
            / "runs"
            / "codex-native-capability-001"
            / "usage-checkpoint-before-04.json"
        ).read_text(encoding="utf-8")
    )

    assert plan["status"] == "ready"
    assert checkpoint["decision"] == "proceed"
    assert checkpoint["primary"]["used_percent"] < plan["call_budget"][
        "stop_threshold_percent"
    ]
    assert checkpoint["reset_credits_consumed"] == 0

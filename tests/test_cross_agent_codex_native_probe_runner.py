from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import codex_native_capability as capability  # noqa: E402
import codex_native_probe_runner as runner  # noqa: E402

ROOT_THREAD = "thr_root"
CHILD_THREAD = "thr_child"
ROOT_TURN = "turn_root"


def _critique() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "verdict": "changes_requested",
        "findings": [
            {
                "finding_id": "f1",
                "severity": "blocking",
                "summary": "Production dispatch still calls legacy_route.",
                "evidence": "routing.py: dispatch and dispatch_batch",
                "claim_ids": ["s1", "c1"],
            },
            {
                "finding_id": "f2",
                "severity": "blocking",
                "summary": "legacy_route duplicates route_request.",
                "evidence": "routing.py: legacy_route should directly delegate",
                "claim_ids": ["d1", "x1"],
            },
        ],
    }


def _usage(thread_id: str, input_tokens: int) -> dict[str, Any]:
    return {
        "method": "thread/tokenUsage/updated",
        "params": {
            "threadId": thread_id,
            "turnId": ROOT_TURN if thread_id == ROOT_THREAD else "turn_child",
            "tokenUsage": {
                "last": {},
                "total": {
                    "inputTokens": input_tokens,
                    "cachedInputTokens": 100,
                    "cacheWriteInputTokens": 0,
                    "outputTokens": 50,
                    "reasoningOutputTokens": 10,
                    "totalTokens": input_tokens + 50,
                },
            },
        },
    }


def _messages() -> list[dict[str, Any]]:
    child_prompt = "critic payload"
    return [
        {
            "method": "thread/started",
            "params": {
                "thread": {
                    "id": CHILD_THREAD,
                    "parentThreadId": ROOT_THREAD,
                }
            },
        },
        {
            "method": "item/completed",
            "params": {
                "threadId": ROOT_THREAD,
                "turnId": ROOT_TURN,
                "item": {
                    "type": "collabAgentToolCall",
                    "id": "spawn",
                    "tool": "spawnAgent",
                    "status": "completed",
                    "senderThreadId": ROOT_THREAD,
                    "receiverThreadIds": [CHILD_THREAD],
                    "model": "gpt-6-sol",
                    "reasoningEffort": "low",
                    "prompt": child_prompt,
                    "agentsStates": {CHILD_THREAD: {"status": "completed"}},
                },
            },
        },
        {
            "method": "item/completed",
            "params": {
                "threadId": ROOT_THREAD,
                "turnId": ROOT_TURN,
                "item": {
                    "type": "collabAgentToolCall",
                    "id": "wait",
                    "tool": "wait",
                    "status": "completed",
                    "senderThreadId": ROOT_THREAD,
                    "receiverThreadIds": [CHILD_THREAD],
                    "model": None,
                    "reasoningEffort": None,
                    "prompt": None,
                    "agentsStates": {CHILD_THREAD: {"status": "completed"}},
                },
            },
        },
        _usage(ROOT_THREAD, 1000),
        _usage(CHILD_THREAD, 700),
        {
            "method": "item/completed",
            "params": {
                "threadId": ROOT_THREAD,
                "turnId": ROOT_TURN,
                "item": {
                    "type": "agentMessage",
                    "id": "final",
                    "phase": "final_answer",
                    "text": json.dumps(_critique()),
                },
            },
        },
        {
            "method": "turn/completed",
            "params": {
                "threadId": ROOT_THREAD,
                "turn": {"id": ROOT_TURN, "status": "completed"},
            },
        },
    ]


def _capture(messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "root_thread_id": ROOT_THREAD,
        "root_turn_id": ROOT_TURN,
        "messages": _messages() if messages is None else messages,
        "completion_ms": 1234.5,
        "stderr": "",
    }


def test_summarizer_proves_topology_usage_and_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner.workflow, "_apparatus_revision", lambda: "a" * 40)
    probe_plan = capability.build_probe()

    result = runner.summarize_capture(_capture(), probe_plan)

    assert result["status"] == "capability_confirmed"
    assert result["child_thread_id"] == CHILD_THREAD
    assert result["collaboration"]["spawn_count"] == 1
    assert result["collaboration"]["spawn_model"] == "gpt-6-sol"
    assert result["collaboration"]["spawn_effort"] == "low"
    assert result["usage"]["root"]["input_tokens"] == 1000
    assert result["usage"]["child"]["input_tokens"] == 700
    assert result["usage"]["sum_input_tokens"] == 1700
    assert result["score"]["defect_area_recall"] == 1.0


def test_summarizer_uses_pre_call_apparatus_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.workflow,
        "_apparatus_revision",
        lambda: pytest.fail("apparatus revision must not be recomputed"),
    )

    result = runner.summarize_capture(
        _capture(),
        capability.build_probe(),
        apparatus_revision="b" * 40,
    )

    assert result["apparatus_revision"] == "b" * 40


def test_summarizer_rejects_missing_child_usage() -> None:
    messages = [
        message
        for message in _messages()
        if not (
            message.get("method") == "thread/tokenUsage/updated"
            and message["params"]["threadId"] == CHILD_THREAD
        )
    ]

    with pytest.raises(runner.CodexNativeProbeError, match="child usage"):
        runner.summarize_capture(_capture(messages), capability.build_probe())


def test_summarizer_rejects_forbidden_tool_item() -> None:
    messages = _messages()
    messages.insert(
        -1,
        {
            "method": "item/completed",
            "params": {
                "threadId": CHILD_THREAD,
                "turnId": "turn_child",
                "item": {"type": "commandExecution", "id": "bad"},
            },
        },
    )

    with pytest.raises(runner.CodexNativeProbeError, match="forbidden"):
        runner.summarize_capture(_capture(messages), capability.build_probe())


def test_opaque_event_content_is_reduced_to_hash_evidence() -> None:
    sanitized = runner._sanitize_opaque(
        {"content": {"encrypted_content": "enc_secret_value"}}
    )

    encrypted = sanitized["content"]["encrypted_content"]
    assert encrypted["bytes"] == len("enc_secret_value")
    assert len(encrypted["sha256"]) == 64
    assert "enc_secret_value" not in json.dumps(sanitized)


def test_evidence_preserves_exact_supplied_plan_without_prompt(tmp_path: Path) -> None:
    probe_plan = capability.build_probe(executable="pinned-codex")
    run_dir = tmp_path / "run"

    runner._write_evidence(
        run_dir,
        probe_plan=probe_plan,
        usage_checkpoint={"decision": "proceed"},
        capture={"messages": [], "stderr": ""},
        result=None,
        error="synthetic exclusion",
    )

    stored = json.loads((run_dir / "probe-plan.json").read_text(encoding="utf-8"))
    assert stored["launch"][0] == "pinned-codex"
    assert stored["plan_sha256"] == probe_plan["plan_sha256"]
    assert stored["turn_start"]["input"].startswith("<redacted")
    assert probe_plan["turn_start"]["input"][0]["text"] not in json.dumps(stored)


def test_execution_refuses_while_usage_reset_is_pending(tmp_path: Path) -> None:
    probe = capability.build_probe()

    with pytest.raises(runner.CodexNativeProbeError, match="not ready"):
        runner.execute_probe(
            executable="codex",
            run_dir=tmp_path / "must-not-exist",
            expected_harness_version=probe["harness_version"],
            expected_plan_sha256=probe["plan_sha256"],
            expected_root_prompt_sha256=probe["root_prompt_sha256"],
            timeout_seconds=1,
        )
    assert not (tmp_path / "must-not-exist").exists()

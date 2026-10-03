from __future__ import annotations

import json
import sys
import textwrap
from copy import deepcopy
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


def test_capture_probe_exercises_json_rpc_lifecycle(tmp_path: Path) -> None:
    fake_server = tmp_path / "fake_app_server.py"
    fake_server.write_text(
        textwrap.dedent(
            """
            import json
            import sys

            def emit(value):
                print(json.dumps(value, separators=(",", ":")), flush=True)

            for line in sys.stdin:
                request = json.loads(line)
                method = request.get("method")
                if method == "initialize":
                    emit({"id": request["id"], "result": {"userAgent": "fake"}})
                elif method == "initialized":
                    continue
                elif method == "thread/start":
                    emit({"id": request["id"], "result": {"thread": {"id": "root"}}})
                elif method == "turn/start":
                    emit({"id": request["id"], "result": {"turn": {"id": "turn"}}})
                    emit({
                        "method": "turn/completed",
                        "params": {
                            "threadId": "root",
                            "turn": {"id": "turn", "status": "completed"},
                        },
                    })
            """
        ).lstrip(),
        encoding="utf-8",
    )
    probe = capability.build_probe()
    probe["launch"] = [sys.executable, str(fake_server)]
    probe["workspace"] = str(tmp_path)

    capture = runner.capture_probe(probe, timeout_seconds=5)

    assert "capture_error" not in capture
    assert capture["root_thread_id"] == "root"
    assert capture["root_turn_id"] == "turn"
    assert any(
        message.get("method") == "turn/completed"
        for message in capture["messages"]
    )


def test_preflight_stops_before_turn_start(tmp_path: Path) -> None:
    fake_server = tmp_path / "fake_preflight_server.py"
    fake_server.write_text(
        textwrap.dedent(
            """
            import json
            import sys

            def emit(value):
                print(json.dumps(value, separators=(",", ":")), flush=True)

            for line in sys.stdin:
                request = json.loads(line)
                method = request.get("method")
                if method == "initialize":
                    emit({"id": request["id"], "result": {"userAgent": "fake"}})
                elif method == "initialized":
                    continue
                elif method == "thread/start":
                    emit({"id": request["id"], "result": {"thread": {"id": "root"}}})
                elif method == "turn/start":
                    emit({"id": request["id"], "error": "turn must not start"})
            """
        ).lstrip(),
        encoding="utf-8",
    )
    probe = capability.build_probe()
    probe["launch"] = [sys.executable, str(fake_server)]
    probe["workspace"] = str(tmp_path)

    result = runner.preflight_probe(probe, timeout_seconds=5)

    assert result["status"] == "preflight_passed"
    assert result["message_count"] == 2
    assert result["harness_version"] == "codex-cli 0.159.3"


def test_executable_resolution_is_frozen_before_subprocess_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex.cmd"
    executable.write_text("synthetic", encoding="utf-8")
    monkeypatch.setattr(runner.shutil, "which", lambda _value: str(executable))

    resolved = runner._resolved_executable("codex")

    assert resolved == str(executable.resolve())


def test_early_failed_root_completion_is_not_accepted() -> None:
    message = {
        "method": "turn/completed",
        "params": {
            "threadId": ROOT_THREAD,
            "turn": {"id": ROOT_TURN, "status": "failed"},
        },
    }

    with pytest.raises(runner.CodexNativeProbeError, match="did not complete"):
        runner._is_completed_root_turn(
            message,
            root_thread_id=ROOT_THREAD,
            root_turn_id=ROOT_TURN,
        )


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
        {
            "content": {"encrypted_content": "enc_secret_value"},
            "encryptedContent": "camel_secret_value",
        }
    )

    encrypted = sanitized["content"]["encrypted_content"]
    assert encrypted["bytes"] == len("enc_secret_value")
    assert len(encrypted["sha256"]) == 64
    assert "enc_secret_value" not in json.dumps(sanitized)
    assert "camel_secret_value" not in json.dumps(sanitized)


def test_evidence_preserves_exact_supplied_plan_without_prompt(tmp_path: Path) -> None:
    probe_plan = capability.build_probe(executable="pinned-codex")
    run_dir = tmp_path / "run"

    runner._reserve_evidence(
        run_dir,
        probe_plan=probe_plan,
        usage_checkpoint={"decision": "proceed"},
    )
    runner._write_capture_evidence(
        run_dir,
        capture={"messages": [], "stderr": ""},
        result=None,
        error="synthetic exclusion",
    )

    stored = json.loads((run_dir / "probe-plan.json").read_text(encoding="utf-8"))
    assert stored["launch"][0] == "pinned-codex"
    assert stored["plan_sha256"] == probe_plan["plan_sha256"]
    assert stored["turn_start"]["input"].startswith("<redacted")
    assert probe_plan["turn_start"]["input"][0]["text"] not in json.dumps(stored)
    disposition = json.loads(
        (run_dir / "disposition.json").read_text(encoding="utf-8")
    )
    assert disposition["retry_allowed"] is False
    assert disposition["model_call_may_have_started"] is False


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


def test_armed_execution_reserves_frozen_path_before_single_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = deepcopy(capability._object(capability.PLAN_PATH))
    plan["status"] = "ready"
    monkeypatch.setattr(capability, "_object", lambda _path: plan)
    monkeypatch.setattr(capability, "EXPERIMENT_ROOT", tmp_path)
    probe = capability.build_probe()
    monkeypatch.setattr(
        runner,
        "_installed_version",
        lambda _executable: probe["harness_version"],
    )
    monkeypatch.setattr(runner.workflow, "_apparatus_revision", lambda: "c" * 40)
    monkeypatch.setattr(
        runner,
        "preflight_probe",
        lambda *_args, **_kwargs: {"status": "preflight_passed"},
    )
    usage_calls = 0

    def usage_snapshot(**_kwargs: Any) -> dict[str, Any]:
        nonlocal usage_calls
        usage_calls += 1
        return {"decision": "proceed"}

    monkeypatch.setattr(runner.codex_usage_snapshot, "read_snapshot", usage_snapshot)
    capture_calls = 0

    def capture_once(_probe: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal capture_calls
        capture_calls += 1
        return _capture()

    monkeypatch.setattr(runner, "capture_probe", capture_once)
    monkeypatch.setattr(
        runner,
        "summarize_capture",
        lambda *_args, **_kwargs: {"status": "capability_confirmed"},
    )
    run_dir = tmp_path / plan["runner"]["run_directory"]

    result = runner.execute_probe(
        executable="codex",
        run_dir=run_dir,
        expected_harness_version=probe["harness_version"],
        expected_plan_sha256=probe["plan_sha256"],
        expected_root_prompt_sha256=probe["root_prompt_sha256"],
        timeout_seconds=5,
    )

    assert result["status"] == "capability_confirmed"
    assert capture_calls == 1
    assert usage_calls == 1
    assert (run_dir / "attempt.json").is_file()
    assert (run_dir / "result.json").is_file()
    with pytest.raises(runner.CodexNativeProbeError, match="already exists"):
        runner.execute_probe(
            executable="codex",
            run_dir=run_dir,
            expected_harness_version=probe["harness_version"],
            expected_plan_sha256=probe["plan_sha256"],
            expected_root_prompt_sha256=probe["root_prompt_sha256"],
            timeout_seconds=5,
        )
    assert capture_calls == 1
    assert usage_calls == 1

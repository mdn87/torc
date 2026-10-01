from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT / "experiments" / "cross-agent-collaboration-001" / "worker_runner.py"
)
SPEC = importlib.util.spec_from_file_location("cross_agent_worker_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_codex_command_uses_stdin_and_fresh_session_controls() -> None:
    command = runner.build_inner_command(
        provider="codex",
        executable="codex",
        workspace="/fixture",
        model="gpt-6-sol",
        effort="xhigh",
    )

    assert command[-1] == "-"
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" not in command
    assert command[command.index("--ask-for-approval") + 1] == "never"
    assert command.index("--ask-for-approval") < command.index("exec")
    assert "--no-daemon" in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert not any("default_permissions" in value for value in command)
    if os.name == "nt":
        assert 'windows.sandbox="unelevated"' in command
    disabled = {
        command[index + 1]
        for index, value in enumerate(command)
        if value == "--disable"
    }
    assert {"apps", "plugins", "multi_agent", "skill_search"} <= disabled
    assert 'model_reasoning_effort="xhigh"' in command


def test_codex_critic_uses_read_only_sandbox() -> None:
    command = runner.build_inner_command(
        provider="codex",
        executable="codex",
        workspace="/fixture",
        model="gpt-6-sol",
        effort="low",
        role="critic",
    )

    assert command[command.index("--sandbox") + 1] == "read-only"


def test_tool_free_codex_command_disables_local_execution() -> None:
    command = runner.build_inner_command(
        provider="codex",
        executable="codex",
        workspace="/fixture",
        model="gpt-6-sol",
        effort="xhigh",
        tool_mode="none",
    )

    disabled = {
        command[index + 1]
        for index, value in enumerate(command)
        if value == "--disable"
    }
    assert {"code_mode_host", "shell_tool", "unified_exec"} <= disabled
    assert command[command.index("--sandbox") + 1] == "read-only"


def test_tool_free_claude_command_denies_local_execution() -> None:
    command = runner.build_inner_command(
        provider="claude-code",
        executable="claude",
        workspace="/fixture",
        model="claude-opus-4-7",
        effort="xhigh",
        tool_mode="none",
    )

    assert command[command.index("--tools") + 1] == ""
    settings = json.loads(command[command.index("--settings") + 1])
    assert settings["permissions"]["allow"] == []
    assert {"Read", "Edit", "Write", "Bash", "Agent"} <= set(
        settings["permissions"]["deny"]
    )


def test_claude_command_disables_customizations_network_and_subagents() -> None:
    command = runner.build_inner_command(
        provider="claude-code",
        executable="claude",
        workspace="/fixture",
        model="claude-opus-4-7",
        effort="low",
    )

    assert "--print" in command
    assert "--safe-mode" in command
    assert "--restricted" in command
    assert "--no-session-persistence" in command
    settings = json.loads(command[command.index("--settings") + 1])
    assert "Agent" in settings["permissions"]["deny"]
    assert "WebSearch" in settings["permissions"]["deny"]
    assert settings["permissions"]["blockReadsOutsideWorkingDirectories"] is True
    assert settings["sandbox"]["failIfUnavailable"] is True
    assert settings["sandbox"]["network"]["allowedDomains"] == []


def test_capture_process_records_first_output_and_completion(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-u",
        "-c",
        "import json; print(json.dumps({'type':'result','usage':{'output_tokens':2}}))",
    ]

    capture = runner.capture_process(
        provider="claude-code",
        command=command,
        workspace=tmp_path,
        prompt="ignored",
        timeout_seconds=10,
    )
    record = runner.build_run_record(
        provider="claude-code",
        transport="native",
        model="fixture",
        effort="low",
        harness_version="fixture 1.0",
        role="implementer",
        session_mode="fresh-ephemeral",
        requested_session_id=None,
        command=command,
        prompt="ignored",
        capture=capture,
    )

    assert record["exit_status"] == 0
    assert record["harness_version"] == "fixture 1.0"
    assert record["timed_out"] is False
    assert record["timing"]["time_to_first_output_ms"] is not None
    assert record["timing"]["completion_ms"] >= record["timing"]["startup_ms"]
    assert record["usage"]["output_tokens"] == 2
    assert record["malformed_event_count"] == 0
    assert record["environment_control"]["cleared_variables"] == []


def test_codex_worker_clears_parent_session_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_PERMISSION_PROFILE", "disabled")
    monkeypatch.setenv("CODEX_SESSION_ID", "parent-session")
    monkeypatch.setenv("CODEX_HOME", "controlled-auth-home")

    environment, control = runner._worker_environment("codex")

    assert "CODEX_PERMISSION_PROFILE" not in environment
    assert "CODEX_SESSION_ID" not in environment
    assert environment["CODEX_HOME"] == "controlled-auth-home"
    assert {"CODEX_PERMISSION_PROFILE", "CODEX_SESSION_ID"} <= set(
        control["cleared_variables"]
    )
    assert "CODEX_HOME" not in control["cleared_variables"]
    assert control["codex_home_preserved"] is True


def test_persistent_and_resumed_commands_preserve_session_identity() -> None:
    session_id = "8c2c081f-42e4-4ad4-a250-823449f16995"
    initial = runner.build_inner_command(
        provider="claude-code",
        executable="claude",
        workspace="/fixture",
        model="opus",
        effort="xhigh",
        session_mode="fresh-persistent",
        session_id=session_id,
    )
    resumed = runner.build_inner_command(
        provider="codex",
        executable="codex",
        workspace="/fixture",
        model="gpt-6-sol",
        effort="xhigh",
        session_mode="resume",
        session_id=session_id,
    )

    assert initial[initial.index("--session-id") + 1] == session_id
    assert "--no-session-persistence" not in initial
    exec_index = resumed.index("exec")
    assert resumed[exec_index : exec_index + 2] == ["exec", "resume"]
    assert resumed[-2:] == [session_id, "-"]
    assert runner.session_id_from_events(
        "codex", [{"type": "thread.started", "thread_id": session_id}]
    ) == session_id


def test_final_agent_text_and_json_decoder_cover_both_harnesses() -> None:
    codex_events = [
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": '```json\n{"ok":true}\n```'},
        }
    ]
    claude_events = [
        {"type": "result", "structured_output": {"ok": True}, "session_id": "id"}
    ]

    assert runner.decode_json_object(runner.final_agent_text("codex", codex_events)) == {
        "ok": True
    }
    assert runner.decode_json_object(runner.final_agent_text("claude-code", claude_events)) == {
        "ok": True
    }


def test_wsl_worker_rejects_a_windows_mounted_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Completed:
        returncode = 0
        stdout = "/mnt/c/Users/test/AppData/Roaming/npm/claude\n"
        stderr = ""

    monkeypatch.setattr(runner.shutil, "which", lambda _name: "wsl.exe")
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: Completed())

    with pytest.raises(runner.WorkerRunnerError, match="Windows-mounted shim"):
        runner._wsl_executable("claude", "Ubuntu")


def test_wsl_worker_prefers_native_linux_install_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = "/home/test/.local/bin/claude\n"
        stderr = ""

    def fake_run(args: list[str], **_kwargs: object) -> Completed:
        captured["args"] = args
        return Completed()

    monkeypatch.setattr(runner.shutil, "which", lambda _name: "wsl.exe")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    resolved = runner._wsl_executable("claude", "Ubuntu")

    assert resolved == "/home/test/.local/bin/claude"
    assert '$HOME/.local/bin/$1' in str(captured["args"])


def test_capture_process_preserves_timeout(tmp_path: Path) -> None:
    capture = runner.capture_process(
        provider="codex",
        command=[sys.executable, "-c", "import time; time.sleep(2)"],
        workspace=tmp_path,
        prompt="",
        timeout_seconds=0.05,
    )

    assert capture["timed_out"] is True
    assert capture["exit_status"] != 0


def test_execute_requires_output_outside_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("work", encoding="utf-8")
    monkeypatch.setattr(runner, "build_command", lambda **_kwargs: ["worker"])

    exit_status = runner.main(
        [
            "--provider",
            "codex",
            "--workspace",
            str(tmp_path),
            "--prompt-file",
            str(prompt),
            "--model",
            "fixture",
            "--effort",
            "low",
            "--output-dir",
            str(tmp_path / "results"),
            "--execute",
        ]
    )

    assert exit_status == 2
    assert "outside the agent workspace" in capsys.readouterr().err

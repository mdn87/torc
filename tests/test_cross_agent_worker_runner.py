from __future__ import annotations

import importlib.util
import json
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
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert 'model_reasoning_effort="xhigh"' in command


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


def test_capture_process_preserves_timeout(tmp_path: Path) -> None:
    capture = runner.capture_process(
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

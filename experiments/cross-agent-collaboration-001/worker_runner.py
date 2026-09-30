"""Measured, opt-in worker launcher for cross-agent experiment 001.

This runner belongs to the experiment apparatus. It is intentionally not part
of TORC's runtime API or provider-routing boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from torc.canonical import canonical_json  # noqa: E402
from torc.experiment_usage import latest_codex_usage, normalize_usage  # noqa: E402

PROVIDERS = ("codex", "claude-code")
TRANSPORTS = ("native", "wsl")


class WorkerRunnerError(RuntimeError):
    """Raised when a worker cannot be launched without weakening controls."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json_lines(text: str) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    malformed = 0
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            malformed += 1
    return events, malformed


def _provider_usage(
    provider: str, events: list[dict[str, Any]]
) -> dict[str, Any]:
    if provider == "codex":
        return normalize_usage("codex-jsonl", latest_codex_usage(events))
    for event in reversed(events):
        usage = event.get("usage")
        if event.get("type") == "result" and isinstance(usage, dict):
            return normalize_usage("claude-code", usage)
    return normalize_usage("claude-code", None)


def _claude_settings() -> dict[str, Any]:
    return {
        "permissions": {
            "allow": ["Read(./**)", "Edit(./**)", "Write(./**)", "Bash"],
            "deny": ["WebFetch", "WebSearch", "Agent"],
            "defaultMode": "dontAsk",
            "disableBypassPermissionsMode": "disable",
            "blockReadsOutsideWorkingDirectories": True,
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "network": {"allowedDomains": []},
        },
    }


def build_inner_command(
    *,
    provider: str,
    executable: str,
    workspace: str,
    model: str,
    effort: str,
) -> list[str]:
    """Build a fresh-session worker command with no prompt in argv."""

    if provider not in PROVIDERS:
        raise WorkerRunnerError(f"unsupported provider: {provider}")
    for label, value in (
        ("executable", executable),
        ("workspace", workspace),
        ("model", model),
        ("effort", effort),
    ):
        if not isinstance(value, str) or not value.strip():
            raise WorkerRunnerError(f"{label} must be a non-empty string")

    if provider == "codex":
        return [
            executable,
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "--json",
            "--model",
            model,
            "--sandbox",
            "workspace-write",
            "-C",
            workspace,
            "-c",
            f"model_reasoning_effort={json.dumps(effort)}",
            "-",
        ]

    settings = json.dumps(_claude_settings(), separators=(",", ":"))
    return [
        executable,
        "--model",
        model,
        "--effort",
        effort,
        "--safe-mode",
        "--restricted",
        "--setting-sources",
        "local",
        "--settings",
        settings,
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--tools",
        "Read,Edit,Write,Bash",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--disable-slash-commands",
        "--no-chrome",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
        "--print",
    ]


def _wsl_path(path: Path, distro: str) -> str:
    wsl = shutil.which("wsl.exe")
    if not wsl:
        raise WorkerRunnerError("wsl.exe is unavailable")
    completed = subprocess.run(
        [wsl, "-d", distro, "--exec", "wslpath", "-a", str(path.resolve())],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    value = completed.stdout.strip()
    if completed.returncode or not value:
        raise WorkerRunnerError("workspace could not be mapped into WSL")
    return value


def _wsl_executable(name: str, distro: str) -> str:
    wsl = shutil.which("wsl.exe")
    if not wsl:
        raise WorkerRunnerError("wsl.exe is unavailable")
    script = (
        'export NVM_DIR="$HOME/.nvm"; '
        '[ ! -s "$NVM_DIR/nvm.sh" ] || . "$NVM_DIR/nvm.sh" >/dev/null; '
        "nvm use default >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || true; "
        'command -v "$1"'
    )
    completed = subprocess.run(
        [wsl, "-d", distro, "--exec", "bash", "-lc", script, "torc", name],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    lines = completed.stdout.strip().splitlines()
    if completed.returncode or not lines:
        raise WorkerRunnerError(f"{name} is unavailable in WSL distro {distro!r}")
    return lines[-1]


def build_command(
    *,
    provider: str,
    transport: str,
    executable: str,
    workspace: Path,
    model: str,
    effort: str,
    distro: str = "Ubuntu",
) -> list[str]:
    if transport not in TRANSPORTS:
        raise WorkerRunnerError(f"unsupported transport: {transport}")
    if transport == "native":
        resolved = shutil.which(executable)
        if not resolved:
            raise WorkerRunnerError(f"native executable is unavailable: {executable}")
        return build_inner_command(
            provider=provider,
            executable=resolved,
            workspace=str(workspace.resolve()),
            model=model,
            effort=effort,
        )

    wsl = shutil.which("wsl.exe")
    if not wsl:
        raise WorkerRunnerError("wsl.exe is unavailable")
    linux_workspace = _wsl_path(workspace, distro)
    inner = build_inner_command(
        provider=provider,
        executable=_wsl_executable(executable, distro),
        workspace=linux_workspace,
        model=model,
        effort=effort,
    )
    return [wsl, "-d", distro, "--cd", linux_workspace, "--exec", *inner]


def probe_harness_version(command: list[str], transport: str) -> str:
    if transport == "native":
        version_command = [command[0], "--version"]
    else:
        try:
            exec_index = command.index("--exec")
            version_command = [*command[: exec_index + 2], "--version"]
        except (ValueError, IndexError) as exc:
            raise WorkerRunnerError("WSL command has no executable boundary") from exc
    completed = subprocess.run(
        version_command,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    version = (completed.stdout or completed.stderr).strip()
    if completed.returncode or not version:
        raise WorkerRunnerError("worker harness version probe failed")
    return version[:200]


def capture_process(
    *,
    command: list[str],
    workspace: Path,
    prompt: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run one worker and preserve output plus monotonic timing evidence."""

    if not command:
        raise WorkerRunnerError("worker command must not be empty")
    if timeout_seconds <= 0:
        raise WorkerRunnerError("timeout must be positive")
    resolved_workspace = workspace.resolve()
    if not resolved_workspace.is_dir():
        raise WorkerRunnerError(f"workspace does not exist: {resolved_workspace}")

    started_at = _utc_now()
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=resolved_workspace,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    launched = time.perf_counter()
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    first_stdout_at: list[float] = []
    first_lock = threading.Lock()

    def drain(pipe: Any, destination: list[str], mark_first: bool) -> None:
        for line in pipe:
            if mark_first:
                with first_lock:
                    if not first_stdout_at:
                        first_stdout_at.append(time.perf_counter())
            destination.append(line)

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=drain, args=(process.stdout, stdout_parts, True), daemon=True
    )
    stderr_thread = threading.Thread(
        target=drain, args=(process.stderr, stderr_parts, False), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    assert process.stdin is not None
    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except BrokenPipeError:
        pass

    timed_out = False
    try:
        exit_status = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        exit_status = process.wait(timeout=10)
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    completed = time.perf_counter()
    completed_at = _utc_now()
    stdout = "".join(stdout_parts)
    stderr = "".join(stderr_parts)
    return {
        "started_at": started_at,
        "completed_at": completed_at,
        "startup_ms": round((launched - started) * 1000, 3),
        "time_to_first_output_ms": (
            round((first_stdout_at[0] - started) * 1000, 3)
            if first_stdout_at
            else None
        ),
        "completion_ms": round((completed - started) * 1000, 3),
        "exit_status": exit_status,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
    }


def build_run_record(
    *,
    provider: str,
    transport: str,
    model: str,
    effort: str,
    harness_version: str,
    command: list[str],
    prompt: str,
    capture: dict[str, Any],
) -> dict[str, Any]:
    events, malformed = _json_lines(capture["stdout"])
    return {
        "schema_version": 1,
        "provider": provider,
        "transport": transport,
        "model": model,
        "effort": effort,
        "harness_version": harness_version,
        "command": command,
        "prompt_sha256": _sha256(prompt),
        "started_at": capture["started_at"],
        "completed_at": capture["completed_at"],
        "timing": {
            "startup_ms": capture["startup_ms"],
            "time_to_first_output_ms": capture["time_to_first_output_ms"],
            "completion_ms": capture["completion_ms"],
        },
        "exit_status": capture["exit_status"],
        "timed_out": capture["timed_out"],
        "stdout_sha256": _sha256(capture["stdout"]),
        "stderr_sha256": _sha256(capture["stderr"]),
        "event_count": len(events),
        "malformed_event_count": malformed,
        "usage": _provider_usage(provider, events),
    }


def _write_run(output_dir: Path, record: dict[str, Any], capture: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "worker-run.json").write_text(
        canonical_json(record) + "\n", encoding="utf-8"
    )
    (output_dir / "stdout.jsonl").write_text(capture["stdout"], encoding="utf-8")
    (output_dir / "stderr.log").write_text(capture["stderr"], encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument("--transport", choices=TRANSPORTS, default="native")
    parser.add_argument("--executable")
    parser.add_argument("--distro", default=os.environ.get("TORC_WSL_DISTRO", "Ubuntu"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--expected-harness-version")
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="launch the worker; without this flag only print the frozen command plan",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    executable = args.executable or ("codex" if args.provider == "codex" else "claude")
    try:
        prompt = args.prompt_file.read_text(encoding="utf-8")
        command = build_command(
            provider=args.provider,
            transport=args.transport,
            executable=executable,
            workspace=args.workspace,
            model=args.model,
            effort=args.effort,
            distro=args.distro,
        )
        plan = {
            "provider": args.provider,
            "transport": args.transport,
            "model": args.model,
            "effort": args.effort,
            "command": command,
            "prompt_sha256": _sha256(prompt),
            "execute": args.execute,
        }
        if not args.execute:
            plan["harness_version"] = probe_harness_version(command, args.transport)
            print(canonical_json(plan))
            return 0
        if args.output_dir is None:
            raise WorkerRunnerError("--output-dir is required with --execute")
        workspace = args.workspace.resolve()
        output_dir = args.output_dir.resolve()
        if output_dir == workspace or output_dir.is_relative_to(workspace):
            raise WorkerRunnerError("runner output must remain outside the agent workspace")
        if not args.expected_harness_version:
            raise WorkerRunnerError("--expected-harness-version is required with --execute")
        harness_version = probe_harness_version(command, args.transport)
        if harness_version != args.expected_harness_version:
            raise WorkerRunnerError(
                "worker harness version differs from the frozen control: "
                f"expected {args.expected_harness_version!r}, got {harness_version!r}"
            )
        capture = capture_process(
            command=command,
            workspace=workspace,
            prompt=prompt,
            timeout_seconds=args.timeout_seconds,
        )
        record = build_run_record(
            provider=args.provider,
            transport=args.transport,
            model=args.model,
            effort=args.effort,
            harness_version=harness_version,
            command=command,
            prompt=prompt,
            capture=capture,
        )
        _write_run(output_dir, record, capture)
        print(canonical_json(record))
        return 0 if record["exit_status"] == 0 and not record["timed_out"] else 1
    except (OSError, subprocess.SubprocessError, WorkerRunnerError) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

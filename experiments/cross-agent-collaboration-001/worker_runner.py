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
import uuid
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
ROLES = ("implementer", "critic")
SESSION_MODES = ("fresh-ephemeral", "fresh-persistent", "resume")
_CODEX_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "in_app_browser",
    "multi_agent",
    "plugins",
    "remote_plugin",
    "skill_search",
)


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


def final_agent_text(provider: str, events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        if provider == "codex":
            item = event.get("item")
            if (
                event.get("type") == "item.completed"
                and isinstance(item, dict)
                and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)
            ):
                return item["text"]
        elif provider == "claude-code" and event.get("type") == "result":
            structured = event.get("structured_output")
            if isinstance(structured, dict):
                return canonical_json(structured)
            result = event.get("result")
            if isinstance(result, str):
                return result
    return None


def decode_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise WorkerRunnerError("worker output did not contain a JSON object") from None
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise WorkerRunnerError("worker output contained malformed JSON") from exc
    if not isinstance(value, dict):
        raise WorkerRunnerError("worker output must be a JSON object")
    return value


def _claude_settings(role: str) -> dict[str, Any]:
    if role == "implementer":
        allowed = ["Read(./**)", "Edit(./**)", "Write(./**)", "Bash"]
        denied = ["WebFetch", "WebSearch", "Agent"]
    else:
        allowed = ["Read(./**)", "Glob", "Grep"]
        denied = ["Edit", "Write", "Bash", "WebFetch", "WebSearch", "Agent"]
    return {
        "permissions": {
            "allow": allowed,
            "deny": denied,
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
    role: str = "implementer",
    session_mode: str = "fresh-ephemeral",
    session_id: str | None = None,
) -> list[str]:
    """Build a fresh-session worker command with no prompt in argv."""

    if provider not in PROVIDERS:
        raise WorkerRunnerError(f"unsupported provider: {provider}")
    if role not in ROLES:
        raise WorkerRunnerError(f"unsupported worker role: {role}")
    if session_mode not in SESSION_MODES:
        raise WorkerRunnerError(f"unsupported session mode: {session_mode}")
    if session_mode == "resume" and not session_id:
        raise WorkerRunnerError("resume mode requires a session id")
    if provider == "claude-code" and session_mode != "fresh-ephemeral":
        try:
            uuid.UUID(str(session_id))
        except (TypeError, ValueError) as exc:
            raise WorkerRunnerError(
                "persistent Claude sessions require a UUID session id"
            ) from exc
    for label, value in (
        ("executable", executable),
        ("workspace", workspace),
        ("model", model),
        ("effort", effort),
    ):
        if not isinstance(value, str) or not value.strip():
            raise WorkerRunnerError(f"{label} must be a non-empty string")

    if provider == "codex":
        permission_profile = ":workspace" if role == "implementer" else ":read-only"
        prefix = [
            executable,
            "--ask-for-approval",
            "never",
            "-c",
            f"default_permissions={json.dumps(permission_profile)}",
        ]
        for feature in _CODEX_DISABLED_FEATURES:
            prefix.extend(["--disable", feature])
        if session_mode == "resume":
            return [
                *prefix,
                "exec",
                "resume",
                "--ignore-user-config",
                "--ignore-rules",
                "--json",
                "--model",
                model,
                "-c",
                f"model_reasoning_effort={json.dumps(effort)}",
                str(session_id),
                "-",
            ]
        command = [
            *prefix,
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "--model",
            model,
            "-C",
            workspace,
            "-c",
            f"model_reasoning_effort={json.dumps(effort)}",
        ]
        if session_mode == "fresh-ephemeral":
            command.append("--ephemeral")
        command.append("-")
        return command

    settings = json.dumps(_claude_settings(role), separators=(",", ":"))
    tools = "Read,Edit,Write,Bash" if role == "implementer" else "Read,Glob,Grep"
    command = [
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
        tools,
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--disable-slash-commands",
        "--no-chrome",
        "--output-format",
        "stream-json",
        "--verbose",
        "--print",
    ]
    if session_mode == "fresh-ephemeral":
        command.insert(-4, "--no-session-persistence")
    elif session_mode == "fresh-persistent":
        command[1:1] = ["--session-id", str(session_id)]
    else:
        command[1:1] = ["--resume", str(session_id)]
    return command


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
        'for candidate in "$HOME/.local/bin/$1" "$HOME/.claude/local/$1"; do '
        '[ ! -x "$candidate" ] || { readlink -f "$candidate"; exit 0; }; '
        "done; "
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
    resolved = lines[-1]
    if resolved.startswith("/mnt/"):
        raise WorkerRunnerError(
            f"{name} resolves to a Windows-mounted shim; install a native Linux "
            f"executable in WSL distro {distro!r}"
        )
    return resolved


def build_command(
    *,
    provider: str,
    transport: str,
    executable: str,
    workspace: Path,
    model: str,
    effort: str,
    distro: str = "Ubuntu",
    role: str = "implementer",
    session_mode: str = "fresh-ephemeral",
    session_id: str | None = None,
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
            role=role,
            session_mode=session_mode,
            session_id=session_id,
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
        role=role,
        session_mode=session_mode,
        session_id=session_id,
    )
    return [wsl, "-d", distro, "--cd", linux_workspace, "--exec", *inner]


def preflight_codex_permissions(
    executable: str, workspace: Path, role: str
) -> dict[str, Any]:
    resolved = shutil.which(executable)
    if not resolved:
        raise WorkerRunnerError(f"native executable is unavailable: {executable}")
    permission_profile = ":workspace" if role == "implementer" else ":read-only"
    if os.name == "nt":
        if role == "implementer":
            probe = (
                "Set-Content -LiteralPath .torc-permission-probe -Value ok; "
                "Get-Content -LiteralPath TASK.md | Out-Null; "
                "Remove-Item -LiteralPath .torc-permission-probe -Force"
            )
        else:
            probe = "Get-Content -LiteralPath TASK.md | Out-Null"
        command = [
            resolved,
            "sandbox",
            "-P",
            permission_profile,
            "-C",
            str(workspace.resolve()),
            "powershell.exe",
            "-NoProfile",
            "-Command",
            probe,
        ]
    else:
        probe = "test -r TASK.md"
        if role == "implementer":
            probe += " && : > .torc-permission-probe && rm .torc-permission-probe"
        command = [
            resolved,
            "sandbox",
            "-P",
            permission_profile,
            "-C",
            str(workspace.resolve()),
            "sh",
            "-c",
            probe,
        ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode:
        raise WorkerRunnerError(
            "Codex permission-profile preflight failed: "
            + (completed.stderr or completed.stdout).strip()[:500]
        )
    return {
        "performed": True,
        "permission_profile": permission_profile,
        "read_verified": True,
        "write_verified": role == "implementer",
    }


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


def session_id_from_events(provider: str, events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if provider == "codex" and event.get("type") == "thread.started":
            value = event.get("thread_id") or event.get("threadId")
        elif provider == "claude-code" and event.get("type") == "result":
            value = event.get("session_id") or event.get("sessionId")
        else:
            continue
        if isinstance(value, str) and value:
            return value
    return None


def build_run_record(
    *,
    provider: str,
    transport: str,
    model: str,
    effort: str,
    harness_version: str,
    role: str,
    session_mode: str,
    requested_session_id: str | None,
    command: list[str],
    prompt: str,
    capture: dict[str, Any],
) -> dict[str, Any]:
    events, malformed = _json_lines(capture["stdout"])
    observed_session_id = session_id_from_events(provider, events)
    if requested_session_id and observed_session_id != requested_session_id:
        raise WorkerRunnerError(
            "worker returned a different session id from the frozen request"
        )
    if session_mode != "fresh-ephemeral" and not observed_session_id:
        raise WorkerRunnerError("persistent worker run did not report a session id")
    return {
        "schema_version": 1,
        "provider": provider,
        "transport": transport,
        "model": model,
        "effort": effort,
        "harness_version": harness_version,
        "role": role,
        "session": {
            "mode": session_mode,
            "requested_id": requested_session_id,
            "observed_id": observed_session_id,
        },
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


def execute_worker(
    *,
    provider: str,
    transport: str,
    executable: str,
    distro: str,
    workspace: Path,
    prompt: str,
    model: str,
    effort: str,
    role: str,
    session_mode: str,
    session_id: str | None,
    expected_harness_version: str,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    resolved_workspace = workspace.resolve()
    resolved_output = output_dir.resolve()
    if resolved_output == resolved_workspace or resolved_output.is_relative_to(
        resolved_workspace
    ):
        raise WorkerRunnerError("runner output must remain outside the agent workspace")
    if resolved_output.exists():
        raise WorkerRunnerError(f"runner output directory already exists: {resolved_output}")
    if provider == "codex" and transport == "native":
        control_preflight = preflight_codex_permissions(executable, resolved_workspace, role)
    else:
        control_preflight = {
            "performed": False,
            "reason": "provider sandbox is fail-closed at worker startup",
        }
    command = build_command(
        provider=provider,
        transport=transport,
        executable=executable,
        workspace=resolved_workspace,
        model=model,
        effort=effort,
        distro=distro,
        role=role,
        session_mode=session_mode,
        session_id=session_id,
    )
    harness_version = probe_harness_version(command, transport)
    if harness_version != expected_harness_version:
        raise WorkerRunnerError(
            "worker harness version differs from the frozen control: "
            f"expected {expected_harness_version!r}, got {harness_version!r}"
        )
    capture = capture_process(
        command=command,
        workspace=resolved_workspace,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
    )
    record = build_run_record(
        provider=provider,
        transport=transport,
        model=model,
        effort=effort,
        harness_version=harness_version,
        role=role,
        session_mode=session_mode,
        requested_session_id=session_id,
        command=command,
        prompt=prompt,
        capture=capture,
    )
    record["control_preflight"] = control_preflight
    _write_run(resolved_output, record, capture)
    return record


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
    parser.add_argument("--role", choices=ROLES, default="implementer")
    parser.add_argument("--session-mode", choices=SESSION_MODES, default="fresh-ephemeral")
    parser.add_argument("--session-id")
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
            role=args.role,
            session_mode=args.session_mode,
            session_id=args.session_id,
        )
        plan = {
            "provider": args.provider,
            "transport": args.transport,
            "model": args.model,
            "effort": args.effort,
            "role": args.role,
            "session_mode": args.session_mode,
            "session_id": args.session_id,
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
        record = execute_worker(
            provider=args.provider,
            transport=args.transport,
            executable=executable,
            distro=args.distro,
            workspace=args.workspace,
            prompt=prompt,
            model=args.model,
            effort=args.effort,
            role=args.role,
            session_mode=args.session_mode,
            session_id=args.session_id,
            expected_harness_version=args.expected_harness_version,
            timeout_seconds=args.timeout_seconds,
            output_dir=args.output_dir,
        )
        print(canonical_json(record))
        return 0 if record["exit_status"] == 0 and not record["timed_out"] else 1
    except (OSError, subprocess.SubprocessError, WorkerRunnerError) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Guard and capture one local Codex native-subagent capability probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import codex_native_capability as capability  # noqa: E402
import codex_usage_snapshot  # noqa: E402
import native_context_response as response_scoring  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402


class CodexNativeProbeError(RuntimeError):
    """Raised when a native probe cannot preserve or prove its controls."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _pump_lines(stream: TextIO, output: queue.Queue[str], copy: list[str]) -> None:
    for line in stream:
        copy.append(line)
        output.put(line)


def _send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if process.stdin is None:
        raise CodexNativeProbeError("app-server stdin is unavailable")
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _next_message(
    lines: queue.Queue[str],
    messages: list[dict[str, Any]],
    *,
    deadline: float,
) -> dict[str, Any]:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CodexNativeProbeError("app-server event stream timed out")
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise CodexNativeProbeError("app-server event stream timed out") from exc
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        messages.append(message)
        return message


def _request(
    process: subprocess.Popen[str],
    lines: queue.Queue[str],
    messages: list[dict[str, Any]],
    *,
    request_id: int,
    method: str,
    params: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    _send(
        process,
        {"id": request_id, "method": method, "params": params},
    )
    while True:
        message = _next_message(lines, messages, deadline=deadline)
        if message.get("id") != request_id:
            if "id" in message and "method" in message:
                raise CodexNativeProbeError(
                    f"unexpected server request during tool-free probe: {message['method']}"
                )
            continue
        if "error" in message:
            raise CodexNativeProbeError(
                f"app-server request failed: {method}: {message['error']}"
            )
        result = message.get("result")
        if not isinstance(result, dict):
            raise CodexNativeProbeError(f"app-server returned no result: {method}")
        return result


def _drain_grace(
    lines: queue.Queue[str], messages: list[dict[str, Any]], *, seconds: float
) -> None:
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty:
            return
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict):
            messages.append(message)


def _is_completed_root_turn(
    message: dict[str, Any], *, root_thread_id: str, root_turn_id: str
) -> bool:
    params = message.get("params")
    if (
        message.get("method") != "turn/completed"
        or not isinstance(params, dict)
        or params.get("threadId") != root_thread_id
    ):
        return False
    turn = params.get("turn")
    if (
        not isinstance(turn, dict)
        or turn.get("id") != root_turn_id
        or turn.get("status") != "completed"
    ):
        raise CodexNativeProbeError("root turn did not complete successfully")
    return True


def _process_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith("CODEX_") and name != "CODEX_HOME":
            del environment[name]
    return environment


def _resolved_executable(executable: str) -> str:
    resolved = shutil.which(executable)
    if not resolved:
        raise CodexNativeProbeError(f"Codex executable is unavailable: {executable}")
    return str(Path(resolved).resolve())


def preflight_probe(
    probe: dict[str, Any], *, timeout_seconds: float
) -> dict[str, Any]:
    """Validate the exact launch and thread request without starting a turn."""
    if timeout_seconds <= 0:
        raise CodexNativeProbeError("probe timeout must be positive")
    observed_at = _utc_now()
    started = time.perf_counter()
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            probe["launch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=probe["workspace"],
            env=_process_environment(),
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise CodexNativeProbeError(f"cannot start Codex app-server: {exc}") from exc
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise CodexNativeProbeError("app-server output streams are unavailable")
    lines: queue.Queue[str] = queue.Queue()
    raw_stdout: list[str] = []
    raw_stderr: list[str] = []
    stdout_reader = threading.Thread(
        target=_pump_lines,
        args=(process.stdout, lines, raw_stdout),
        daemon=True,
    )
    stderr_queue: queue.Queue[str] = queue.Queue()
    stderr_reader = threading.Thread(
        target=_pump_lines,
        args=(process.stderr, stderr_queue, raw_stderr),
        daemon=True,
    )
    stdout_reader.start()
    stderr_reader.start()
    messages: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout_seconds
    try:
        _request(
            process,
            lines,
            messages,
            request_id=1,
            method="initialize",
            params=probe["initialize"],
            deadline=deadline,
        )
        _send(process, {"method": "initialized", "params": {}})
        thread_result = _request(
            process,
            lines,
            messages,
            request_id=2,
            method="thread/start",
            params=probe["thread_start"],
            deadline=deadline,
        )
        thread = thread_result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise CodexNativeProbeError("thread/start returned no root thread id")
    except CodexNativeProbeError as exc:
        stderr = "".join(raw_stderr).strip()
        detail = f"; stderr: {stderr}" if stderr else ""
        raise CodexNativeProbeError(f"app-server preflight failed: {exc}{detail}") from exc
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        stdout_reader.join(timeout=2)
        stderr_reader.join(timeout=2)
    return {
        "schema_version": 1,
        "status": "preflight_passed",
        "observed_at": observed_at,
        "completion_ms": round((time.perf_counter() - started) * 1000, 3),
        "message_count": len(messages),
        "stdout_sha256": hashlib.sha256("".join(raw_stdout).encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256("".join(raw_stderr).encode()).hexdigest(),
        "harness_version": probe["harness_version"],
        "plan_sha256": probe["plan_sha256"],
        "root_prompt_sha256": probe["root_prompt_sha256"],
    }


def capture_probe(
    probe: dict[str, Any], *, timeout_seconds: float
) -> dict[str, Any]:
    """Run the single guarded app-server turn and retain in-memory events."""
    if timeout_seconds <= 0:
        raise CodexNativeProbeError("probe timeout must be positive")
    started_at = _utc_now()
    started = time.perf_counter()
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            probe["launch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=probe["workspace"],
            env=_process_environment(),
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise CodexNativeProbeError(f"cannot start Codex app-server: {exc}") from exc
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise CodexNativeProbeError("app-server output streams are unavailable")
    lines: queue.Queue[str] = queue.Queue()
    raw_stdout: list[str] = []
    raw_stderr: list[str] = []
    stdout_reader = threading.Thread(
        target=_pump_lines,
        args=(process.stdout, lines, raw_stdout),
        daemon=True,
    )
    stderr_queue: queue.Queue[str] = queue.Queue()
    stderr_reader = threading.Thread(
        target=_pump_lines,
        args=(process.stderr, stderr_queue, raw_stderr),
        daemon=True,
    )
    stdout_reader.start()
    stderr_reader.start()
    messages: list[dict[str, Any]] = []
    root_thread_id: str | None = None
    root_turn_id: str | None = None
    turn_start_sent = False
    deadline = time.monotonic() + timeout_seconds
    error: Exception | None = None
    try:
        _request(
            process,
            lines,
            messages,
            request_id=1,
            method="initialize",
            params=probe["initialize"],
            deadline=deadline,
        )
        _send(process, {"method": "initialized", "params": {}})
        thread_result = _request(
            process,
            lines,
            messages,
            request_id=2,
            method="thread/start",
            params=probe["thread_start"],
            deadline=deadline,
        )
        thread = thread_result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise CodexNativeProbeError("thread/start returned no root thread id")
        root_thread_id = thread["id"]
        turn_params = {"threadId": root_thread_id, **probe["turn_start"]}
        turn_start_sent = True
        turn_result = _request(
            process,
            lines,
            messages,
            request_id=3,
            method="turn/start",
            params=turn_params,
            deadline=deadline,
        )
        turn = turn_result.get("turn")
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
            raise CodexNativeProbeError("turn/start returned no root turn id")
        root_turn_id = turn["id"]
        completed = any(
            _is_completed_root_turn(
                message,
                root_thread_id=root_thread_id,
                root_turn_id=root_turn_id,
            )
            for message in messages
        )
        while not completed:
            message = _next_message(lines, messages, deadline=deadline)
            completed = _is_completed_root_turn(
                message,
                root_thread_id=root_thread_id,
                root_turn_id=root_turn_id,
            )
        _drain_grace(lines, messages, seconds=1.0)
    except Exception as exc:  # preserve capture evidence before re-raising
        error = exc
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        stdout_reader.join(timeout=2)
        stderr_reader.join(timeout=2)
    completed = time.perf_counter()
    result = {
        "schema_version": 1,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "completion_ms": round((completed - started) * 1000, 3),
        "root_thread_id": root_thread_id,
        "root_turn_id": root_turn_id,
        "turn_start_sent": turn_start_sent,
        "messages": messages,
        "stderr": "".join(raw_stderr),
        "raw_stdout_sha256": hashlib.sha256("".join(raw_stdout).encode()).hexdigest(),
        "exit_status": process.returncode,
    }
    if error is not None:
        result["capture_error"] = str(error)
    return result


def _item(message: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    if message.get("method") != "item/completed":
        return None, None
    params = message.get("params")
    if not isinstance(params, dict):
        return None, None
    item = params.get("item")
    return params.get("threadId"), item if isinstance(item, dict) else None


def _usage_total(params: dict[str, Any]) -> dict[str, int]:
    token_usage = params.get("tokenUsage")
    total = token_usage.get("total") if isinstance(token_usage, dict) else None
    if not isinstance(total, dict):
        raise CodexNativeProbeError("thread token usage has no total")
    fields = {
        "input_tokens": "inputTokens",
        "cached_input_tokens": "cachedInputTokens",
        "cache_write_input_tokens": "cacheWriteInputTokens",
        "output_tokens": "outputTokens",
        "reasoning_output_tokens": "reasoningOutputTokens",
        "total_tokens": "totalTokens",
    }
    normalized: dict[str, int] = {}
    for target, source in fields.items():
        value = total.get(source, 0 if source == "cacheWriteInputTokens" else None)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CodexNativeProbeError(f"thread usage field is invalid: {source}")
        normalized[target] = value
    return normalized


def _decode_critique(text: str, probe_plan: dict[str, Any]) -> dict[str, Any]:
    try:
        critique = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodexNativeProbeError("root final answer is not JSON") from exc
    if not isinstance(critique, dict):
        raise CodexNativeProbeError("root final answer is not a JSON object")
    plan = capability._object(capability.PLAN_PATH)
    candidate_id = plan["candidate"]["candidate_id"]
    candidate = response_scoring.request_builder._candidate(candidate_id)
    _, control = workflow._compile_handoff(
        candidate["fixture_id"],
        plan["series_id"],
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"codex-native/{plan['provider_controls']['subagent_model']}",
    )
    try:
        workflow._validate_critique(critique, control)
    except workflow.WorkflowRunnerError as exc:
        raise CodexNativeProbeError(f"critic result is invalid: {exc}") from exc
    expected_prompt_hash = probe_plan["root_prompt_sha256"]
    if expected_prompt_hash != capability.build_probe()["root_prompt_sha256"]:
        raise CodexNativeProbeError("probe prompt no longer reconstructs")
    return critique


def summarize_capture(
    capture: dict[str, Any],
    probe_plan: dict[str, Any],
    *,
    apparatus_revision: str | None = None,
) -> dict[str, Any]:
    """Fail closed on topology, usage, tools, and critic-result drift."""
    if capture.get("capture_error"):
        raise CodexNativeProbeError(f"probe capture failed: {capture['capture_error']}")
    root_thread_id = capture.get("root_thread_id")
    root_turn_id = capture.get("root_turn_id")
    messages = capture.get("messages")
    if not isinstance(root_thread_id, str) or not isinstance(root_turn_id, str):
        raise CodexNativeProbeError("probe has no root identity")
    if not isinstance(messages, list):
        raise CodexNativeProbeError("probe messages are unavailable")

    child_threads: set[str] = set()
    collaboration: list[dict[str, Any]] = []
    forbidden_items: list[str] = []
    root_finals: list[str] = []
    usage_by_thread: dict[str, dict[str, int]] = {}
    harmless_items = {"userMessage", "agentMessage", "reasoning", "error"}
    collaboration_items = {"collabAgentToolCall", "subAgentActivity"}
    for message in messages:
        if not isinstance(message, dict):
            raise CodexNativeProbeError("probe message is not an object")
        params = message.get("params")
        if message.get("method") == "thread/started" and isinstance(params, dict):
            thread = params.get("thread")
            if (
                isinstance(thread, dict)
                and thread.get("parentThreadId") == root_thread_id
                and isinstance(thread.get("id"), str)
            ):
                child_threads.add(thread["id"])
        if (
            message.get("method") == "thread/tokenUsage/updated"
            and isinstance(params, dict)
            and isinstance(params.get("threadId"), str)
        ):
            usage_by_thread[params["threadId"]] = _usage_total(params)
        thread_id, item = _item(message)
        if item is None:
            continue
        item_type = item.get("type")
        if item_type == "subAgentActivity" and isinstance(item.get("agentThreadId"), str):
            child_threads.add(item["agentThreadId"])
        if item_type == "collabAgentToolCall":
            collaboration.append(item)
            for receiver in item.get("receiverThreadIds", []):
                if isinstance(receiver, str) and receiver != root_thread_id:
                    child_threads.add(receiver)
        elif item_type == "agentMessage" and thread_id == root_thread_id:
            phase = item.get("phase")
            if phase in {None, "final_answer"} and isinstance(item.get("text"), str):
                root_finals.append(item["text"])
        elif item_type not in harmless_items | collaboration_items:
            forbidden_items.append(str(item_type))

    if forbidden_items:
        raise CodexNativeProbeError(
            f"probe used forbidden item types: {sorted(set(forbidden_items))}"
        )
    if len(child_threads) != 1:
        raise CodexNativeProbeError("probe did not expose exactly one child thread")
    child_thread_id = next(iter(child_threads))
    spawn = [item for item in collaboration if item.get("tool") == "spawnAgent"]
    waits = [item for item in collaboration if item.get("tool") == "wait"]
    other_actions = [
        item.get("tool")
        for item in collaboration
        if item.get("tool") not in {"spawnAgent", "wait"}
    ]
    if len(spawn) != 1 or len(waits) != 1 or other_actions:
        raise CodexNativeProbeError("probe collaboration topology is not one spawn and one wait")
    spawn_item = spawn[0]
    plan = capability._object(capability.PLAN_PATH)
    controls = plan["provider_controls"]
    if (
        spawn_item.get("status") != "completed"
        or spawn_item.get("receiverThreadIds") != [child_thread_id]
        or spawn_item.get("model") != controls["subagent_model"]
        or spawn_item.get("reasoningEffort") != controls["subagent_effort"]
        or not isinstance(spawn_item.get("prompt"), str)
    ):
        raise CodexNativeProbeError("spawn item does not prove the frozen child controls")
    states = waits[0].get("agentsStates")
    child_state = states.get(child_thread_id) if isinstance(states, dict) else None
    if not isinstance(child_state, dict) or child_state.get("status") != "completed":
        raise CodexNativeProbeError("wait item does not prove child completion")
    if set(usage_by_thread) < {root_thread_id, child_thread_id}:
        raise CodexNativeProbeError("separate root and child usage was not observed")
    if len(root_finals) != 1:
        raise CodexNativeProbeError("probe has no unique root final answer")
    critique = _decode_critique(root_finals[0], probe_plan)
    try:
        score = response_scoring._score(
            critique,
            candidate_id=plan["candidate"]["candidate_id"],
            arm="native_isolated",
        )
    except response_scoring.NativeContextResponseError as exc:
        raise CodexNativeProbeError(f"critic score is invalid: {exc}") from exc
    score["series_id"] = plan["series_id"]
    score["arm"] = "codex_native_isolated_capability"
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed",
        "apparatus_revision": apparatus_revision or workflow._apparatus_revision(),
        "candidate_id": plan["candidate"]["candidate_id"],
        "model": controls["root_model"],
        "root_thread_id": root_thread_id,
        "root_turn_id": root_turn_id,
        "child_thread_id": child_thread_id,
        "collaboration": {
            "spawn_count": 1,
            "wait_count": 1,
            "spawn_model": spawn_item["model"],
            "spawn_effort": spawn_item["reasoningEffort"],
            "spawn_prompt_bytes": len(spawn_item["prompt"].encode("utf-8")),
            "spawn_prompt_sha256": hashlib.sha256(
                spawn_item["prompt"].encode("utf-8")
            ).hexdigest(),
        },
        "usage": {
            "root": usage_by_thread[root_thread_id],
            "child": usage_by_thread[child_thread_id],
            "sum_input_tokens": usage_by_thread[root_thread_id]["input_tokens"]
            + usage_by_thread[child_thread_id]["input_tokens"],
        },
        "timing": {"completion_ms": capture.get("completion_ms")},
        "critique": critique,
        "score": score,
        "probe_plan_sha256": probe_plan["plan_sha256"],
        "root_prompt_sha256": probe_plan["root_prompt_sha256"],
    }


def _host_replacements(probe_plan: dict[str, Any]) -> dict[str, str]:
    replacements = {
        str(REPO_ROOT.resolve()): "<repo>",
        str((Path.home() / ".codex").resolve()): "<codex-home>",
    }
    executable = Path(probe_plan["launch"][0])
    if executable.is_absolute():
        replacements[str(executable.resolve())] = "<resolved-codex-executable>"
    return replacements


def _sanitize_opaque(
    value: Any, *, replacements: dict[str, str] | None = None
) -> Any:
    replacements = replacements or {}
    if isinstance(value, list):
        return [
            _sanitize_opaque(item, replacements=replacements) for item in value
        ]
    if isinstance(value, str):
        for source, replacement in replacements.items():
            value = value.replace(source, replacement)
        return value
    if not isinstance(value, dict):
        return value
    sanitized = {}
    for key, item in value.items():
        if key in {
            "encrypted_content",
            "encryptedContent",
            "installationId",
            "serverName",
        } and isinstance(item, str):
            sanitized[key] = {
                "bytes": len(item.encode("utf-8")),
                "sha256": hashlib.sha256(item.encode("utf-8")).hexdigest(),
            }
        else:
            sanitized[key] = _sanitize_opaque(item, replacements=replacements)
    return sanitized


def _redacted_probe_plan(probe_plan: dict[str, Any]) -> dict[str, Any]:
    stored_plan = dict(probe_plan)
    stored_plan["turn_start"] = {
        **probe_plan["turn_start"],
        "input": "<redacted; see root prompt hash and bytes>",
    }
    return stored_plan


def _reserve_evidence(
    run_dir: Path,
    *,
    probe_plan: dict[str, Any],
    usage_checkpoint: dict[str, Any],
    apparatus_revision: str,
) -> None:
    resolved = run_dir.resolve()
    if resolved.exists():
        raise CodexNativeProbeError(f"run directory already exists: {resolved}")
    resolved.mkdir(parents=True)
    stored_plan = _sanitize_opaque(
        _redacted_probe_plan(probe_plan),
        replacements=_host_replacements(probe_plan),
    )
    (resolved / "probe-plan.json").write_text(
        canonical_json(stored_plan) + "\n", encoding="utf-8"
    )
    (resolved / "usage-checkpoint.json").write_text(
        canonical_json(usage_checkpoint) + "\n", encoding="utf-8"
    )
    (resolved / "attempt.json").write_text(
        canonical_json(
            {
                "schema_version": 1,
                "status": "reserved",
                "reserved_at": _utc_now(),
                "apparatus_revision": apparatus_revision,
                "retry_requires_plan_change": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_capture_evidence(
    run_dir: Path,
    *,
    capture: dict[str, Any],
    result: dict[str, Any] | None,
    error: str | None,
) -> None:
    resolved = run_dir.resolve()
    if not resolved.is_dir():
        raise CodexNativeProbeError(f"run directory was not reserved: {resolved}")
    replacements = {
        str(REPO_ROOT.resolve()): "<repo>",
        str((Path.home() / ".codex").resolve()): "<codex-home>",
    }
    sanitized_messages = _sanitize_opaque(
        capture["messages"], replacements=replacements
    )
    (resolved / "events.jsonl").write_text(
        "".join(canonical_json(message) + "\n" for message in sanitized_messages),
        encoding="utf-8",
    )
    (resolved / "stderr.log").write_text(capture["stderr"], encoding="utf-8")
    capture_record = {
        key: value
        for key, value in capture.items()
        if key not in {"messages", "stderr"}
    }
    capture_record["event_count"] = len(capture["messages"])
    (resolved / "capture.json").write_text(
        canonical_json(capture_record) + "\n", encoding="utf-8"
    )
    if result is not None:
        (resolved / "result.json").write_text(
            canonical_json(result) + "\n", encoding="utf-8"
        )
    if error is not None:
        (resolved / "disposition.json").write_text(
            canonical_json(
                {
                    "schema_version": 1,
                    "status": "excluded",
                    "reason": error,
                    "model_call_may_have_started": bool(
                        capture.get("turn_start_sent")
                    ),
                    "evidence_preserved": True,
                    "retry_allowed": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )


def _installed_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    version = (completed.stdout or completed.stderr).strip()
    if completed.returncode or not version:
        raise CodexNativeProbeError("Codex version probe failed")
    return version


def execute_probe(
    *,
    executable: str,
    run_dir: Path,
    expected_harness_version: str,
    expected_plan_sha256: str,
    expected_root_prompt_sha256: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    plan = capability._object(capability.PLAN_PATH)
    if plan.get("status") != "ready":
        raise CodexNativeProbeError(
            "probe is not ready; record a below-threshold usage checkpoint and commit status ready"
        )
    executable = _resolved_executable(executable)
    probe_plan = capability.build_probe(executable=executable)
    expected = plan["provider_controls"]["harness_version"]
    actual_version = _installed_version(executable)
    if expected_harness_version != expected or actual_version != expected:
        raise CodexNativeProbeError("Codex harness version does not match the frozen plan")
    if expected_plan_sha256 != probe_plan["plan_sha256"]:
        raise CodexNativeProbeError("capability plan hash does not match")
    if expected_root_prompt_sha256 != probe_plan["root_prompt_sha256"]:
        raise CodexNativeProbeError("root prompt hash does not match")
    resolved_run_dir = run_dir.resolve()
    workspace = Path(probe_plan["workspace"]).resolve()
    configured_run = Path(plan["runner"]["run_directory"])
    if configured_run.is_absolute() or ".." in configured_run.parts:
        raise CodexNativeProbeError("frozen run directory is invalid")
    expected_run_dir = (capability.EXPERIMENT_ROOT / configured_run).resolve()
    if resolved_run_dir != expected_run_dir:
        raise CodexNativeProbeError(
            f"run directory does not match the frozen plan: {expected_run_dir}"
        )
    if resolved_run_dir.exists():
        raise CodexNativeProbeError(
            f"run directory already exists: {resolved_run_dir}"
        )
    if resolved_run_dir == workspace or resolved_run_dir.is_relative_to(workspace):
        raise CodexNativeProbeError("run directory must be outside the worker workspace")
    apparatus_revision = workflow._apparatus_revision()
    preflight_probe(probe_plan, timeout_seconds=min(timeout_seconds, 30.0))
    threshold = plan["call_budget"]["stop_threshold_percent"]
    checkpoint = codex_usage_snapshot.read_snapshot(
        executable=executable,
        stop_threshold_percent=threshold,
    )
    if checkpoint["decision"] != "proceed":
        raise CodexNativeProbeError("current usage reached the probe stop threshold")
    _reserve_evidence(
        resolved_run_dir,
        probe_plan=probe_plan,
        usage_checkpoint=checkpoint,
        apparatus_revision=apparatus_revision,
    )
    result: dict[str, Any] | None = None
    error: str | None = None
    try:
        capture = capture_probe(probe_plan, timeout_seconds=timeout_seconds)
    except CodexNativeProbeError as exc:
        capture = {
            "schema_version": 1,
            "started_at": _utc_now(),
            "completed_at": _utc_now(),
            "root_thread_id": None,
            "root_turn_id": None,
            "turn_start_sent": False,
            "messages": [],
            "stderr": "",
            "capture_error": str(exc),
        }
    try:
        result = summarize_capture(
            capture,
            probe_plan,
            apparatus_revision=apparatus_revision,
        )
    except CodexNativeProbeError as exc:
        error = str(exc)
    _write_capture_evidence(
        resolved_run_dir,
        capture=capture,
        result=result,
        error=error,
    )
    if error is not None:
        raise CodexNativeProbeError(f"probe excluded; evidence preserved: {error}")
    assert result is not None
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="codex")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--expected-harness-version")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--expected-root-prompt-sha256")
    parser.add_argument("--timeout", type=float, default=300.0)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.preflight:
            executable = _resolved_executable(args.executable)
            probe_plan = capability.build_probe(executable=executable)
            expected_version = capability._object(capability.PLAN_PATH)[
                "provider_controls"
            ]["harness_version"]
            if _installed_version(executable) != expected_version:
                raise CodexNativeProbeError(
                    "Codex harness version does not match the frozen plan"
                )
            print(
                canonical_json(
                    preflight_probe(probe_plan, timeout_seconds=args.timeout)
                )
            )
            return 0
        if not args.execute:
            executable = _resolved_executable(args.executable)
            print(canonical_json(capability.public_plan(executable=executable)))
            return 0
        required = {
            "--run-dir": args.run_dir,
            "--expected-harness-version": args.expected_harness_version,
            "--expected-plan-sha256": args.expected_plan_sha256,
            "--expected-root-prompt-sha256": args.expected_root_prompt_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise CodexNativeProbeError(
                "live probe requires " + ", ".join(missing)
            )
        result = execute_probe(
            executable=args.executable,
            run_dir=args.run_dir,
            expected_harness_version=args.expected_harness_version,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_root_prompt_sha256=args.expected_root_prompt_sha256,
            timeout_seconds=args.timeout,
        )
        print(canonical_json(result))
        return 0
    except (
        CodexNativeProbeError,
        capability.CodexNativeCapabilityError,
        codex_usage_snapshot.CodexUsageSnapshotError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

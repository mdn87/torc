"""Read a sanitized Codex usage snapshot through the local app-server protocol."""

from __future__ import annotations

import argparse
import json
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

from torc.canonical import canonical_json  # noqa: E402


class CodexUsageSnapshotError(RuntimeError):
    """Raised when the local app server cannot return a safe usage snapshot."""


def _pump_lines(stream: TextIO, output: queue.Queue[str]) -> None:
    for line in stream:
        output.put(line)


def _request(
    process: subprocess.Popen[str],
    lines: queue.Queue[str],
    *,
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    if process.stdin is None:
        raise CodexUsageSnapshotError("app-server stdin is unavailable")
    message = {"id": request_id, "method": method, "params": params}
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CodexUsageSnapshotError(f"app-server request timed out: {method}")
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise CodexUsageSnapshotError(
                f"app-server request timed out: {method}"
            ) from exc
        try:
            response = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(response, dict) or response.get("id") != request_id:
            continue
        if "error" in response:
            raise CodexUsageSnapshotError(
                f"app-server request failed: {method}: {response['error']}"
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise CodexUsageSnapshotError(
                f"app-server returned no result object: {method}"
            )
        return result


def _window(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("usedPercent"), int):
        raise CodexUsageSnapshotError("rate-limit window is malformed")
    return {
        "used_percent": value["usedPercent"],
        "window_duration_minutes": value.get("windowDurationMins"),
        "resets_at": value.get("resetsAt"),
    }


def sanitize_snapshot(
    result: dict[str, Any], *, stop_threshold_percent: int
) -> dict[str, Any]:
    rate_limits = result.get("rateLimits")
    if not isinstance(rate_limits, dict):
        raise CodexUsageSnapshotError("usage response has no rate-limit snapshot")
    primary = _window(rate_limits.get("primary"))
    secondary = _window(rate_limits.get("secondary"))
    reset_credits = result.get("rateLimitResetCredits")
    available = (
        reset_credits.get("availableCount")
        if isinstance(reset_credits, dict)
        else None
    )
    used_percent = primary["used_percent"] if primary is not None else None
    decision = (
        "stop"
        if used_percent is None or used_percent >= stop_threshold_percent
        else "proceed"
    )
    return {
        "schema_version": 1,
        "observed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "source": "codex app-server account/rateLimits/read",
        "ordinary_usage_allowed": result.get("ordinaryUsageAllowed"),
        "plan_type": rate_limits.get("planType"),
        "primary": primary,
        "secondary": secondary,
        "reset_credits_available": available,
        "reset_credits_consumed": 0,
        "stop_threshold_percent": stop_threshold_percent,
        "decision": decision,
    }


def read_snapshot(
    *,
    executable: str = "codex",
    stop_threshold_percent: int = 75,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    resolved_executable = shutil.which(executable)
    if not resolved_executable:
        raise CodexUsageSnapshotError(
            f"Codex executable is unavailable: {executable}"
        )
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            [resolved_executable, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise CodexUsageSnapshotError(f"cannot start Codex app server: {exc}") from exc
    if process.stdout is None:
        process.kill()
        raise CodexUsageSnapshotError("app-server stdout is unavailable")
    lines: queue.Queue[str] = queue.Queue()
    reader = threading.Thread(
        target=_pump_lines,
        args=(process.stdout, lines),
        daemon=True,
    )
    reader.start()
    try:
        _request(
            process,
            lines,
            request_id=1,
            method="initialize",
            params={
                "clientInfo": {"name": "torc-experiment", "version": "1.0"},
                "capabilities": {"experimentalApi": True},
            },
            timeout_seconds=timeout_seconds,
        )
        result = _request(
            process,
            lines,
            request_id=2,
            method="account/rateLimits/read",
            params={
                "excludeResetCreditDetails": True,
                "supportsLunaReserve": False,
            },
            timeout_seconds=timeout_seconds,
        )
        return sanitize_snapshot(
            result, stop_threshold_percent=stop_threshold_percent
        )
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="codex")
    parser.add_argument("--stop-threshold", type=int, default=75)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.stop_threshold <= 100:
        parser.error("--stop-threshold must be between 1 and 100")
    try:
        snapshot = read_snapshot(
            executable=args.executable,
            stop_threshold_percent=args.stop_threshold,
            timeout_seconds=args.timeout,
        )
        rendered = canonical_json(snapshot)
        if args.output is not None:
            if args.output.exists():
                raise CodexUsageSnapshotError(
                    f"refusing to replace usage evidence: {args.output}"
                )
            if not args.output.parent.is_dir():
                raise CodexUsageSnapshotError(
                    f"usage evidence parent does not exist: {args.output.parent}"
                )
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if snapshot["decision"] == "proceed" else 3
    except CodexUsageSnapshotError as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

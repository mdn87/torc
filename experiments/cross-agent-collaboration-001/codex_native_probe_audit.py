"""Audit the preserved native-subagent capability probe without model calls."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import codex_native_probe_runner as runner  # noqa: E402
import native_context_response as response_scoring  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
DEFAULT_RUN = (
    EXPERIMENT_ROOT
    / "runs"
    / "codex-native-capability-001"
    / "01-native-isolated"
)
DEFAULT_OUTPUT = EXPERIMENT_ROOT / "codex-native-capability-001-analysis.json"
BASELINE_RUNS = (
    "01-refactor-compact",
    "04-refactor-compact",
    "05-refactor-compact",
)


class CodexNativeProbeAuditError(RuntimeError):
    """Raised when preserved capability evidence is incomplete or inconsistent."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexNativeProbeAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CodexNativeProbeAuditError(f"expected a JSON object: {path}")
    return value


def _events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CodexNativeProbeAuditError(f"cannot read {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexNativeProbeAuditError(
                f"invalid event JSON at line {line_number}"
            ) from exc
        if not isinstance(event, dict):
            raise CodexNativeProbeAuditError(
                f"event at line {line_number} is not an object"
            )
        events.append(event)
    return events


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        raise CodexNativeProbeAuditError("comparison denominator must be positive")
    return round(numerator / denominator, 6)


def _baseline() -> dict[str, Any]:
    root = EXPERIMENT_ROOT / "runs" / "critic-transport-002"
    scores = [_object(root / run_id / "probe-score.json") for run_id in BASELINE_RUNS]
    if any(
        score.get("candidate_id") != "refactor-baseline-v1"
        or score.get("critic_context") != "claim-capsule-candidate-v1"
        for score in scores
    ):
        raise CodexNativeProbeAuditError("direct compact baseline identity drifted")
    return {
        "run_ids": list(BASELINE_RUNS),
        "sample_count": len(scores),
        "input_tokens": [score["usage"]["input_tokens"] for score in scores],
        "median_input_tokens": statistics.median(
            score["usage"]["input_tokens"] for score in scores
        ),
        "median_completion_ms": statistics.median(
            score["timing"]["completion_ms"] for score in scores
        ),
        "median_defect_area_recall": statistics.median(
            score["defect_area_recall"] for score in scores
        ),
    }


def audit_run(run_dir: Path = DEFAULT_RUN) -> dict[str, Any]:
    """Return the deterministic post-hoc audit of the single preserved call."""
    resolved = run_dir.resolve()
    capture = _object(resolved / "capture.json")
    disposition = _object(resolved / "disposition.json")
    probe_plan = _object(resolved / "probe-plan.json")
    events = _events(resolved / "events.jsonl")
    if disposition.get("status") != "excluded" or disposition.get("retry_allowed"):
        raise CodexNativeProbeAuditError("probe disposition is not frozen as excluded")
    root_thread_id = capture.get("root_thread_id")
    if not isinstance(root_thread_id, str):
        raise CodexNativeProbeAuditError("capture has no root thread")

    child_activity: dict[str, list[str]] = {}
    completed_collaboration: list[dict[str, Any]] = []
    usage_by_thread: dict[str, dict[str, int]] = {}
    finals_by_thread: dict[str, list[str]] = {}
    settings_by_thread: dict[str, dict[str, Any]] = {}
    started_threads: set[str] = set()
    child_user_message_count = 0
    for event in events:
        params = event.get("params")
        if not isinstance(params, dict):
            continue
        thread_id = params.get("threadId")
        if event.get("method") == "thread/started":
            thread = params.get("thread")
            if isinstance(thread, dict) and isinstance(thread.get("id"), str):
                started_threads.add(thread["id"])
        elif (
            event.get("method") == "thread/settings/updated"
            and isinstance(thread_id, str)
            and isinstance(params.get("threadSettings"), dict)
        ):
            settings_by_thread[thread_id] = params["threadSettings"]
        elif (
            event.get("method") == "thread/tokenUsage/updated"
            and isinstance(thread_id, str)
        ):
            usage_by_thread[thread_id] = runner._usage_total(params)

        item_thread_id, item = runner._item(event)
        if item is None or not isinstance(item_thread_id, str):
            continue
        item_type = item.get("type")
        if item_type == "subAgentActivity":
            child_id = item.get("agentThreadId")
            kind = item.get("kind")
            if isinstance(child_id, str) and isinstance(kind, str):
                child_activity.setdefault(child_id, []).append(kind)
        elif item_type == "collabAgentToolCall":
            completed_collaboration.append(item)
        elif item_type == "agentMessage" and item.get("phase") == "final_answer":
            text = item.get("text")
            if isinstance(text, str):
                finals_by_thread.setdefault(item_thread_id, []).append(text)
        elif item_type == "userMessage" and item_thread_id != root_thread_id:
            child_user_message_count += 1

    if len(child_activity) != 1:
        raise CodexNativeProbeAuditError("evidence does not identify exactly one child")
    child_thread_id = next(iter(child_activity))
    if child_activity[child_thread_id] != ["started", "completed"]:
        raise CodexNativeProbeAuditError("child activity lifecycle is incomplete")
    spawn_items = [
        item for item in completed_collaboration if item.get("tool") == "spawnAgent"
    ]
    wait_items = [
        item for item in completed_collaboration if item.get("tool") == "wait"
    ]
    if spawn_items or len(wait_items) != 1:
        raise CodexNativeProbeAuditError("observed collaboration shape drifted")
    if set(usage_by_thread) < {root_thread_id, child_thread_id}:
        raise CodexNativeProbeAuditError("separate root and child usage is missing")
    root_finals = finals_by_thread.get(root_thread_id, [])
    child_finals = finals_by_thread.get(child_thread_id, [])
    if len(root_finals) != 1 or len(child_finals) != 1:
        raise CodexNativeProbeAuditError("root or child final answer is not unique")
    if root_finals[0] != child_finals[0]:
        raise CodexNativeProbeAuditError("root did not return the child answer unchanged")

    critique = runner._decode_critique(root_finals[0], probe_plan)
    score = response_scoring._score(
        critique,
        candidate_id="refactor-baseline-v1",
        arm="codex_native_isolated_capability",
    )
    root_usage = usage_by_thread[root_thread_id]
    child_usage = usage_by_thread[child_thread_id]
    combined_input = root_usage["input_tokens"] + child_usage["input_tokens"]
    baseline = _baseline()
    baseline_input = baseline["median_input_tokens"]
    completion_ms = capture.get("completion_ms")
    if not isinstance(completion_ms, (int, float)) or isinstance(completion_ms, bool):
        raise CodexNativeProbeAuditError("capture completion time is invalid")
    root_settings = settings_by_thread.get(root_thread_id)
    if not isinstance(root_settings, dict):
        raise CodexNativeProbeAuditError("root settings are not observable")

    return {
        "schema_version": 1,
        "analysis_id": "codex-native-capability-001",
        "status": "capability_rejected_confirmed",
        "run_id": resolved.name,
        "apparatus_revision": "2c0908647f42f28c550caea525856379766baca2",
        "provider": "codex",
        "model": "gpt-6-sol",
        "effort": "low",
        "quality": {
            "changes_requested_correct": score["changes_requested_correct"],
            "defect_area_recall": score["defect_area_recall"],
            "finding_count": score["finding_count"],
            "root_returned_child_answer_unchanged": True,
            "direct_compact_median_defect_area_recall": baseline[
                "median_defect_area_recall"
            ],
        },
        "observability": {
            "one_child_activity_lifecycle": True,
            "separate_root_and_child_usage": True,
            "completed_wait_item_count": 1,
            "completed_spawn_agent_item_count": 0,
            "child_thread_started_event_observed": child_thread_id in started_threads,
            "child_settings_observed": child_thread_id in settings_by_thread,
            "child_user_message_observed": child_user_message_count > 0,
            "child_prompt_observed": False,
            "child_model_and_effort_observed": False,
            "root_model_observed": root_settings.get("model"),
            "root_effort_observed": root_settings.get("effort"),
        },
        "usage": {
            "root": root_usage,
            "child": child_usage,
            "combined_input_tokens": combined_input,
            "direct_compact_baseline": baseline,
            "child_to_direct_compact_input_ratio": _ratio(
                child_usage["input_tokens"], baseline_input
            ),
            "combined_to_direct_compact_input_ratio": _ratio(
                combined_input, baseline_input
            ),
            "combined_input_increase_percent": round(
                (combined_input - baseline_input) / baseline_input * 100,
                3,
            ),
        },
        "timing": {
            "native_completion_ms": completion_ms,
            "direct_compact_median_completion_ms": baseline[
                "median_completion_ms"
            ],
            "native_to_direct_compact_completion_ratio": _ratio(
                completion_ms, baseline["median_completion_ms"]
            ),
        },
        "decision": {
            "plus_backed_series_allowed": False,
            "automatic_retry_allowed": False,
            "reason": (
                "The local app-server proves a child ran and reports separate usage, "
                "but it does not expose the spawn prompt or the child's model and effort."
            ),
            "cost_implication": (
                "The child alone used slightly less input than a direct compact critic, "
                "but three root orchestration rounds made combined native input about "
                "four times the direct baseline."
            ),
        },
        "limitations": [
            "This is one capability call, not a repeated performance series.",
            (
                "The combined total sums separately reported thread totals; it does not "
                "infer hidden provider billing semantics."
            ),
            (
                "The child model and effort are frozen inputs but were not independently "
                "emitted in child events."
            ),
            (
                "Service timing is uncontrolled and the native and direct calls occurred "
                "in different windows."
            ),
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_run(args.run_dir)
        rendered = canonical_json(result)
        if args.output is not None:
            if args.output.exists():
                raise CodexNativeProbeAuditError(
                    f"refusing to replace analysis: {args.output}"
                )
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    except (
        CodexNativeProbeAuditError,
        runner.CodexNativeProbeError,
        response_scoring.NativeContextResponseError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

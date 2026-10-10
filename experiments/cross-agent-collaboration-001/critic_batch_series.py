"""Plan, execute, and report the counterbalanced compact-critic batch series."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import codex_usage_snapshot  # noqa: E402
import critic_batch_probe as batch  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-batch-confirmation-004-plan.json"


class CriticBatchSeriesError(RuntimeError):
    """Raised when a confirmation run cannot preserve its frozen controls."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticBatchSeriesError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticBatchSeriesError(f"expected a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _scheduled_run(plan: dict[str, Any], run_index: int) -> dict[str, Any]:
    schedule = plan["counterbalanced_schedule"]
    if not isinstance(run_index, int) or isinstance(run_index, bool):
        raise CriticBatchSeriesError("run index must be an integer")
    if run_index < 1 or run_index > len(schedule):
        raise CriticBatchSeriesError("run index is outside the frozen schedule")
    run = schedule[run_index - 1]
    if run.get("run_index") != run_index:
        raise CriticBatchSeriesError("frozen schedule indices are not contiguous")
    return run


def _resolve_run_dir(plan: dict[str, Any], run: dict[str, Any]) -> Path:
    series_root = Path(plan["call_budget"]["series_directory"])
    run_id = Path(run["run_id"])
    if (
        series_root.is_absolute()
        or run_id.is_absolute()
        or ".." in series_root.parts
        or ".." in run_id.parts
        or len(run_id.parts) != 1
    ):
        raise CriticBatchSeriesError("frozen run directory is unsafe")
    return (EXPERIMENT_ROOT / series_root / run_id).resolve()


def _verify_apparatus(plan: dict[str, Any]) -> list[dict[str, str]]:
    verified = []
    for item in plan.get("apparatus_inputs", []):
        path = REPO_ROOT / item["path"]
        observed = _sha256_file(path)
        if observed != item["sha256"]:
            raise CriticBatchSeriesError(f"apparatus hash drifted for {item['path']}: {observed}")
        verified.append({"path": item["path"], "sha256": observed})
    if not verified:
        raise CriticBatchSeriesError("frozen apparatus inputs are missing")
    return verified


def build_run(run_index: int) -> dict[str, Any]:
    """Return one exact, model-free prompt plan without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "frozen_before_live_runs"}:
        raise CriticBatchSeriesError("batch series is not plannable")
    run = _scheduled_run(plan, run_index)
    candidate_ids = run["candidate_order"]
    payloads = batch._payloads(
        {
            "provider_controls": plan["provider_controls"],
            "candidates": candidate_ids,
        }
    )
    prompt = batch._prompt(payloads)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "run_index": run_index,
        "run_id": run["run_id"],
        "candidate_order": candidate_ids,
        "candidates": [
            {key: value for key, value in payload.items() if key != "payload"}
            for payload in payloads
        ],
        "prompt_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "plan_sha256": _sha256_file(PLAN_PATH),
        "prompt": prompt,
    }


def _existing_results(plan: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for run in plan["counterbalanced_schedule"]:
        run_dir = _resolve_run_dir(plan, run)
        result_path = run_dir / "result.json"
        disposition_path = run_dir / "disposition.json"
        if result_path.exists() and disposition_path.exists():
            raise CriticBatchSeriesError(f"run has both result and disposition: {run['run_id']}")
        if disposition_path.exists():
            disposition = _object(disposition_path)
            results.append(
                {
                    "run_index": run["run_index"],
                    "run_id": run["run_id"],
                    "status": "excluded",
                    "reason": disposition.get("reason", "unknown"),
                }
            )
        elif result_path.exists():
            result = _object(result_path)
            if result.get("candidate_order") != run["candidate_order"]:
                raise CriticBatchSeriesError(f"candidate order drifted for {run['run_id']}")
            results.append(result)
    return results


def _assert_next_run(plan: dict[str, Any], run_index: int) -> None:
    results = _existing_results(plan)
    if any(item.get("status") == "excluded" for item in results):
        raise CriticBatchSeriesError("series stopped after an excluded run")
    if any(not item.get("quality_passed", False) for item in results):
        raise CriticBatchSeriesError("series stopped after a quality failure")
    completed = {item["run_index"] for item in results}
    expected = len(completed) + 1
    if completed != set(range(1, expected)) or run_index != expected:
        raise CriticBatchSeriesError(f"next permitted run index is {expected}")


def execute_run(
    *,
    run_index: int,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "frozen_before_live_runs":
        raise CriticBatchSeriesError("batch series is not frozen for live runs")
    _verify_apparatus(plan)
    probe = build_run(run_index)
    if expected_plan_sha256 != probe["plan_sha256"]:
        raise CriticBatchSeriesError("batch plan hash does not match")
    if expected_prompt_sha256 != probe["prompt_sha256"]:
        raise CriticBatchSeriesError("batch prompt hash does not match")
    run = _scheduled_run(plan, run_index)
    expected_run_dir = _resolve_run_dir(plan, run)
    if run_dir.resolve() != expected_run_dir:
        raise CriticBatchSeriesError("run directory does not match the frozen plan")
    if expected_run_dir.exists():
        raise CriticBatchSeriesError(f"run directory already exists: {run_dir}")
    _assert_next_run(plan, run_index)
    threshold = plan["call_budget"]["stop_threshold_percent"]
    checkpoint = codex_usage_snapshot.read_snapshot(stop_threshold_percent=threshold)
    if checkpoint["decision"] != "proceed":
        raise CriticBatchSeriesError("current usage reached the batch stop threshold")

    expected_run_dir.mkdir(parents=True)
    public_probe = {key: value for key, value in probe.items() if key != "prompt"}
    _write_json(expected_run_dir / "probe-plan.json", public_probe)
    _write_json(expected_run_dir / "usage-checkpoint.json", checkpoint)
    attempt_path = expected_run_dir / "attempt.json"
    _write_json(
        attempt_path,
        {
            "schema_version": 1,
            "status": "reserved",
            "apparatus_revision": plan["apparatus_revision"],
            "retry_requires_plan_change": True,
        },
    )
    phase_dir = expected_run_dir / "phase"
    settings = workflow._provider_settings(workflow.load_manifest(), "codex")
    error: Exception | None = None
    record: dict[str, Any] | None = None
    try:
        first_candidate = probe["candidates"][0]
        workspace = EXPERIMENT_ROOT / "fixtures" / first_candidate["fixture_id"] / "agent-visible"
        record = workflow._run_worker(
            settings=settings,
            workspace=workspace,
            prompt=probe["prompt"],
            effort=plan["provider_controls"]["effort"],
            role="critic",
            tool_mode="none",
            session_mode="fresh-ephemeral",
            session_id=None,
            timeout_seconds=workflow.load_manifest()["timeout_seconds"],
            output_dir=phase_dir,
        )
        output = workflow._phase_output_object("codex", phase_dir)
        scored = batch.validate_batch(
            output,
            candidate_ids=probe["candidate_order"],
            model=plan["provider_controls"]["model"],
        )
    except (
        batch.CriticBatchProbeError,
        workflow.WorkflowRunnerError,
        worker_runner.WorkerRunnerError,
    ) as exc:
        error = exc
    if error is not None:
        _write_json(
            expected_run_dir / "disposition.json",
            {
                "schema_version": 1,
                "status": "excluded",
                "reason": str(error),
                "model_call_may_have_started": (phase_dir / "worker-run.json").exists(),
                "retry_allowed": False,
            },
        )
        raise CriticBatchSeriesError(f"batch run excluded; evidence preserved: {error}") from error
    assert record is not None
    quality_passed = all(
        item["score"]["changes_requested_correct"]
        and item["score"]["defect_area_recall"] == 1.0
        and item["score"]["unsupported_finding_count"] == 0
        for item in scored
    )
    result = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "completed",
        "run_index": run_index,
        "run_id": run["run_id"],
        "candidate_order": probe["candidate_order"],
        "prompt_bytes": probe["prompt_bytes"],
        "prompt_sha256": probe["prompt_sha256"],
        "candidate_results": scored,
        "quality_passed": quality_passed,
        "usage": record["usage"],
        "timing": record["timing"],
    }
    _write_json(expected_run_dir / "batch-output.json", output)
    _write_json(expected_run_dir / "result.json", result)
    _write_json(
        attempt_path,
        {
            "schema_version": 1,
            "status": "completed",
            "apparatus_revision": plan["apparatus_revision"],
            "retry_requires_plan_change": True,
        },
    )
    return result


def summarize_results(plan: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = batch._baseline(plan)
    excluded = [item for item in results if item.get("status") == "excluded"]
    completed = [item for item in results if item.get("status") == "completed"]
    scheduled_count = len(plan["counterbalanced_schedule"])
    per_candidate_position: dict[str, dict[str, dict[str, int]]] = {}
    for item in completed:
        for position, candidate in enumerate(item["candidate_results"], start=1):
            candidate_id = candidate["candidate_id"]
            position_result = per_candidate_position.setdefault(candidate_id, {}).setdefault(
                str(position), {"runs": 0, "quality_passes": 0}
            )
            position_result["runs"] += 1
            score = candidate["score"]
            if (
                score["changes_requested_correct"]
                and score["defect_area_recall"] == 1.0
                and score["unsupported_finding_count"] == 0
            ):
                position_result["quality_passes"] += 1
    quality_passed = bool(completed) and all(item["quality_passed"] for item in completed)
    report: dict[str, Any] = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "in_progress",
        "scheduled_run_count": scheduled_count,
        "completed_run_count": len(completed),
        "excluded_run_count": len(excluded),
        "completed_run_ids": [item["run_id"] for item in completed],
        "per_candidate_position": per_candidate_position,
        "quality_passed_so_far": quality_passed,
        "matched_direct_baseline": baseline,
        "exploratory_capability_run_excluded_from_estimate": plan["exploratory_predecessor"],
    }
    if excluded:
        report["status"] = "stopped_excluded"
        report["excluded_runs"] = excluded
        return report
    if completed and not quality_passed:
        report["status"] = "stopped_quality_failure"
        return report
    if len(completed) != scheduled_count:
        return report
    input_median = statistics.median(item["usage"]["input_tokens"] for item in completed)
    completion_median = statistics.median(item["timing"]["completion_ms"] for item in completed)
    input_ratio = input_median / baseline["summed_median_input_tokens"]
    completion_ratio = completion_median / baseline["summed_median_completion_ms"]
    input_passed = input_ratio <= plan["confirmation_thresholds"]["maximum_median_input_ratio"]
    completion_passed = (
        completion_ratio <= plan["confirmation_thresholds"]["maximum_median_completion_ratio"]
    )
    confirmed = quality_passed and input_passed and completion_passed
    report.update(
        {
            "status": "confirmed" if confirmed else "rejected",
            "median_batch_input_tokens": input_median,
            "median_batch_completion_ms": round(completion_median, 3),
            "median_input_ratio_to_summed_direct": round(input_ratio, 6),
            "median_input_reduction_percent": round((1 - input_ratio) * 100, 3),
            "median_completion_ratio_to_summed_direct": round(completion_ratio, 6),
            "input_threshold_passed": input_passed,
            "completion_threshold_passed": completion_passed,
            "confirmation_thresholds_passed": confirmed,
        }
    )
    return report


def report() -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "frozen_before_live_runs":
        raise CriticBatchSeriesError("batch series is not frozen")
    _verify_apparatus(plan)
    return summarize_results(plan, _existing_results(plan))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-index", type=int)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--expected-prompt-sha256")
    parser.add_argument("--include-prompt", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--write-report", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.report or args.write_report:
            value = report()
            if args.write_report:
                _write_json(args.write_report, value)
            print(canonical_json(value))
            return 0
        if args.run_index is None:
            raise CriticBatchSeriesError("--run-index is required")
        if not args.execute:
            value = build_run(args.run_index)
            if not args.include_prompt:
                value = {key: item for key, item in value.items() if key != "prompt"}
            print(canonical_json(value))
            return 0
        required = {
            "--run-dir": args.run_dir,
            "--expected-plan-sha256": args.expected_plan_sha256,
            "--expected-prompt-sha256": args.expected_prompt_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise CriticBatchSeriesError("live batch run requires " + ", ".join(missing))
        value = execute_run(
            run_index=args.run_index,
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(value))
        return 0
    except (
        CriticBatchSeriesError,
        batch.CriticBatchProbeError,
        codex_usage_snapshot.CodexUsageSnapshotError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Run and report the counterbalanced compact claim-link confirmation."""

from __future__ import annotations

import argparse
import hashlib
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
import critic_batch_series as batch_series  # noqa: E402
import critic_claim_link_probe as link  # noqa: E402
import critic_claim_matrix_probe as matrix  # noqa: E402
import native_context_request as request_builder  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-claim-link-confirmation-005-plan.json"


class CriticClaimLinkSeriesError(RuntimeError):
    """Raised when a claim-link confirmation run violates a frozen control."""


def _object(path: Path) -> dict[str, Any]:
    try:
        return batch_series._object(path)
    except batch_series.CriticBatchSeriesError as exc:
        raise CriticClaimLinkSeriesError(str(exc)) from exc


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _verify_apparatus(plan: dict[str, Any]) -> list[dict[str, str]]:
    verified = []
    for item in plan.get("apparatus_inputs", []):
        path = REPO_ROOT / item["path"]
        observed = _sha256_file(path)
        if observed != item["sha256"]:
            raise CriticClaimLinkSeriesError(
                f"apparatus hash drifted for {item['path']}: {observed}"
            )
        verified.append({"path": item["path"], "sha256": observed})
    if not verified:
        raise CriticClaimLinkSeriesError("frozen apparatus inputs are missing")
    return verified


def _scheduled_run(plan: dict[str, Any], run_index: int) -> dict[str, Any]:
    try:
        return batch_series._scheduled_run(plan, run_index)
    except batch_series.CriticBatchSeriesError as exc:
        raise CriticClaimLinkSeriesError(str(exc)) from exc


def _resolve_run_dir(plan: dict[str, Any], run: dict[str, Any]) -> Path:
    try:
        return batch_series._resolve_run_dir(plan, run)
    except batch_series.CriticBatchSeriesError as exc:
        raise CriticClaimLinkSeriesError(str(exc)) from exc


def _validation_plan(plan: dict[str, Any], candidate_ids: list[str]) -> dict[str, Any]:
    return {
        "candidates": candidate_ids,
        "provider_controls": plan["provider_controls"],
        "reviewable_claim_categories": plan["reviewable_claim_categories"],
        "expected_claim_statuses": plan["expected_claim_statuses"],
    }


def build_run(run_index: int) -> dict[str, Any]:
    """Return one exact model-free run plan without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "frozen_before_live_runs"}:
        raise CriticClaimLinkSeriesError("claim-link series is not plannable")
    run = _scheduled_run(plan, run_index)
    candidate_ids = run["candidate_order"]
    validation_plan = _validation_plan(plan, candidate_ids)
    payloads = batch._payloads(validation_plan)
    claim_ids = link._claim_ids(validation_plan)
    prompt = link._prompt(payloads=payloads, claim_ids=claim_ids)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "run_index": run_index,
        "run_id": run["run_id"],
        "candidate_order": candidate_ids,
        "reviewable_claim_ids": claim_ids,
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
    try:
        return batch_series._existing_results(plan)
    except batch_series.CriticBatchSeriesError as exc:
        raise CriticClaimLinkSeriesError(str(exc)) from exc


def _assert_next_run(plan: dict[str, Any], run_index: int) -> None:
    results = _existing_results(plan)
    if any(item.get("status") == "excluded" for item in results):
        raise CriticClaimLinkSeriesError("series stopped after an excluded run")
    if any(not item.get("quality_passed", False) for item in results):
        raise CriticClaimLinkSeriesError("series stopped after a quality failure")
    completed = {item["run_index"] for item in results}
    expected = len(completed) + 1
    if completed != set(range(1, expected)) or run_index != expected:
        raise CriticClaimLinkSeriesError(f"next permitted run index is {expected}")


def execute_run(
    *,
    run_index: int,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "frozen_before_live_runs":
        raise CriticClaimLinkSeriesError("claim-link series is not frozen")
    _verify_apparatus(plan)
    probe = build_run(run_index)
    if expected_plan_sha256 != probe["plan_sha256"]:
        raise CriticClaimLinkSeriesError("claim-link series plan hash does not match")
    if expected_prompt_sha256 != probe["prompt_sha256"]:
        raise CriticClaimLinkSeriesError("claim-link series prompt hash does not match")
    run = _scheduled_run(plan, run_index)
    expected_run_dir = _resolve_run_dir(plan, run)
    if run_dir.resolve() != expected_run_dir:
        raise CriticClaimLinkSeriesError("run directory does not match the frozen plan")
    if expected_run_dir.exists():
        raise CriticClaimLinkSeriesError(f"run directory already exists: {run_dir}")
    _assert_next_run(plan, run_index)
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=plan["call_budget"]["stop_threshold_percent"]
    )
    if checkpoint["decision"] != "proceed":
        raise CriticClaimLinkSeriesError(
            "current usage reached the claim-link series stop threshold"
        )

    expected_run_dir.mkdir(parents=True)
    _write_json(
        expected_run_dir / "probe-plan.json",
        {key: value for key, value in probe.items() if key != "prompt"},
    )
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
        scored = link.validate_output(
            output,
            plan=_validation_plan(plan, probe["candidate_order"]),
        )
    except (
        CriticClaimLinkSeriesError,
        link.CriticClaimLinkProbeError,
        batch.CriticBatchProbeError,
        matrix.CriticClaimMatrixProbeError,
        request_builder.NativeContextRequestError,
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
        raise CriticClaimLinkSeriesError(
            f"claim-link run excluded; evidence preserved: {error}"
        ) from error
    assert record is not None
    quality_passed = all(
        item["score"]["changes_requested_correct"]
        and item["claim_map_correct"]
        and item["structured_finding_linkage_complete"]
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
    """Summarize structured quality and aggregate confirmation cost."""
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
            if (
                candidate["score"]["changes_requested_correct"]
                and candidate["claim_map_correct"]
                and candidate["structured_finding_linkage_complete"]
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
        "excluded_predecessors": plan["excluded_predecessors"],
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
    output_median = statistics.median(item["usage"]["output_tokens"] for item in completed)
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
            "median_batch_output_tokens": output_median,
            "median_batch_completion_ms": round(completion_median, 3),
            "median_input_ratio_to_summed_direct": round(input_ratio, 6),
            "median_input_reduction_percent": round((1 - input_ratio) * 100, 3),
            "median_completion_ratio_to_summed_direct": round(completion_ratio, 6),
            "median_completion_reduction_percent": round((1 - completion_ratio) * 100, 3),
            "input_threshold_passed": input_passed,
            "completion_threshold_passed": completion_passed,
            "confirmation_thresholds_passed": confirmed,
        }
    )
    return report


def report() -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "frozen_before_live_runs":
        raise CriticClaimLinkSeriesError("claim-link series is not frozen")
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.report:
            print(canonical_json(report()))
            return 0
        if args.run_index is None:
            raise CriticClaimLinkSeriesError("--run-index is required")
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
            raise CriticClaimLinkSeriesError("live claim-link run requires " + ", ".join(missing))
        value = execute_run(
            run_index=args.run_index,
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(value))
        return 0
    except (
        CriticClaimLinkSeriesError,
        link.CriticClaimLinkProbeError,
        batch_series.CriticBatchSeriesError,
        codex_usage_snapshot.CodexUsageSnapshotError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

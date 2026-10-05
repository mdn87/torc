"""Run two counterbalanced replications of new-fixture claim-link batching."""

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
import critic_claim_link_controls as controls  # noqa: E402
import critic_claim_link_generalization as source  # noqa: E402
import fixture_control  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-claim-link-replication-008-plan.json"


class CriticClaimLinkReplicationError(RuntimeError):
    """Raised when the replication series violates a frozen control."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkReplicationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkReplicationError(f"expected a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _cell(plan: dict[str, Any], run_id: str) -> dict[str, Any]:
    matches = [item for item in plan["schedule"] if item["run_id"] == run_id]
    if len(matches) != 1:
        raise CriticClaimLinkReplicationError(f"unknown or repeated run ID: {run_id}")
    return matches[0]


def _candidates(plan: dict[str, Any], cell: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = controls._source_candidates(plan)
    try:
        selected = [by_id[candidate_id] for candidate_id in cell["candidate_order"]]
    except KeyError as exc:
        raise CriticClaimLinkReplicationError(f"unknown candidate: {exc.args[0]}") from exc
    if len(selected) != 2 or len(set(cell["candidate_order"])) != 2:
        raise CriticClaimLinkReplicationError("replication requires two unique candidates")
    return selected


def build_probe(run_id: str) -> dict[str, Any]:
    """Build one scheduled request without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "ready", "complete", "rejected"}:
        raise CriticClaimLinkReplicationError("series is not plannable")
    cell = _cell(plan, run_id)
    candidates = _candidates(plan, cell)
    claim_ids = source._claim_ids(plan, candidates)
    payloads = source._payloads(plan, candidates)
    prompt = controls._prompt(payloads=payloads, claim_ids=claim_ids)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "run_id": run_id,
        "order": cell["order"],
        "candidate_order": cell["candidate_order"],
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


def _series_root(plan: dict[str, Any]) -> Path:
    configured = Path(plan["call_budget"]["series_directory"])
    if configured.is_absolute() or ".." in configured.parts:
        raise CriticClaimLinkReplicationError("series directory is unsafe")
    return (EXPERIMENT_ROOT / configured).resolve()


def _completed_results(plan: dict[str, Any]) -> list[dict[str, Any]]:
    root = _series_root(plan)
    completed = []
    for cell in plan["schedule"]:
        run_root = root / cell["run_id"]
        if (run_root / "disposition.json").exists():
            raise CriticClaimLinkReplicationError(
                f"excluded cell stops the series: {cell['run_id']}"
            )
        result_path = run_root / "result.json"
        if not result_path.exists():
            break
        result = _object(result_path)
        if not result.get("quality_passed"):
            raise CriticClaimLinkReplicationError(
                f"quality failure stops the series: {cell['run_id']}"
            )
        completed.append(result)
    return completed


def next_cell() -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    completed = _completed_results(plan)
    if len(completed) == len(plan["schedule"]):
        return {"status": "complete", "completed_calls": len(completed)}
    probe = build_probe(plan["schedule"][len(completed)]["run_id"])
    return {
        "status": plan["status"],
        "completed_calls": len(completed),
        "next": {key: value for key, value in probe.items() if key != "prompt"},
    }


def _verify_apparatus(plan: dict[str, Any]) -> None:
    if not plan.get("apparatus_inputs"):
        raise CriticClaimLinkReplicationError("frozen apparatus inputs are missing")
    for item in plan["apparatus_inputs"]:
        observed = _sha256_file(REPO_ROOT / item["path"])
        if observed != item["sha256"]:
            raise CriticClaimLinkReplicationError(
                f"apparatus hash drifted for {item['path']}: {observed}"
            )


def execute_cell(
    *,
    run_id: str,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "ready":
        raise CriticClaimLinkReplicationError("series is not ready")
    _verify_apparatus(plan)
    completed = _completed_results(plan)
    if len(completed) == len(plan["schedule"]):
        raise CriticClaimLinkReplicationError("series is already complete")
    cell = plan["schedule"][len(completed)]
    if run_id != cell["run_id"]:
        raise CriticClaimLinkReplicationError("run is not the next scheduled cell")
    probe = build_probe(run_id)
    if probe["plan_sha256"] != expected_plan_sha256:
        raise CriticClaimLinkReplicationError("plan hash does not match")
    if probe["prompt_sha256"] != expected_prompt_sha256:
        raise CriticClaimLinkReplicationError("prompt hash does not match")
    if cell.get("prompt_sha256") != probe["prompt_sha256"]:
        raise CriticClaimLinkReplicationError("frozen prompt hash drifted")
    resolved_run = run_dir.resolve()
    if resolved_run != _series_root(plan) / run_id or resolved_run.exists():
        raise CriticClaimLinkReplicationError("run directory is invalid or already exists")
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=plan["call_budget"]["stop_threshold_percent"]
    )
    if checkpoint["decision"] != "proceed":
        raise CriticClaimLinkReplicationError("current usage reached the stop threshold")

    resolved_run.mkdir(parents=True)
    _write_json(
        resolved_run / "probe-plan.json",
        {key: value for key, value in probe.items() if key != "prompt"},
    )
    _write_json(resolved_run / "usage-checkpoint.json", checkpoint)
    attempt_path = resolved_run / "attempt.json"
    _write_json(attempt_path, {"schema_version": 1, "status": "reserved"})
    candidates = _candidates(plan, cell)
    phase_dir = resolved_run / "phase"
    settings = workflow._provider_settings(workflow.load_manifest(), "codex")
    error: Exception | None = None
    record: dict[str, Any] | None = None
    try:
        workspace = EXPERIMENT_ROOT / "fixtures" / candidates[0]["fixture_id"] / "agent-visible"
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
        validated = controls._validate_output(output, plan=plan, candidates=candidates)
    except (
        CriticClaimLinkReplicationError,
        controls.CriticClaimLinkControlsError,
        fixture_control.FixtureControlError,
        source.CriticClaimLinkGeneralizationError,
        workflow.WorkflowRunnerError,
        worker_runner.WorkerRunnerError,
    ) as exc:
        error = exc
    if error is not None:
        _write_json(
            resolved_run / "disposition.json",
            {
                "schema_version": 1,
                "status": "excluded",
                "reason": str(error),
                "model_call_may_have_started": (phase_dir / "worker-run.json").exists(),
                "retry_allowed": False,
            },
        )
        raise CriticClaimLinkReplicationError(
            f"cell excluded; evidence preserved: {error}"
        ) from error
    assert record is not None
    quality_passed = all(
        item["claim_map_correct"]
        and item["verdict_correct"]
        and item["structured_finding_linkage_complete"]
        for item in validated
    )
    result = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "completed" if quality_passed else "quality_rejected",
        "run_id": run_id,
        "order": cell["order"],
        "candidate_order": cell["candidate_order"],
        "prompt_bytes": probe["prompt_bytes"],
        "prompt_sha256": probe["prompt_sha256"],
        "candidate_results": validated,
        "quality_passed": quality_passed,
        "usage": record["usage"],
        "timing": record["timing"],
    }
    _write_json(resolved_run / "output.json", output)
    _write_json(resolved_run / "result.json", result)
    _write_json(attempt_path, {"schema_version": 1, "status": "completed"})
    return result


def report() -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    fresh = _completed_results(plan)
    value: dict[str, Any] = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "incomplete",
        "completed_calls": len(fresh),
        "planned_calls": len(plan["schedule"]),
    }
    if len(fresh) != len(plan["schedule"]):
        return value
    all_batches = fresh + [
        {**_object(REPO_ROOT / item["result_path"]), "order": item["order"]}
        for item in plan["prior_batches"]
    ]
    baseline = plan["matched_direct_baseline"]
    by_order = {}
    for order in ("header_first", "cutover_first"):
        selected = [item for item in all_batches if item["order"] == order]
        by_order[order] = {
            "observations": len(selected),
            "median_input_tokens": statistics.median(
                item["usage"]["input_tokens"] for item in selected
            ),
            "median_completion_ms": round(
                statistics.median(item["timing"]["completion_ms"] for item in selected),
                3,
            ),
        }
    median_input = statistics.median(item["usage"]["input_tokens"] for item in all_batches)
    median_time = statistics.median(item["timing"]["completion_ms"] for item in all_batches)
    thresholds = plan["confirmation_thresholds"]
    passed = (
        all(item["quality_passed"] for item in all_batches)
        and all(item["observations"] == 2 for item in by_order.values())
        and median_input / baseline["summed_input_tokens"]
        <= thresholds["maximum_median_input_ratio_to_summed_direct"]
        and median_time / baseline["summed_completion_ms"]
        <= thresholds["maximum_median_completion_ratio_to_summed_direct"]
    )
    value.update(
        {
            "status": "replicated" if passed else "replication_rejected",
            "batch_observations": len(all_batches),
            "by_order": by_order,
            "median_batch_input_tokens": median_input,
            "median_input_reduction_percent": round(
                (1 - median_input / baseline["summed_input_tokens"]) * 100,
                3,
            ),
            "median_batch_completion_ms": round(median_time, 3),
            "median_completion_reduction_percent": round(
                (1 - median_time / baseline["summed_completion_ms"]) * 100,
                3,
            ),
            "confirmation_thresholds_passed": passed,
        }
    )
    return value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--expected-prompt-sha256")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.report:
            print(canonical_json(report()))
            return 0
        if not args.execute:
            print(canonical_json(next_cell()))
            return 0
        required = {
            "--run-id": args.run_id,
            "--run-dir": args.run_dir,
            "--expected-plan-sha256": args.expected_plan_sha256,
            "--expected-prompt-sha256": args.expected_prompt_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise CriticClaimLinkReplicationError("live cell requires " + ", ".join(missing))
        print(
            canonical_json(
                execute_cell(
                    run_id=args.run_id,
                    run_dir=args.run_dir,
                    expected_plan_sha256=args.expected_plan_sha256,
                    expected_prompt_sha256=args.expected_prompt_sha256,
                )
            )
        )
        return 0
    except (
        CriticClaimLinkReplicationError,
        codex_usage_snapshot.CodexUsageSnapshotError,
        controls.CriticClaimLinkControlsError,
        fixture_control.FixtureControlError,
        source.CriticClaimLinkGeneralizationError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

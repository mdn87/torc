"""Build a deterministic report for the frozen critic transport confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import critic_probe_score as probe_score  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
DEFAULT_PLAN = EXPERIMENT_ROOT / "critic-transport-series-002-plan.json"
DEFAULT_RUNS_DIR = EXPERIMENT_ROOT / "runs" / "critic-transport-002"


class CriticTransportReportError(RuntimeError):
    """Raised when confirmation evidence violates its frozen plan."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticTransportReportError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticTransportReportError(f"expected a JSON object: {path}")
    return value


def _ratio(numerator: float | int, denominator: float | int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _median(values: list[float | int]) -> float | None:
    return round(float(statistics.median(values)), 6) if values else None


def _validate_order(plan: dict[str, Any], scores: list[dict[str, Any]]) -> None:
    planned = plan["counterbalanced_order_per_candidate"]
    for candidate in plan["candidates"]:
        observed = [
            score["critic_context"]
            for score in scores
            if score["candidate_id"] == candidate["candidate_id"]
        ]
        if len(observed) > len(planned) or observed != planned[: len(observed)]:
            raise CriticTransportReportError(
                f"run order drift for {candidate['candidate_id']}: {observed}"
            )


def _validate_apparatus_inputs(plan: dict[str, Any]) -> None:
    for apparatus_input in plan["apparatus_inputs"]:
        path = REPO_ROOT / apparatus_input["path"]
        try:
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise CriticTransportReportError(
                f"cannot read frozen apparatus input: {path}"
            ) from exc
        if observed != apparatus_input["sha256"]:
            raise CriticTransportReportError(
                f"frozen apparatus input drift: {apparatus_input['path']}"
            )


def _validate_transport_evidence(
    *,
    plan: dict[str, Any],
    plan_path: Path,
    run_dir: Path,
    result: dict[str, Any],
) -> None:
    fixture_id = result["fixture_id"]
    run_id = result.get("run_id", run_dir.name)
    candidate_hash = _object(run_dir / "score-candidate.json")[
        "workspace_tree_sha256"
    ]
    settings = workflow._provider_settings(
        workflow.load_manifest(), plan["provider_controls"]["provider"]
    )
    expected_capsule, expected_control = workflow._compile_handoff(
        fixture_id,
        run_id,
        f"candidate-{candidate_hash[:16]}",
        f"{plan['provider_controls']['provider']}/{settings['model']}",
    )
    if _object(run_dir / "execution-capsule.json") != expected_capsule:
        raise CriticTransportReportError(f"execution capsule drift: {run_dir.name}")
    if _object(run_dir / "claim-control-envelope.json") != expected_control:
        raise CriticTransportReportError(f"claim control drift: {run_dir.name}")
    candidate_diff = (run_dir / "candidate.diff").read_text(encoding="utf-8")
    if candidate_diff:
        raise CriticTransportReportError(
            f"fixture baseline replay has a non-empty candidate diff: {run_dir.name}"
        )

    fixture_root = plan_path.parent / "fixtures" / fixture_id / "agent-visible"
    with tempfile.TemporaryDirectory(prefix="torc-critic-report-") as temp_dir:
        workspace = Path(temp_dir) / "candidate"
        shutil.copytree(fixture_root, workspace)
        (workspace / "CANDIDATE.diff").write_text(candidate_diff, encoding="utf-8")
        prompt = workflow._critic_prompt(
            expected_capsule,
            workspace,
            workflow._editable_paths(workflow.load_manifest(), fixture_id),
            result["critic_context"],
        )
    phase = result["phases"][0]
    worker = _object(run_dir / phase["record"])
    expected_prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if worker.get("prompt_sha256") != expected_prompt_hash or worker.get(
        "prompt_bytes"
    ) != len(prompt.encode("utf-8")):
        raise CriticTransportReportError(f"critic prompt drift: {run_dir.name}")


def _group_scores(
    plan: dict[str, Any], scores: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for candidate in plan["candidates"]:
        candidate_id = candidate["candidate_id"]
        for transport in plan["transports"]:
            selected = [
                score
                for score in scores
                if score["candidate_id"] == candidate_id
                and score["critic_context"] == transport
            ]
            if not selected:
                continue
            calls = len(selected)
            changes_requested = sum(
                score["critic_verdict"] == "changes_requested" for score in selected
            )
            input_tokens = [
                score["usage"]["input_tokens"]
                for score in selected
                if score.get("usage", {}).get("input_tokens") is not None
            ]
            output_tokens = [
                score["usage"]["output_tokens"]
                for score in selected
                if score.get("usage", {}).get("output_tokens") is not None
            ]
            completion_ms = [
                score["timing"]["completion_ms"]
                for score in selected
                if score.get("timing", {}).get("completion_ms") is not None
            ]
            groups.append(
                {
                    "candidate_id": candidate_id,
                    "critic_context": transport,
                    "call_count": calls,
                    "changes_requested_count": changes_requested,
                    "changes_requested_rate": _ratio(changes_requested, calls),
                    "median_defect_area_recall": _median(
                        [score["defect_area_recall"] for score in selected]
                    ),
                    "unsupported_finding_count": sum(
                        score["unsupported_finding_count"] for score in selected
                    ),
                    "valid_claim_citation_count": sum(
                        score["valid_claim_citation_count"] for score in selected
                    ),
                    "median_prompt_bytes": _median(
                        [score["prompt_bytes"] for score in selected]
                    ),
                    "median_input_tokens": _median(input_tokens),
                    "median_output_tokens": _median(output_tokens),
                    "median_completion_ms": _median(completion_ms),
                }
            )
    return groups


def _comparisons(
    plan: dict[str, Any], groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    compact_id, full_id = plan["transports"]
    comparisons: list[dict[str, Any]] = []
    for candidate in plan["candidates"]:
        candidate_id = candidate["candidate_id"]
        by_transport = {
            group["critic_context"]: group
            for group in groups
            if group["candidate_id"] == candidate_id
        }
        if compact_id not in by_transport or full_id not in by_transport:
            continue
        compact = by_transport[compact_id]
        full = by_transport[full_id]
        comparisons.append(
            {
                "candidate_id": candidate_id,
                "compact_call_count": compact["call_count"],
                "full_call_count": full["call_count"],
                "compact_to_full_prompt_byte_ratio": _ratio(
                    compact["median_prompt_bytes"], full["median_prompt_bytes"]
                ),
                "compact_to_full_input_token_ratio": _ratio(
                    compact["median_input_tokens"], full["median_input_tokens"]
                ),
                "compact_to_full_completion_ratio": _ratio(
                    compact["median_completion_ms"], full["median_completion_ms"]
                ),
                "compact_minus_full_recall": round(
                    compact["median_defect_area_recall"]
                    - full["median_defect_area_recall"],
                    6,
                ),
            }
        )
    return comparisons


def build_report(
    *, runs_dir: Path = DEFAULT_RUNS_DIR, plan_path: Path = DEFAULT_PLAN
) -> dict[str, Any]:
    plan = _object(plan_path)
    if plan.get("status") != "frozen_before_live_runs":
        raise CriticTransportReportError("confirmation plan is not frozen")
    _validate_apparatus_inputs(plan)
    resolved_runs = runs_dir.resolve()
    state = _object(resolved_runs / "block-state.json")
    plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if state.get("plan_sha256") != plan_hash:
        raise CriticTransportReportError("block state does not reference the frozen plan")

    candidates_by_fixture = {
        candidate["fixture_id"]: candidate["candidate_id"]
        for candidate in plan["candidates"]
    }
    scores: list[dict[str, Any]] = []
    run_dirs = sorted(
        path
        for path in resolved_runs.iterdir()
        if path.is_dir() and (path / "workflow-result.json").is_file()
    )
    for run_dir in run_dirs:
        result = _object(run_dir / "workflow-result.json")
        try:
            candidate_id = candidates_by_fixture[result["fixture_id"]]
        except (KeyError, TypeError) as exc:
            raise CriticTransportReportError(
                f"run has no planned candidate: {run_dir.name}"
            ) from exc
        try:
            score = probe_score.score_run(
                run_dir=run_dir,
                candidate_id=candidate_id,
                plan_path=plan_path,
            )
        except probe_score.CriticProbeScoreError as exc:
            raise CriticTransportReportError(
                f"invalid probe run {run_dir.name}: {exc}"
            ) from exc
        stored_score = _object(run_dir / "probe-score.json")
        if stored_score != score:
            raise CriticTransportReportError(
                f"stored score does not match deterministic rescore: {run_dir.name}"
            )
        _validate_transport_evidence(
            plan=plan,
            plan_path=plan_path,
            run_dir=run_dir,
            result=result,
        )
        scores.append(score)

    _validate_order(plan, scores)
    groups = _group_scores(plan, scores)
    expected_calls = (
        len(plan["candidates"])
        * len(plan["transports"])
        * plan["repeats_per_transport_per_candidate"]
    )
    checkpoints = [
        _object(path)
        for path in sorted(resolved_runs.glob("usage-checkpoint-*.json"))
    ]
    checkpoints.sort(key=lambda checkpoint: checkpoint.get("observed_at", ""))
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_sha256": plan_hash,
        "status": state["status"],
        "completed_call_count": len(scores),
        "expected_call_count": expected_calls,
        "remaining_call_count": expected_calls - len(scores),
        "groups": groups,
        "comparisons": _comparisons(plan, groups),
        "scores": scores,
        "usage_checkpoints": checkpoints,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args(argv)
    try:
        print(canonical_json(build_report(runs_dir=args.runs_dir, plan_path=args.plan)))
        return 0
    except CriticTransportReportError as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

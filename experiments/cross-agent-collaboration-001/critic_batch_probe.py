"""Build, execute, and score one guarded two-candidate critic batch."""

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
import native_context_request as request_builder  # noqa: E402
import native_context_response as response_scoring  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-batch-capability-001-plan.json"


class CriticBatchProbeError(RuntimeError):
    """Raised when the batch probe cannot preserve its frozen controls."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticBatchProbeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticBatchProbeError(f"expected a JSON object: {path}")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payloads(plan: dict[str, Any]) -> list[dict[str, Any]]:
    model = plan["provider_controls"]["model"]
    payloads = []
    for candidate_id in plan["candidates"]:
        candidate = request_builder._candidate(candidate_id)
        payload = request_builder._critic_payload(
            candidate,
            "portable_direct",
            model,
        )
        payloads.append(
            {
                "candidate_id": candidate_id,
                "fixture_id": candidate["fixture_id"],
                "candidate_workspace_tree_sha256": candidate[
                    "candidate_workspace_tree_sha256"
                ],
                "payload": payload,
                "payload_bytes": len(payload.encode("utf-8")),
                "payload_sha256": _sha256_text(payload),
            }
        )
    return payloads


def _prompt(payloads: list[dict[str, Any]]) -> str:
    contract = {
        "schema_version": 1,
        "critiques": [
            {
                "candidate_id": payload["candidate_id"],
                "result": {
                    "schema_version": 1,
                    "verdict": "approve|changes_requested",
                    "findings": [
                        {
                            "finding_id": "f1",
                            "severity": "blocking|non_blocking",
                            "summary": "...",
                            "evidence": "path:line or testable observation",
                            "claim_ids": ["x1"],
                        }
                    ],
                },
            }
            for payload in payloads
        ],
    }
    sections = "\n\n".join(
        f"BEGIN CANDIDATE {index}: {payload['candidate_id']}\n"
        f"{payload['payload']}\n"
        f"END CANDIDATE {index}: {payload['candidate_id']}"
        for index, payload in enumerate(payloads, start=1)
    )
    return (
        "This is a controlled batching trial in tool-free mode. Review both independent "
        "candidate payloads below. Do not use tools or mix claims, evidence, or findings "
        "between candidates. Each enclosed payload's critic rules apply to its own nested "
        "result, while this outer instruction controls the combined response. Return exactly "
        "one JSON object with no Markdown and this shape: "
        + canonical_json(contract)
        + ". Include each candidate exactly once in the given order.\n\n"
        + sections
    )


def build_probe() -> dict[str, Any]:
    """Return the exact model-free prompt plan without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"ready", "complete", "rejected"}:
        raise CriticBatchProbeError("batch probe is not in a plannable state")
    payloads = _payloads(plan)
    prompt = _prompt(payloads)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "candidate_count": len(payloads),
        "candidates": [
            {key: value for key, value in payload.items() if key != "payload"}
            for payload in payloads
        ],
        "prompt_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": _sha256_text(prompt),
        "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
        "prompt": prompt,
    }


def _candidate_control(candidate_id: str, model: str) -> dict[str, Any]:
    candidate = request_builder._candidate(candidate_id)
    _, control = workflow._compile_handoff(
        candidate["fixture_id"],
        f"critic-transport-003-{candidate_id}",
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"openai-responses/{model}",
    )
    return control


def validate_batch(
    value: dict[str, Any], *, candidate_ids: list[str], model: str
) -> list[dict[str, Any]]:
    if set(value) != {"schema_version", "critiques"} or value.get(
        "schema_version"
    ) != 1:
        raise CriticBatchProbeError("batch output header is invalid")
    critiques = value.get("critiques")
    if not isinstance(critiques, list) or len(critiques) != len(candidate_ids):
        raise CriticBatchProbeError("batch output has the wrong critique count")
    observed_ids = [item.get("candidate_id") for item in critiques if isinstance(item, dict)]
    if observed_ids != candidate_ids:
        raise CriticBatchProbeError("batch candidate identity or order drifted")
    scored = []
    for item, candidate_id in zip(critiques, candidate_ids, strict=True):
        if set(item) != {"candidate_id", "result"} or not isinstance(
            item.get("result"), dict
        ):
            raise CriticBatchProbeError("batch critique envelope is invalid")
        critique = item["result"]
        try:
            workflow._validate_critique(
                critique,
                _candidate_control(candidate_id, model),
            )
            score = response_scoring._score(
                critique,
                candidate_id=candidate_id,
                arm="batched_portable_direct",
            )
        except (
            workflow.WorkflowRunnerError,
            response_scoring.NativeContextResponseError,
        ) as exc:
            raise CriticBatchProbeError(
                f"batch critique is invalid for {candidate_id}: {exc}"
            ) from exc
        scored.append(
            {
                "candidate_id": candidate_id,
                "critique": critique,
                "score": score,
            }
        )
    return scored


def _baseline(plan: dict[str, Any]) -> dict[str, Any]:
    baseline = plan["matched_direct_baseline"]
    run_ids = baseline["refactor_run_ids"] + baseline["release_run_ids"]
    root = EXPERIMENT_ROOT / "runs" / "critic-transport-002"
    scores = [_object(root / run_id / "probe-score.json") for run_id in run_ids]
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for score in scores:
        by_candidate.setdefault(score["candidate_id"], []).append(score)
    medians = {
        candidate_id: {
            "input_tokens": statistics.median(
                score["usage"]["input_tokens"] for score in candidate_scores
            ),
            "completion_ms": statistics.median(
                score["timing"]["completion_ms"] for score in candidate_scores
            ),
            "defect_area_recall": statistics.median(
                score["defect_area_recall"] for score in candidate_scores
            ),
        }
        for candidate_id, candidate_scores in by_candidate.items()
    }
    summed_input = sum(item["input_tokens"] for item in medians.values())
    summed_time = sum(item["completion_ms"] for item in medians.values())
    if summed_input != baseline["summed_median_input_tokens"] or round(
        summed_time, 3
    ) != baseline["summed_median_completion_ms"]:
        raise CriticBatchProbeError("matched direct baseline drifted")
    return {
        "run_ids": run_ids,
        "candidate_medians": medians,
        "summed_median_input_tokens": summed_input,
        "summed_median_completion_ms": round(summed_time, 3),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def execute_probe(
    *,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "ready":
        raise CriticBatchProbeError("batch probe is not ready")
    probe = build_probe()
    if expected_plan_sha256 != probe["plan_sha256"]:
        raise CriticBatchProbeError("batch plan hash does not match")
    if expected_prompt_sha256 != probe["prompt_sha256"]:
        raise CriticBatchProbeError("batch prompt hash does not match")
    configured = Path(plan["call_budget"]["run_directory"])
    expected_run = (EXPERIMENT_ROOT / configured).resolve()
    resolved_run = run_dir.resolve()
    if configured.is_absolute() or ".." in configured.parts or resolved_run != expected_run:
        raise CriticBatchProbeError("run directory does not match the frozen plan")
    if resolved_run.exists():
        raise CriticBatchProbeError(f"run directory already exists: {resolved_run}")
    apparatus_revision = workflow._apparatus_revision()
    threshold = plan["call_budget"]["stop_threshold_percent"]
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=threshold
    )
    if checkpoint["decision"] != "proceed":
        raise CriticBatchProbeError("current usage reached the batch stop threshold")

    resolved_run.mkdir(parents=True)
    public_probe = {key: value for key, value in probe.items() if key != "prompt"}
    _write_json(resolved_run / "probe-plan.json", public_probe)
    _write_json(resolved_run / "usage-checkpoint.json", checkpoint)
    _write_json(
        resolved_run / "attempt.json",
        {
            "schema_version": 1,
            "status": "reserved",
            "apparatus_revision": apparatus_revision,
            "retry_requires_plan_change": True,
        },
    )
    phase_dir = resolved_run / "phase"
    settings = workflow._provider_settings(workflow.load_manifest(), "codex")
    error: Exception | None = None
    record: dict[str, Any] | None = None
    try:
        record = workflow._run_worker(
            settings=settings,
            workspace=(
                EXPERIMENT_ROOT
                / "fixtures"
                / "refactor-superseded-path"
                / "agent-visible"
            ),
            prompt=probe["prompt"],
            effort=plan["provider_controls"]["effort"],
            role="critic",
            tool_mode="none",
            session_mode="fresh-ephemeral",
            session_id=None,
            timeout_seconds=workflow.load_manifest()["timeout_seconds"],
            output_dir=phase_dir,
        )
        batch = workflow._phase_output_object("codex", phase_dir)
        scored = validate_batch(
            batch,
            candidate_ids=plan["candidates"],
            model=plan["provider_controls"]["model"],
        )
    except (
        CriticBatchProbeError,
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
        raise CriticBatchProbeError(
            f"batch probe excluded; evidence preserved: {error}"
        ) from error
    assert record is not None
    baseline = _baseline(plan)
    input_tokens = record["usage"]["input_tokens"]
    completion_ms = record["timing"]["completion_ms"]
    input_ratio = input_tokens / baseline["summed_median_input_tokens"]
    time_ratio = completion_ms / baseline["summed_median_completion_ms"]
    quality_passed = all(
        item["score"]["changes_requested_correct"]
        and item["score"]["defect_area_recall"] == 1.0
        for item in scored
    )
    capability_confirmed = quality_passed and input_ratio <= 0.8 and time_ratio <= 1
    result = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed" if capability_confirmed else "capability_rejected",
        "apparatus_revision": apparatus_revision,
        "prompt_bytes": probe["prompt_bytes"],
        "prompt_sha256": probe["prompt_sha256"],
        "candidate_results": scored,
        "usage": record["usage"],
        "timing": record["timing"],
        "matched_direct_baseline": baseline,
        "quality_passed": quality_passed,
        "input_ratio_to_summed_direct": round(input_ratio, 6),
        "input_reduction_percent": round((1 - input_ratio) * 100, 3),
        "completion_ratio_to_summed_direct": round(time_ratio, 6),
        "capability_thresholds_passed": capability_confirmed,
    }
    _write_json(resolved_run / "batch-output.json", batch)
    _write_json(resolved_run / "result.json", result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--expected-prompt-sha256")
    parser.add_argument("--include-prompt", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if not args.execute:
            probe = build_probe()
            if not args.include_prompt:
                probe = {key: value for key, value in probe.items() if key != "prompt"}
            print(canonical_json(probe))
            return 0
        required = {
            "--run-dir": args.run_dir,
            "--expected-plan-sha256": args.expected_plan_sha256,
            "--expected-prompt-sha256": args.expected_prompt_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise CriticBatchProbeError(
                "live batch probe requires " + ", ".join(missing)
            )
        result = execute_probe(
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(result))
        return 0
    except (
        CriticBatchProbeError,
        codex_usage_snapshot.CodexUsageSnapshotError,
        request_builder.NativeContextRequestError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

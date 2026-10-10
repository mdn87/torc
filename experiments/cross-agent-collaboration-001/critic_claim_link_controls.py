"""Run matched direct controls and a reversed batch for new claim-link fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import codex_usage_snapshot  # noqa: E402
import critic_claim_link_generalization as source  # noqa: E402
import critic_claim_link_probe as link  # noqa: E402
import fixture_control  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-claim-link-controls-007-plan.json"


class CriticClaimLinkControlsError(RuntimeError):
    """Raised when the matched-control series violates a frozen control."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkControlsError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkControlsError(f"expected a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _source_candidates(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_path = REPO_ROOT / plan["source_capability"]["plan_path"]
    source_plan = _object(source_path)
    candidates = source._candidates(source_plan)
    if source_plan["provider_controls"] != plan["provider_controls"]:
        raise CriticClaimLinkControlsError("source provider controls drifted")
    if source_plan["reviewable_claim_categories"] != plan["reviewable_claim_categories"]:
        raise CriticClaimLinkControlsError("source claim categories drifted")
    return {candidate["candidate_id"]: candidate for candidate in candidates}


def _cell(plan: dict[str, Any], run_id: str) -> dict[str, Any]:
    matches = [item for item in plan["schedule"] if item.get("run_id") == run_id]
    if len(matches) != 1:
        raise CriticClaimLinkControlsError(f"unknown or repeated run ID: {run_id}")
    return matches[0]


def _selected_candidates(plan: dict[str, Any], cell: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = _source_candidates(plan)
    try:
        candidates = [by_id[candidate_id] for candidate_id in cell["candidate_order"]]
    except KeyError as exc:
        raise CriticClaimLinkControlsError(f"unknown candidate: {exc.args[0]}") from exc
    expected_count = 1 if cell["mode"] == "direct" else 2
    if len(candidates) != expected_count or len(candidates) != len(set(cell["candidate_order"])):
        raise CriticClaimLinkControlsError("cell candidate membership is invalid")
    return candidates


def _prompt(*, payloads: list[dict[str, Any]], claim_ids: dict[str, list[str]]) -> str:
    contract = {
        "schema_version": 1,
        "critiques": [
            {
                "candidate_id": payload["candidate_id"],
                "claim_links": {
                    claim_id: ["f1"] for claim_id in claim_ids[payload["candidate_id"]]
                },
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
    target = (
        "both independent candidate payloads" if len(payloads) == 2 else "the candidate payload"
    )
    return (
        "This is a controlled compact claim-link trial in tool-free mode. Review "
        + target
        + ". Do not use tools or mix claims, evidence, findings, or links between "
        "candidates. The outer contract lists every reviewable claim exactly once. "
        "For each claim, return an empty finding-ID list when no violation is observed; "
        "return one or more finding IDs when the claim is violated. Every referenced "
        "finding must exist and cite that same claim ID. Every finding must be referenced "
        "by at least one claim. Put evidence only in findings; do not add assessment prose. "
        "Each enclosed payload's critic rules apply to its nested result. Return exactly "
        "one JSON object with no Markdown and this shape: "
        + canonical_json(contract)
        + ". Include each candidate exactly once in the given order.\n\n"
        + sections
    )


def build_probe(run_id: str) -> dict[str, Any]:
    """Return one scheduled model-free request without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "ready", "complete", "rejected"}:
        raise CriticClaimLinkControlsError("series is not plannable")
    cell = _cell(plan, run_id)
    candidates = _selected_candidates(plan, cell)
    claim_ids = source._claim_ids(plan, candidates)
    payloads = source._payloads(plan, candidates)
    prompt = _prompt(payloads=payloads, claim_ids=claim_ids)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "run_id": run_id,
        "mode": cell["mode"],
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


def _validate_output(
    value: dict[str, Any],
    *,
    plan: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_ids = [candidate["candidate_id"] for candidate in candidates]
    if set(value) != {"schema_version", "critiques"} or value.get("schema_version") != 1:
        raise CriticClaimLinkControlsError("output header is invalid")
    critiques = value.get("critiques")
    if not isinstance(critiques, list) or len(critiques) != len(candidates):
        raise CriticClaimLinkControlsError("critique count is invalid")
    if [item.get("candidate_id") for item in critiques if isinstance(item, dict)] != candidate_ids:
        raise CriticClaimLinkControlsError("candidate identity or order drifted")
    claim_ids = source._claim_ids(plan, candidates)
    model = plan["provider_controls"]["model"]
    validated = []
    for item, candidate in zip(critiques, candidates, strict=True):
        if not isinstance(item, dict) or set(item) != {
            "candidate_id",
            "claim_links",
            "result",
        }:
            raise CriticClaimLinkControlsError("candidate envelope is invalid")
        critique = item.get("result")
        if not isinstance(critique, dict):
            raise CriticClaimLinkControlsError("nested critique is invalid")
        try:
            workflow._validate_critique(
                critique,
                source._candidate_control(candidate, model),
            )
            links = link._validate_claim_links(
                item=item,
                expected_claim_ids=claim_ids[candidate["candidate_id"]],
            )
        except (workflow.WorkflowRunnerError, link.CriticClaimLinkProbeError) as exc:
            raise CriticClaimLinkControlsError(
                f"invalid critique for {candidate['candidate_id']}: {exc}"
            ) from exc
        expected = candidate["expected_claim_statuses"]
        validated.append(
            {
                "candidate_id": candidate["candidate_id"],
                "critique": critique,
                **links,
                "expected_claim_statuses": expected,
                "claim_map_correct": links["observed_claim_statuses"] == expected,
                "verdict_correct": critique["verdict"] == candidate["expected_verdict"],
            }
        )
    return validated


def _verify_apparatus(plan: dict[str, Any]) -> None:
    inputs = plan.get("apparatus_inputs", [])
    if not inputs:
        raise CriticClaimLinkControlsError("frozen apparatus inputs are missing")
    for item in inputs:
        observed = _sha256_file(REPO_ROOT / item["path"])
        if observed != item["sha256"]:
            raise CriticClaimLinkControlsError(
                f"apparatus hash drifted for {item['path']}: {observed}"
            )


def _series_root(plan: dict[str, Any]) -> Path:
    configured = Path(plan["call_budget"]["series_directory"])
    if configured.is_absolute() or ".." in configured.parts:
        raise CriticClaimLinkControlsError("series directory is unsafe")
    return (EXPERIMENT_ROOT / configured).resolve()


def _completed_results(plan: dict[str, Any]) -> list[dict[str, Any]]:
    root = _series_root(plan)
    completed = []
    for cell in plan["schedule"]:
        result_path = root / cell["run_id"] / "result.json"
        disposition = root / cell["run_id"] / "disposition.json"
        if disposition.exists():
            raise CriticClaimLinkControlsError(f"excluded cell stops the series: {cell['run_id']}")
        if not result_path.exists():
            break
        result = _object(result_path)
        if not result.get("quality_passed"):
            raise CriticClaimLinkControlsError(
                f"quality failure stops the series: {cell['run_id']}"
            )
        completed.append(result)
    return completed


def next_cell() -> dict[str, Any]:
    """Return the next scheduled cell and its deterministic probe."""
    plan = _object(PLAN_PATH)
    completed = _completed_results(plan)
    if len(completed) >= len(plan["schedule"]):
        return {"status": "complete", "completed_calls": len(completed)}
    cell = plan["schedule"][len(completed)]
    probe = build_probe(cell["run_id"])
    return {
        "status": "ready" if plan["status"] == "ready" else plan["status"],
        "completed_calls": len(completed),
        "next": {key: value for key, value in probe.items() if key != "prompt"},
    }


def execute_cell(
    *,
    run_id: str,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "ready":
        raise CriticClaimLinkControlsError("series is not ready")
    _verify_apparatus(plan)
    completed = _completed_results(plan)
    if len(completed) >= len(plan["schedule"]):
        raise CriticClaimLinkControlsError("series is already complete")
    cell = plan["schedule"][len(completed)]
    if run_id != cell["run_id"]:
        raise CriticClaimLinkControlsError("run is not the next scheduled cell")
    probe = build_probe(run_id)
    if expected_plan_sha256 != probe["plan_sha256"]:
        raise CriticClaimLinkControlsError("plan hash does not match")
    if expected_prompt_sha256 != probe["prompt_sha256"]:
        raise CriticClaimLinkControlsError("prompt hash does not match")
    if cell.get("prompt_sha256") != probe["prompt_sha256"]:
        raise CriticClaimLinkControlsError("frozen cell prompt hash drifted")
    expected_run = _series_root(plan) / run_id
    resolved_run = run_dir.resolve()
    if resolved_run != expected_run or resolved_run.exists():
        raise CriticClaimLinkControlsError("run directory is invalid or already exists")
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=plan["call_budget"]["stop_threshold_percent"]
    )
    if checkpoint["decision"] != "proceed":
        raise CriticClaimLinkControlsError("current usage reached the stop threshold")

    resolved_run.mkdir(parents=True)
    _write_json(
        resolved_run / "probe-plan.json",
        {key: value for key, value in probe.items() if key != "prompt"},
    )
    _write_json(resolved_run / "usage-checkpoint.json", checkpoint)
    attempt_path = resolved_run / "attempt.json"
    _write_json(
        attempt_path,
        {"schema_version": 1, "status": "reserved", "retry_allowed": False},
    )
    candidates = _selected_candidates(plan, cell)
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
        validated = _validate_output(output, plan=plan, candidates=candidates)
    except (
        CriticClaimLinkControlsError,
        fixture_control.FixtureControlError,
        link.CriticClaimLinkProbeError,
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
        raise CriticClaimLinkControlsError(f"cell excluded; evidence preserved: {error}") from error
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
        "mode": cell["mode"],
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
    _write_json(
        attempt_path,
        {"schema_version": 1, "status": "completed", "retry_allowed": False},
    )
    return result


def report() -> dict[str, Any]:
    """Summarize completed cells and apply cost gates when all exist."""
    plan = _object(PLAN_PATH)
    results = _completed_results(plan)
    value: dict[str, Any] = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "incomplete",
        "completed_calls": len(results),
        "planned_calls": len(plan["schedule"]),
    }
    if len(results) != len(plan["schedule"]):
        return value
    direct = [item for item in results if item["mode"] == "direct"]
    batch = next(item for item in results if item["mode"] == "batch")
    summed_input = sum(item["usage"]["input_tokens"] for item in direct)
    summed_time = sum(item["timing"]["completion_ms"] for item in direct)
    input_ratio = batch["usage"]["input_tokens"] / summed_input
    completion_ratio = batch["timing"]["completion_ms"] / summed_time
    thresholds = plan["capability_thresholds"]
    passed = (
        all(item["quality_passed"] for item in results)
        and input_ratio <= thresholds["maximum_batch_input_ratio_to_summed_direct"]
        and completion_ratio <= thresholds["maximum_batch_completion_ratio_to_summed_direct"]
    )
    value.update(
        {
            "status": "capability_confirmed" if passed else "capability_rejected",
            "summed_direct_input_tokens": summed_input,
            "fresh_batch_input_tokens": batch["usage"]["input_tokens"],
            "fresh_batch_input_ratio": round(input_ratio, 6),
            "fresh_batch_input_reduction_percent": round((1 - input_ratio) * 100, 3),
            "summed_direct_completion_ms": round(summed_time, 3),
            "fresh_batch_completion_ms": batch["timing"]["completion_ms"],
            "fresh_batch_completion_ratio": round(completion_ratio, 6),
            "fresh_batch_completion_reduction_percent": round((1 - completion_ratio) * 100, 3),
            "capability_thresholds_passed": passed,
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
            raise CriticClaimLinkControlsError("live cell requires " + ", ".join(missing))
        value = execute_cell(
            run_id=args.run_id,
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(value))
        return 0
    except (
        CriticClaimLinkControlsError,
        codex_usage_snapshot.CodexUsageSnapshotError,
        fixture_control.FixtureControlError,
        link.CriticClaimLinkProbeError,
        source.CriticClaimLinkGeneralizationError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

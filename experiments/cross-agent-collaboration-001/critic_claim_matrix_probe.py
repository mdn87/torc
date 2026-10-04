"""Build, run, and score one structured-claim compact critic batch."""

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
import critic_batch_probe as batch  # noqa: E402
import native_context_request as request_builder  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-claim-matrix-capability-001-plan.json"


class CriticClaimMatrixProbeError(RuntimeError):
    """Raised when the structured-claim probe violates a frozen control."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimMatrixProbeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimMatrixProbeError(f"expected a JSON object: {path}")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
            raise CriticClaimMatrixProbeError(
                f"apparatus hash drifted for {item['path']}: {observed}"
            )
        verified.append({"path": item["path"], "sha256": observed})
    if not verified:
        raise CriticClaimMatrixProbeError("frozen apparatus inputs are missing")
    return verified


def _capsule(candidate_id: str, model: str) -> dict[str, Any]:
    candidate = request_builder._candidate(candidate_id)
    capsule, _ = workflow._compile_handoff(
        candidate["fixture_id"],
        f"critic-claim-matrix-001-{candidate_id}",
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"openai-responses/{model}",
    )
    return capsule


def _reviewable_claim_ids(*, candidate_id: str, model: str, categories: list[str]) -> list[str]:
    claims = _capsule(candidate_id, model)["claims"]
    identifiers = [
        claim_id for category in categories for claim_id in sorted(claims.get(category, {}))
    ]
    if len(identifiers) != len(set(identifiers)):
        raise CriticClaimMatrixProbeError(f"reviewable claim IDs are not unique for {candidate_id}")
    if not identifiers:
        raise CriticClaimMatrixProbeError(f"reviewable claim set is empty for {candidate_id}")
    return identifiers


def _prompt(
    *,
    payloads: list[dict[str, Any]],
    claim_ids: dict[str, list[str]],
) -> str:
    contract = {
        "schema_version": 1,
        "critiques": [
            {
                "candidate_id": payload["candidate_id"],
                "claim_assessments": [
                    {
                        "claim_id": claim_id,
                        "status": "met|unmet",
                        "evidence": "path:line or testable observation",
                        "finding_ids": ["f1"],
                    }
                    for claim_id in claim_ids[payload["candidate_id"]]
                ],
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
        "This is a controlled structured-coverage trial in tool-free mode. Review both "
        "independent candidate payloads. Do not use tools or mix claims, evidence, findings, "
        "or assessments between candidates. The outer contract lists every reviewable claim; "
        "return each exactly once in that order. Mark a claim met only when the candidate has "
        "no observed violation. Mark it unmet when the candidate contradicts it. Every "
        "assessment needs concrete evidence. An unmet assessment must name at least one "
        "finding_id whose finding cites that same claim_id; a met assessment must use an empty "
        "finding_ids list. Each enclosed payload's critic rules apply to its nested result. "
        "Return exactly one JSON object with no Markdown and this shape: "
        + canonical_json(contract)
        + ". Include each candidate exactly once in the given order.\n\n"
        + sections
    )


def build_probe() -> dict[str, Any]:
    """Return the exact model-free request plan without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "ready", "complete", "rejected"}:
        raise CriticClaimMatrixProbeError("claim-matrix probe is not plannable")
    payloads = batch._payloads(plan)
    categories = plan["reviewable_claim_categories"]
    claim_ids = {
        candidate_id: _reviewable_claim_ids(
            candidate_id=candidate_id,
            model=plan["provider_controls"]["model"],
            categories=categories,
        )
        for candidate_id in plan["candidates"]
    }
    prompt = _prompt(payloads=payloads, claim_ids=claim_ids)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "candidate_order": plan["candidates"],
        "reviewable_claim_ids": claim_ids,
        "candidates": [
            {key: value for key, value in payload.items() if key != "payload"}
            for payload in payloads
        ],
        "prompt_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": _sha256_text(prompt),
        "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
        "prompt": prompt,
    }


def _validate_assessments(
    *,
    item: dict[str, Any],
    expected_claim_ids: list[str],
) -> list[dict[str, Any]]:
    assessments = item.get("claim_assessments")
    if not isinstance(assessments, list):
        raise CriticClaimMatrixProbeError("claim assessments must be a list")
    observed_ids = [
        assessment.get("claim_id") for assessment in assessments if isinstance(assessment, dict)
    ]
    if observed_ids != expected_claim_ids:
        raise CriticClaimMatrixProbeError("claim assessment identity, order, or coverage drifted")
    findings = item["result"]["findings"]
    finding_by_id = {finding["finding_id"]: finding for finding in findings}
    for assessment in assessments:
        if set(assessment) != {"claim_id", "status", "evidence", "finding_ids"}:
            raise CriticClaimMatrixProbeError("claim assessment keys do not match the contract")
        status = assessment["status"]
        evidence = assessment["evidence"]
        finding_ids = assessment["finding_ids"]
        if status not in {"met", "unmet"}:
            raise CriticClaimMatrixProbeError("claim assessment status is invalid")
        if not isinstance(evidence, str) or not evidence.strip():
            raise CriticClaimMatrixProbeError("claim assessment evidence is empty")
        if (
            not isinstance(finding_ids, list)
            or any(not isinstance(value, str) or not value for value in finding_ids)
            or len(finding_ids) != len(set(finding_ids))
        ):
            raise CriticClaimMatrixProbeError("claim assessment finding IDs are invalid")
        if status == "met" and finding_ids:
            raise CriticClaimMatrixProbeError("met claim assessment must not reference a finding")
        if status == "unmet" and not finding_ids:
            raise CriticClaimMatrixProbeError("unmet claim assessment must reference a finding")
        for finding_id in finding_ids:
            finding = finding_by_id.get(finding_id)
            if finding is None:
                raise CriticClaimMatrixProbeError("claim assessment references a missing finding")
            if assessment["claim_id"] not in finding["claim_ids"]:
                raise CriticClaimMatrixProbeError(
                    "claim assessment references a finding without the same claim"
                )
    return assessments


def validate_output(value: dict[str, Any], *, plan: dict[str, Any]) -> list[dict[str, Any]]:
    if set(value) != {"schema_version", "critiques"} or value.get("schema_version") != 1:
        raise CriticClaimMatrixProbeError("claim-matrix output header is invalid")
    critiques = value.get("critiques")
    if not isinstance(critiques, list) or len(critiques) != len(plan["candidates"]):
        raise CriticClaimMatrixProbeError("claim-matrix critique count is invalid")
    observed_ids = [item.get("candidate_id") for item in critiques if isinstance(item, dict)]
    if observed_ids != plan["candidates"]:
        raise CriticClaimMatrixProbeError("claim-matrix candidate order drifted")
    nested = {
        "schema_version": 1,
        "critiques": [
            {"candidate_id": item["candidate_id"], "result": item["result"]} for item in critiques
        ],
    }
    base_results = batch.validate_batch(
        nested,
        candidate_ids=plan["candidates"],
        model=plan["provider_controls"]["model"],
    )
    by_candidate = {item["candidate_id"]: item for item in base_results}
    categories = plan["reviewable_claim_categories"]
    validated = []
    for item in critiques:
        if set(item) != {
            "candidate_id",
            "claim_assessments",
            "result",
        }:
            raise CriticClaimMatrixProbeError("claim-matrix candidate envelope is invalid")
        candidate_id = item["candidate_id"]
        claim_ids = _reviewable_claim_ids(
            candidate_id=candidate_id,
            model=plan["provider_controls"]["model"],
            categories=categories,
        )
        assessments = _validate_assessments(
            item=item,
            expected_claim_ids=claim_ids,
        )
        expected = plan["expected_claim_statuses"][candidate_id]
        observed = {assessment["claim_id"]: assessment["status"] for assessment in assessments}
        validated.append(
            {
                **by_candidate[candidate_id],
                "claim_assessments": assessments,
                "claim_matrix_correct": observed == expected,
                "expected_claim_statuses": expected,
                "observed_claim_statuses": observed,
            }
        )
    return validated


def execute_probe(
    *,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "ready":
        raise CriticClaimMatrixProbeError("claim-matrix probe is not ready")
    _verify_apparatus(plan)
    probe = build_probe()
    if expected_plan_sha256 != probe["plan_sha256"]:
        raise CriticClaimMatrixProbeError("claim-matrix plan hash does not match")
    if expected_prompt_sha256 != probe["prompt_sha256"]:
        raise CriticClaimMatrixProbeError("claim-matrix prompt hash does not match")
    configured = Path(plan["call_budget"]["run_directory"])
    expected_run = (EXPERIMENT_ROOT / configured).resolve()
    resolved_run = run_dir.resolve()
    if configured.is_absolute() or ".." in configured.parts or resolved_run != expected_run:
        raise CriticClaimMatrixProbeError("run directory does not match the frozen plan")
    if resolved_run.exists():
        raise CriticClaimMatrixProbeError(f"run directory already exists: {resolved_run}")
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=plan["call_budget"]["stop_threshold_percent"]
    )
    if checkpoint["decision"] != "proceed":
        raise CriticClaimMatrixProbeError("current usage reached the claim-matrix stop threshold")

    resolved_run.mkdir(parents=True)
    _write_json(
        resolved_run / "probe-plan.json",
        {key: value for key, value in probe.items() if key != "prompt"},
    )
    _write_json(resolved_run / "usage-checkpoint.json", checkpoint)
    _write_json(
        resolved_run / "attempt.json",
        {
            "schema_version": 1,
            "status": "reserved",
            "apparatus_revision": plan["apparatus_revision"],
            "retry_requires_plan_change": True,
        },
    )
    phase_dir = resolved_run / "phase"
    settings = workflow._provider_settings(workflow.load_manifest(), "codex")
    error: Exception | None = None
    record: dict[str, Any] | None = None
    try:
        candidate = request_builder._candidate(plan["candidates"][0])
        workspace = EXPERIMENT_ROOT / "fixtures" / candidate["fixture_id"] / "agent-visible"
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
        scored = validate_output(output, plan=plan)
    except (
        CriticClaimMatrixProbeError,
        batch.CriticBatchProbeError,
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
        raise CriticClaimMatrixProbeError(
            f"claim-matrix probe excluded; evidence preserved: {error}"
        ) from error
    assert record is not None
    baseline = batch._baseline(plan)
    input_ratio = record["usage"]["input_tokens"] / baseline["summed_median_input_tokens"]
    completion_ratio = record["timing"]["completion_ms"] / baseline["summed_median_completion_ms"]
    quality_passed = all(
        item["score"]["changes_requested_correct"]
        and item["claim_matrix_correct"]
        and item["score"]["unsupported_finding_count"] == 0
        for item in scored
    )
    capability_confirmed = (
        quality_passed
        and input_ratio <= plan["capability_thresholds"]["maximum_input_ratio_to_direct"]
        and completion_ratio <= plan["capability_thresholds"]["maximum_completion_ratio_to_direct"]
    )
    result = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed" if capability_confirmed else "capability_rejected",
        "prompt_bytes": probe["prompt_bytes"],
        "prompt_sha256": probe["prompt_sha256"],
        "candidate_results": scored,
        "quality_passed": quality_passed,
        "usage": record["usage"],
        "timing": record["timing"],
        "matched_direct_baseline": baseline,
        "input_ratio_to_summed_direct": round(input_ratio, 6),
        "input_reduction_percent": round((1 - input_ratio) * 100, 3),
        "completion_ratio_to_summed_direct": round(completion_ratio, 6),
        "capability_thresholds_passed": capability_confirmed,
    }
    _write_json(resolved_run / "batch-output.json", output)
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
            value = build_probe()
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
            raise CriticClaimMatrixProbeError(
                "live claim-matrix probe requires " + ", ".join(missing)
            )
        value = execute_probe(
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(value))
        return 0
    except (
        CriticClaimMatrixProbeError,
        batch.CriticBatchProbeError,
        codex_usage_snapshot.CodexUsageSnapshotError,
        request_builder.NativeContextRequestError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

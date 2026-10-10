"""Build, run, and score one compact claim-link critic batch."""

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
import critic_claim_matrix_probe as matrix  # noqa: E402
import native_context_request as request_builder  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-claim-link-capability-002-plan.json"


class CriticClaimLinkProbeError(RuntimeError):
    """Raised when the compact claim-link probe violates a frozen control."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkProbeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkProbeError(f"expected a JSON object: {path}")
    return value


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
            raise CriticClaimLinkProbeError(
                f"apparatus hash drifted for {item['path']}: {observed}"
            )
        verified.append({"path": item["path"], "sha256": observed})
    if not verified:
        raise CriticClaimLinkProbeError("frozen apparatus inputs are missing")
    return verified


def _claim_ids(plan: dict[str, Any]) -> dict[str, list[str]]:
    return {
        candidate_id: matrix._reviewable_claim_ids(
            candidate_id=candidate_id,
            model=plan["provider_controls"]["model"],
            categories=plan["reviewable_claim_categories"],
        )
        for candidate_id in plan["candidates"]
    }


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
    return (
        "This is a controlled compact claim-link trial in tool-free mode. Review both "
        "independent candidate payloads. Do not use tools or mix claims, evidence, findings, "
        "or links between candidates. The outer contract lists every reviewable claim exactly "
        "once. For each claim, return an empty finding-ID list when no violation is observed; "
        "return one or more finding IDs when the claim is violated. Every referenced finding "
        "must exist and cite that same claim ID. Every finding must be referenced by at least "
        "one claim. Put evidence only in findings; do not add assessment prose. Each enclosed "
        "payload's critic rules apply to its nested result. Return exactly one JSON object with "
        "no Markdown and this shape: "
        + canonical_json(contract)
        + ". Include each candidate exactly once in the given order.\n\n"
        + sections
    )


def build_probe() -> dict[str, Any]:
    """Return the exact model-free request plan without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "ready", "complete", "rejected"}:
        raise CriticClaimLinkProbeError("claim-link probe is not plannable")
    payloads = batch._payloads(plan)
    claim_ids = _claim_ids(plan)
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
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "plan_sha256": _sha256_file(PLAN_PATH),
        "prompt": prompt,
    }


def _validate_claim_links(*, item: dict[str, Any], expected_claim_ids: list[str]) -> dict[str, Any]:
    links = item.get("claim_links")
    if not isinstance(links, dict) or set(links) != set(expected_claim_ids):
        raise CriticClaimLinkProbeError(
            "claim-link identity or coverage does not match the contract"
        )
    findings = item["result"]["findings"]
    finding_by_id = {finding["finding_id"]: finding for finding in findings}
    linked_finding_ids: set[str] = set()
    for claim_id in expected_claim_ids:
        finding_ids = links[claim_id]
        if (
            not isinstance(finding_ids, list)
            or any(not isinstance(value, str) or not value for value in finding_ids)
            or len(finding_ids) != len(set(finding_ids))
        ):
            raise CriticClaimLinkProbeError("claim-link finding IDs are invalid")
        for finding_id in finding_ids:
            finding = finding_by_id.get(finding_id)
            if finding is None:
                raise CriticClaimLinkProbeError("claim link references a missing finding")
            if claim_id not in finding["claim_ids"]:
                raise CriticClaimLinkProbeError(
                    "claim link references a finding without the same claim"
                )
            linked_finding_ids.add(finding_id)
    finding_ids = set(finding_by_id)
    unlinked = sorted(finding_ids - linked_finding_ids)
    observed_statuses = {
        claim_id: "unmet" if links[claim_id] else "met" for claim_id in expected_claim_ids
    }
    return {
        "claim_links": links,
        "observed_claim_statuses": observed_statuses,
        "structured_finding_linkage_complete": not unlinked,
        "unlinked_finding_ids": unlinked,
    }


def validate_output(value: dict[str, Any], *, plan: dict[str, Any]) -> list[dict[str, Any]]:
    if set(value) != {"schema_version", "critiques"} or value.get("schema_version") != 1:
        raise CriticClaimLinkProbeError("claim-link output header is invalid")
    critiques = value.get("critiques")
    if not isinstance(critiques, list) or len(critiques) != len(plan["candidates"]):
        raise CriticClaimLinkProbeError("claim-link critique count is invalid")
    for item in critiques:
        if not isinstance(item, dict) or set(item) != {
            "candidate_id",
            "claim_links",
            "result",
        }:
            raise CriticClaimLinkProbeError("claim-link candidate envelope is invalid")
    if [item["candidate_id"] for item in critiques] != plan["candidates"]:
        raise CriticClaimLinkProbeError("claim-link candidate order drifted")
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
    claim_ids = _claim_ids(plan)
    validated = []
    for item in critiques:
        candidate_id = item["candidate_id"]
        links = _validate_claim_links(
            item=item,
            expected_claim_ids=claim_ids[candidate_id],
        )
        expected = plan["expected_claim_statuses"][candidate_id]
        validated.append(
            {
                **by_candidate[candidate_id],
                **links,
                "expected_claim_statuses": expected,
                "claim_map_correct": links["observed_claim_statuses"] == expected,
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
        raise CriticClaimLinkProbeError("claim-link probe is not ready")
    _verify_apparatus(plan)
    probe = build_probe()
    if expected_plan_sha256 != probe["plan_sha256"]:
        raise CriticClaimLinkProbeError("claim-link plan hash does not match")
    if expected_prompt_sha256 != probe["prompt_sha256"]:
        raise CriticClaimLinkProbeError("claim-link prompt hash does not match")
    configured = Path(plan["call_budget"]["run_directory"])
    expected_run = (EXPERIMENT_ROOT / configured).resolve()
    resolved_run = run_dir.resolve()
    if configured.is_absolute() or ".." in configured.parts or resolved_run != expected_run:
        raise CriticClaimLinkProbeError("run directory does not match the frozen plan")
    if resolved_run.exists():
        raise CriticClaimLinkProbeError(f"run directory already exists: {resolved_run}")
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=plan["call_budget"]["stop_threshold_percent"]
    )
    if checkpoint["decision"] != "proceed":
        raise CriticClaimLinkProbeError("current usage reached the claim-link stop threshold")

    resolved_run.mkdir(parents=True)
    _write_json(
        resolved_run / "probe-plan.json",
        {key: value for key, value in probe.items() if key != "prompt"},
    )
    _write_json(resolved_run / "usage-checkpoint.json", checkpoint)
    attempt_path = resolved_run / "attempt.json"
    _write_json(
        attempt_path,
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
        CriticClaimLinkProbeError,
        batch.CriticBatchProbeError,
        matrix.CriticClaimMatrixProbeError,
        request_builder.NativeContextRequestError,
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
        raise CriticClaimLinkProbeError(
            f"claim-link probe excluded; evidence preserved: {error}"
        ) from error
    assert record is not None
    baseline = batch._baseline(plan)
    input_ratio = record["usage"]["input_tokens"] / baseline["summed_median_input_tokens"]
    completion_ratio = record["timing"]["completion_ms"] / baseline["summed_median_completion_ms"]
    quality_passed = all(
        item["score"]["changes_requested_correct"]
        and item["claim_map_correct"]
        and item["structured_finding_linkage_complete"]
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
        "apparatus_revision": plan["apparatus_revision"],
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
            raise CriticClaimLinkProbeError("live claim-link probe requires " + ", ".join(missing))
        value = execute_probe(
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(value))
        return 0
    except (
        CriticClaimLinkProbeError,
        batch.CriticBatchProbeError,
        matrix.CriticClaimMatrixProbeError,
        codex_usage_snapshot.CodexUsageSnapshotError,
        request_builder.NativeContextRequestError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

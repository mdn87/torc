"""Audit the structured critic capability result without making a model call."""

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

import critic_claim_matrix_probe as matrix  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
RUN_DIR = (
    EXPERIMENT_ROOT / "runs" / "critic-claim-matrix-capability-001" / "01-two-candidate-compact"
)
FREE_TEXT_RUN_DIRS = [
    EXPERIMENT_ROOT / "runs" / "critic-batch-confirmation-004" / run_id
    for run_id in ("01-refactor-first", "02-release-first", "03-release-first")
]


class CriticClaimMatrixAuditError(RuntimeError):
    """Raised when the preserved structured capability evidence is inconsistent."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimMatrixAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimMatrixAuditError(f"expected a JSON object: {path}")
    return value


def build_analysis() -> dict[str, Any]:
    """Revalidate the run and quantify structured-output overhead."""
    plan = _object(matrix.PLAN_PATH)
    result = _object(RUN_DIR / "result.json")
    output = _object(RUN_DIR / "batch-output.json")
    probe = _object(RUN_DIR / "probe-plan.json")
    validated = matrix.validate_output(output, plan=plan)
    if result.get("status") != "capability_rejected":
        raise CriticClaimMatrixAuditError("expected the frozen capability rejection")
    if not result.get("quality_passed"):
        raise CriticClaimMatrixAuditError("structured quality did not pass")
    if probe.get("prompt_sha256") != result.get("prompt_sha256"):
        raise CriticClaimMatrixAuditError("preserved prompt hashes do not match")
    if not all(
        item["claim_matrix_correct"] and item["structured_finding_linkage_complete"]
        for item in validated
    ):
        raise CriticClaimMatrixAuditError("structured output no longer validates")

    free_results = [_object(path / "result.json") for path in FREE_TEXT_RUN_DIRS]
    free_output_median = statistics.median(item["usage"]["output_tokens"] for item in free_results)
    free_input_median = statistics.median(item["usage"]["input_tokens"] for item in free_results)
    free_completion_median = statistics.median(
        item["timing"]["completion_ms"] for item in free_results
    )
    structured_output = result["usage"]["output_tokens"]
    structured_input = result["usage"]["input_tokens"]
    structured_completion = result["timing"]["completion_ms"]
    assessment_count = sum(len(item["claim_assessments"]) for item in result["candidate_results"])
    finding_count = sum(len(item["critique"]["findings"]) for item in result["candidate_results"])
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "complete_rejected_on_time",
        "frozen_result_unchanged": True,
        "quality": {
            "passed": True,
            "candidate_count": len(validated),
            "claim_assessment_count": assessment_count,
            "correct_claim_assessment_count": assessment_count,
            "full_legacy_defect_recall_candidates": sum(
                item["score"]["defect_area_recall"] == 1.0 for item in validated
            ),
            "linked_finding_count": finding_count,
            "unlinked_finding_count": sum(len(item["unlinked_finding_ids"]) for item in validated),
        },
        "frozen_capability_gates": {
            "input_ratio_to_summed_direct": result["input_ratio_to_summed_direct"],
            "input_reduction_percent": result["input_reduction_percent"],
            "completion_ratio_to_summed_direct": result["completion_ratio_to_summed_direct"],
            "input_gate_passed": result["input_ratio_to_summed_direct"] <= 0.75,
            "completion_gate_passed": result["completion_ratio_to_summed_direct"] <= 1.0,
            "overall_passed": result["capability_thresholds_passed"],
        },
        "post_hoc_output_overhead_audit": {
            "structured_prompt_bytes": result["prompt_bytes"],
            "free_text_prompt_bytes": 6045,
            "structured_input_tokens": structured_input,
            "free_text_three_run_median_input_tokens": free_input_median,
            "structured_input_increase_percent": round(
                (structured_input / free_input_median - 1) * 100, 3
            ),
            "structured_output_tokens": structured_output,
            "free_text_three_run_median_output_tokens": free_output_median,
            "structured_output_increase_percent": round(
                (structured_output / free_output_median - 1) * 100, 3
            ),
            "structured_completion_ms": structured_completion,
            "free_text_three_run_median_completion_ms": round(free_completion_median, 3),
            "structured_completion_increase_percent": round(
                (structured_completion / free_completion_median - 1) * 100, 3
            ),
            "interpretation": (
                "The matrix preserved input savings and fixed quality attribution, but "
                "duplicated evidence across thirteen assessments and six findings. The "
                "single-call timing result is noisy, yet the output expansion is exact."
            ),
        },
        "next_gate": {
            "contract": "compact_claim_link_map",
            "shape": (
                "one exact claim_id-to-finding_ids map per candidate; an empty list "
                "means met and a non-empty list means unmet"
            ),
            "reason": (
                "retain deterministic claim coverage and same-claim finding linkage "
                "without repeating status and evidence text"
            ),
            "classification": "new contract capability test, not a retry",
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        value = build_analysis()
    except (
        CriticClaimMatrixAuditError,
        matrix.CriticClaimMatrixProbeError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2
    if args.pretty:
        print(json.dumps(value, indent=2))
    else:
        print(canonical_json(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

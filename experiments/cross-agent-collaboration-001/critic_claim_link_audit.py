"""Audit the compact claim-link capability result without a model call."""

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

import critic_claim_link_probe as link  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
RUN_DIR = EXPERIMENT_ROOT / "runs" / "critic-claim-link-capability-002" / "01-two-candidate-compact"
MATRIX_RUN_DIR = (
    EXPERIMENT_ROOT / "runs" / "critic-claim-matrix-capability-001" / "01-two-candidate-compact"
)
FREE_TEXT_RUN_DIRS = [
    EXPERIMENT_ROOT / "runs" / "critic-batch-confirmation-004" / run_id
    for run_id in ("01-refactor-first", "02-release-first", "03-release-first")
]


class CriticClaimLinkAuditError(RuntimeError):
    """Raised when preserved compact claim-link evidence is inconsistent."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkAuditError(f"expected a JSON object: {path}")
    return value


def _reduction(new: float, old: float) -> float:
    return round((1 - new / old) * 100, 3)


def build_analysis() -> dict[str, Any]:
    """Revalidate quality and compare compact versus verbose structure."""
    plan = _object(link.PLAN_PATH)
    result = _object(RUN_DIR / "result.json")
    output = _object(RUN_DIR / "batch-output.json")
    validated = link.validate_output(output, plan=plan)
    matrix_result = _object(MATRIX_RUN_DIR / "result.json")
    free_results = [_object(path / "result.json") for path in FREE_TEXT_RUN_DIRS]
    if result.get("status") != "capability_confirmed":
        raise CriticClaimLinkAuditError("expected the frozen capability confirmation")
    if not all(
        item["claim_map_correct"] and item["structured_finding_linkage_complete"]
        for item in validated
    ):
        raise CriticClaimLinkAuditError("compact claim-link output no longer validates")
    free_medians = {
        "input_tokens": statistics.median(item["usage"]["input_tokens"] for item in free_results),
        "output_tokens": statistics.median(item["usage"]["output_tokens"] for item in free_results),
        "completion_ms": statistics.median(
            item["timing"]["completion_ms"] for item in free_results
        ),
    }
    claim_count = sum(len(item["claim_links"]) for item in result["candidate_results"])
    finding_count = sum(len(item["critique"]["findings"]) for item in result["candidate_results"])
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed",
        "quality": {
            "candidate_count": len(validated),
            "correct_claim_status_count": claim_count,
            "reviewable_claim_count": claim_count,
            "full_legacy_defect_recall_candidates": sum(
                item["score"]["defect_area_recall"] == 1.0 for item in validated
            ),
            "linked_finding_count": finding_count,
            "unlinked_finding_count": sum(len(item["unlinked_finding_ids"]) for item in validated),
            "legacy_lexical_unsupported_finding_count_descriptive_only": sum(
                item["score"]["unsupported_finding_count"] for item in validated
            ),
        },
        "frozen_capability_gates": {
            "input_tokens": result["usage"]["input_tokens"],
            "input_reduction_percent_vs_summed_direct": result["input_reduction_percent"],
            "completion_ms": result["timing"]["completion_ms"],
            "completion_ratio_to_summed_direct": result["completion_ratio_to_summed_direct"],
            "all_passed": result["capability_thresholds_passed"],
        },
        "compact_vs_verbose_matrix": {
            "prompt_byte_reduction_percent": _reduction(
                result["prompt_bytes"], matrix_result["prompt_bytes"]
            ),
            "input_token_reduction_percent": _reduction(
                result["usage"]["input_tokens"],
                matrix_result["usage"]["input_tokens"],
            ),
            "output_token_reduction_percent": _reduction(
                result["usage"]["output_tokens"],
                matrix_result["usage"]["output_tokens"],
            ),
            "completion_reduction_percent": _reduction(
                result["timing"]["completion_ms"],
                matrix_result["timing"]["completion_ms"],
            ),
        },
        "compact_vs_free_text_three_run_medians": {
            "input_token_increase_percent": round(
                (result["usage"]["input_tokens"] / free_medians["input_tokens"] - 1) * 100,
                3,
            ),
            "output_token_increase_percent": round(
                (result["usage"]["output_tokens"] / free_medians["output_tokens"] - 1) * 100,
                3,
            ),
            "completion_increase_percent": round(
                (result["timing"]["completion_ms"] / free_medians["completion_ms"] - 1) * 100,
                3,
            ),
        },
        "next_gate": (
            "freeze four fresh compact claim-link batches in AB, BA, BA, AB order; "
            "exclude all capability calls from confirmation estimates"
        ),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        value = build_analysis()
    except (CriticClaimLinkAuditError, link.CriticClaimLinkProbeError) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2
    if args.pretty:
        print(json.dumps(value, indent=2))
    else:
        print(canonical_json(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

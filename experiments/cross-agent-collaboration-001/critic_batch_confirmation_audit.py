"""Audit the stopped critic-batch confirmation without making a model call."""

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

import critic_batch_series as series  # noqa: E402
import critic_probe_score as probe_score  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
TRANSPORT_PLAN_PATH = EXPERIMENT_ROOT / "critic-transport-series-002-plan.json"


class CriticBatchConfirmationAuditError(RuntimeError):
    """Raised when preserved confirmation evidence is incomplete or inconsistent."""


def _candidate(plan: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    matches = [item for item in plan["candidates"] if item["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise CriticBatchConfirmationAuditError(
            f"candidate is not uniquely planned: {candidate_id}"
        )
    return matches[0]


def _miss_audit(
    *,
    candidate_plan: dict[str, Any],
    candidate_result: dict[str, Any],
) -> list[dict[str, Any]]:
    areas = {item["area_id"]: item for item in candidate_plan["required_defect_areas"]}
    findings = candidate_result["critique"]["findings"]
    audited = []
    for area_id in candidate_result["score"]["missed_defect_area_ids"]:
        area = areas[area_id]
        acceptable = set(area["acceptable_claim_ids"])
        related = [finding for finding in findings if acceptable.intersection(finding["claim_ids"])]
        related_text = "\n".join(
            f"{finding['summary']}\n{finding['evidence']}" for finding in related
        ).lower()
        group_matches = [
            {
                "terms": group,
                "matched_terms": [term for term in group if term.lower() in related_text],
            }
            for group in area["evidence_term_groups"]
        ]
        audited.append(
            {
                "area_id": area_id,
                "acceptable_claim_ids": sorted(acceptable),
                "related_findings": related,
                "original_lexical_group_matches_across_related_findings": group_matches,
                "fail_closed_inflection_observed": any(
                    phrase in related_text
                    for phrase in ("failing closed", "fails closed", "failed closed")
                ),
                "any_single_finding_matches_frozen_area": any(
                    probe_score._finding_matches_area(finding, area) for finding in related
                ),
            }
        )
    return audited


def build_analysis() -> dict[str, Any]:
    """Recompute the strict outcome and descriptive stopped-series aggregates."""
    plan = series._object(series.PLAN_PATH)
    strict_report = series.report()
    results = series._existing_results(plan)
    completed = [item for item in results if item.get("status") == "completed"]
    if strict_report["status"] != "stopped_quality_failure" or len(completed) != 3:
        raise CriticBatchConfirmationAuditError("expected the preserved three-run quality stop")
    transport_plan = series._object(TRANSPORT_PLAN_PATH)
    candidate_results = [
        candidate for result in completed for candidate in result["candidate_results"]
    ]
    misses = []
    for result in candidate_results:
        if result["score"]["defect_area_recall"] == 1.0:
            continue
        misses.append(
            {
                "candidate_id": result["candidate_id"],
                "missed_areas": _miss_audit(
                    candidate_plan=_candidate(transport_plan, result["candidate_id"]),
                    candidate_result=result,
                ),
            }
        )
    baseline = strict_report["matched_direct_baseline"]
    median_input = statistics.median(item["usage"]["input_tokens"] for item in completed)
    median_completion = statistics.median(item["timing"]["completion_ms"] for item in completed)
    input_ratio = median_input / baseline["summed_median_input_tokens"]
    completion_ratio = median_completion / baseline["summed_median_completion_ms"]
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "stopped_quality_failure",
        "preregistered_result": {
            "completed_batch_calls": len(completed),
            "scheduled_batch_calls": len(plan["counterbalanced_schedule"]),
            "strict_confirmation_passed": False,
            "reason": "one release-policy critique scored 0.75 deterministic defect-area recall",
            "fourth_call_permitted": False,
        },
        "descriptive_quality": {
            "candidate_critiques": len(candidate_results),
            "correct_changes_requested_verdicts": sum(
                item["score"]["changes_requested_correct"] for item in candidate_results
            ),
            "full_deterministic_recall_critiques": sum(
                item["score"]["defect_area_recall"] == 1.0 for item in candidate_results
            ),
            "unsupported_finding_count": sum(
                item["score"]["unsupported_finding_count"] for item in candidate_results
            ),
        },
        "descriptive_cost_not_a_confirmation_claim": {
            "median_batch_input_tokens": median_input,
            "median_input_ratio_to_summed_direct": round(input_ratio, 6),
            "median_input_reduction_percent": round((1 - input_ratio) * 100, 3),
            "median_batch_completion_ms": round(median_completion, 3),
            "median_completion_ratio_to_summed_direct": round(completion_ratio, 6),
            "median_completion_reduction_percent": round((1 - completion_ratio) * 100, 3),
        },
        "post_hoc_scorer_audit": {
            "primary_scores_changed": False,
            "misses": misses,
            "interpretation": (
                "The missed area retained its x5 claim citation and described the "
                "malformed and unknown-action behaviors, but no single finding used "
                "one frozen second-group lexical term. This is evidence for a "
                "structured claim-coverage contract, not grounds to override the "
                "preregistered failure."
            ),
        },
        "next_gate": (
            "Test a result contract that requires one explicit assessment for every "
            "capsule claim before spending more calls on batch-size confirmation."
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
    except (
        CriticBatchConfirmationAuditError,
        series.CriticBatchSeriesError,
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

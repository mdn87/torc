"""Audit the compact claim-link confirmation without making a model call."""

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
import critic_claim_link_series as series  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent


class CriticClaimLinkConfirmationAuditError(RuntimeError):
    """Raised when confirmation evidence is incomplete or inconsistent."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkConfirmationAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkConfirmationAuditError(f"expected a JSON object: {path}")
    return value


def build_analysis() -> dict[str, Any]:
    """Revalidate all four cells and summarize the frozen confirmation."""
    plan = _object(series.PLAN_PATH)
    report = series.report()
    results = series._existing_results(plan)
    completed = [item for item in results if item.get("status") == "completed"]
    if report.get("status") != "confirmed" or len(completed) != 4:
        raise CriticClaimLinkConfirmationAuditError(
            "expected the completed confirmed four-run series"
        )
    validated_runs = []
    run_root = EXPERIMENT_ROOT / "runs" / "critic-claim-link-confirmation-005"
    for scheduled, result in zip(plan["counterbalanced_schedule"], completed, strict=True):
        output = _object(run_root / scheduled["run_id"] / "batch-output.json")
        validated = link.validate_output(
            output,
            plan=series._validation_plan(plan, scheduled["candidate_order"]),
        )
        if not result["quality_passed"] or not all(
            item["claim_map_correct"] and item["structured_finding_linkage_complete"]
            for item in validated
        ):
            raise CriticClaimLinkConfirmationAuditError(
                f"structured quality drifted for {scheduled['run_id']}"
            )
        validated_runs.append(validated)
    candidates = [candidate for run in validated_runs for candidate in run]
    claim_status_count = sum(len(item["claim_links"]) for item in candidates)
    finding_count = sum(len(item["critique"]["findings"]) for item in candidates)
    by_order: dict[str, dict[str, float]] = {}
    for order in ("refactor_first", "release_first"):
        selected = [
            result
            for result in completed
            if (result["candidate_order"][0] == "refactor-baseline-v1")
            == (order == "refactor_first")
        ]
        by_order[order] = {
            "run_count": len(selected),
            "median_input_tokens": statistics.median(
                item["usage"]["input_tokens"] for item in selected
            ),
            "median_completion_ms": round(
                statistics.median(item["timing"]["completion_ms"] for item in selected),
                3,
            ),
        }
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "confirmed",
        "design": {
            "fresh_batch_calls": 4,
            "candidate_critiques": 8,
            "order": ["AB", "BA", "BA", "AB"],
            "excluded_predecessors": plan["excluded_predecessors"],
        },
        "structured_quality": {
            "correct_claim_status_count": claim_status_count,
            "reviewable_claim_status_count": claim_status_count,
            "candidate_position_quality_passes": 8,
            "linked_finding_count": finding_count,
            "unlinked_finding_count": sum(len(item["unlinked_finding_ids"]) for item in candidates),
            "full_legacy_defect_recall_candidates_descriptive_only": sum(
                item["score"]["defect_area_recall"] == 1.0 for item in candidates
            ),
            "legacy_unsupported_finding_count_descriptive_only": sum(
                item["score"]["unsupported_finding_count"] for item in candidates
            ),
        },
        "primary_cost_result": {
            "median_batch_input_tokens": report["median_batch_input_tokens"],
            "median_input_reduction_percent_vs_summed_direct": report[
                "median_input_reduction_percent"
            ],
            "median_batch_output_tokens": report["median_batch_output_tokens"],
            "median_batch_completion_ms": report["median_batch_completion_ms"],
            "median_completion_reduction_percent_vs_summed_direct": report[
                "median_completion_reduction_percent"
            ],
            "all_frozen_thresholds_passed": report["confirmation_thresholds_passed"],
        },
        "order_check": {
            "quality_changed_by_position": False,
            "by_order": by_order,
        },
        "interpretation": (
            "For these two bounded tool-free reviews, a two-candidate compact "
            "claim-link batch preserved every structured claim decision and reduced "
            "both provider input and completion time relative to matched separate calls."
        ),
        "recommendation": (
            "Use batch size two for independent read-only critiques with the same model, "
            "effort, policy boundary, and compact claim-link contract. Broaden fixtures and "
            "providers before increasing batch size or generalizing the effect."
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
        CriticClaimLinkConfirmationAuditError,
        series.CriticClaimLinkSeriesError,
        link.CriticClaimLinkProbeError,
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

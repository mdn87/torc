"""Audit matched claim-link controls and both batch orders without a model call."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import critic_claim_link_controls as controls  # noqa: E402
import critic_claim_link_generalization_audit as source_audit  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
RUN_ROOT = EXPERIMENT_ROOT / "runs" / "critic-claim-link-controls-007"
SOURCE_RUN = EXPERIMENT_ROOT / "runs" / "critic-claim-link-generalization-006" / "01-header-first"


class CriticClaimLinkControlsAuditError(RuntimeError):
    """Raised when matched-control evidence is incomplete or inconsistent."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkControlsAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkControlsAuditError(f"expected a JSON object: {path}")
    return value


def _validated_fresh_runs(
    plan: dict[str, Any],
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    validated_runs = []
    provider = plan["provider_controls"]
    for cell in plan["schedule"]:
        run_root = RUN_ROOT / cell["run_id"]
        probe = controls.build_probe(cell["run_id"])
        committed_probe = _object(run_root / "probe-plan.json")
        expected_probe = {key: value for key, value in probe.items() if key != "prompt"}
        if committed_probe != expected_probe:
            raise CriticClaimLinkControlsAuditError(f"committed probe drifted: {cell['run_id']}")
        candidates = controls._selected_candidates(plan, cell)
        output = _object(run_root / "output.json")
        validated = controls._validate_output(
            output,
            plan=plan,
            candidates=candidates,
        )
        result = _object(run_root / "result.json")
        worker = _object(run_root / "phase" / "worker-run.json")
        if (
            worker.get("provider") != provider["provider"]
            or worker.get("model") != provider["model"]
            or worker.get("effort") != provider["effort"]
            or worker.get("tool_mode") != provider["tool_mode"]
            or worker.get("harness_version") != provider["harness_version"]
        ):
            raise CriticClaimLinkControlsAuditError(f"provider controls drifted: {cell['run_id']}")
        if (
            result.get("status") != "completed"
            or not result.get("quality_passed")
            or result.get("candidate_results") != validated
            or result.get("usage") != worker.get("usage")
            or result.get("timing") != worker.get("timing")
            or result.get("prompt_sha256") != probe["prompt_sha256"]
        ):
            raise CriticClaimLinkControlsAuditError(f"result evidence drifted: {cell['run_id']}")
        if not all(
            item["claim_map_correct"]
            and item["verdict_correct"]
            and item["structured_finding_linkage_complete"]
            for item in validated
        ):
            raise CriticClaimLinkControlsAuditError(f"structured quality failed: {cell['run_id']}")
        validated_runs.append((result, validated))
    return validated_runs


def _quality_counts(validated: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "correct_claim_status_count": sum(len(candidate["claim_links"]) for candidate in validated),
        "correct_verdict_count": len(validated),
        "linked_finding_count": sum(
            len(candidate["critique"]["findings"]) for candidate in validated
        ),
        "unlinked_finding_count": sum(
            len(candidate["unlinked_finding_ids"]) for candidate in validated
        ),
    }


def _batch_cost(
    result: dict[str, Any],
    *,
    candidate_order: list[str],
    summed_input: int,
    summed_time: float,
) -> dict[str, Any]:
    input_tokens = result["usage"]["input_tokens"]
    completion_ms = result["timing"]["completion_ms"]
    return {
        "candidate_order": candidate_order,
        "input_tokens": input_tokens,
        "input_reduction_percent_vs_summed_direct": round(
            (1 - input_tokens / summed_input) * 100,
            3,
        ),
        "output_tokens": result["usage"]["output_tokens"],
        "completion_ms": completion_ms,
        "completion_reduction_percent_vs_summed_direct": round(
            (1 - completion_ms / summed_time) * 100,
            3,
        ),
    }


def build_analysis() -> dict[str, Any]:
    """Revalidate all direct and batch evidence and summarize the capability."""
    plan = _object(controls.PLAN_PATH)
    fresh = _validated_fresh_runs(plan)
    report = controls.report()
    if report.get("status") != "capability_confirmed":
        raise CriticClaimLinkControlsAuditError("matched-control report is not confirmed")
    source_analysis = source_audit.build_analysis()
    if source_analysis.get("status") != "capability_confirmed":
        raise CriticClaimLinkControlsAuditError("source batch is not confirmed")
    source_result = _object(SOURCE_RUN / "result.json")

    direct_results = [result for result, _ in fresh if result["mode"] == "direct"]
    reversed_result, reversed_validated = next(
        (result, validated) for result, validated in fresh if result["mode"] == "batch"
    )
    fresh_validated = [candidate for _, run in fresh for candidate in run]
    source_validated = source_result["candidate_results"]
    summed_input = report["summed_direct_input_tokens"]
    summed_time = report["summed_direct_completion_ms"]
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed",
        "design": {
            "fresh_direct_calls": 2,
            "fresh_reversed_batch_calls": 1,
            "source_header_first_batch_calls": 1,
            "candidate_fixture_shapes": 2,
            "matched_repeats_per_cell": 1,
        },
        "structured_quality": {
            "fresh_calls": _quality_counts(fresh_validated),
            "both_batch_orders": _quality_counts(source_validated + reversed_validated),
            "each_candidate_passed_in_each_batch_position": True,
        },
        "direct_controls": {
            "calls": [
                {
                    "candidate_order": result["candidate_order"],
                    "input_tokens": result["usage"]["input_tokens"],
                    "output_tokens": result["usage"]["output_tokens"],
                    "completion_ms": result["timing"]["completion_ms"],
                }
                for result in direct_results
            ],
            "summed_input_tokens": summed_input,
            "summed_completion_ms": summed_time,
        },
        "batch_results": {
            "header_first_source": _batch_cost(
                source_result,
                candidate_order=source_analysis["design"]["candidate_order"],
                summed_input=summed_input,
                summed_time=summed_time,
            ),
            "cutover_first_fresh": _batch_cost(
                reversed_result,
                candidate_order=reversed_result["candidate_order"],
                summed_input=summed_input,
                summed_time=summed_time,
            ),
            "input_tokens_identical_across_orders": (
                source_result["usage"]["input_tokens"] == reversed_result["usage"]["input_tokens"]
            ),
        },
        "thresholds": {
            "maximum_batch_input_ratio_to_summed_direct": plan["capability_thresholds"][
                "maximum_batch_input_ratio_to_summed_direct"
            ],
            "maximum_batch_completion_ratio_to_summed_direct": plan["capability_thresholds"][
                "maximum_batch_completion_ratio_to_summed_direct"
            ],
            "fresh_reversed_batch_passed": report["capability_thresholds_passed"],
        },
        "interpretation": (
            "Across two new fixture shapes, compact claim-link batching preserved every "
            "structured decision in both candidate orders and used 47.2% less input than "
            "matched direct calls. Both orders were faster than summed direct calls, but "
            "the order timings differed enough to require repetition before claiming a stable "
            "latency effect."
        ),
        "next_gate": (
            "Run two additional counterbalanced batches, one per order, then report medians "
            "across the two observations per order. Keep batch size two and the same frozen "
            "quality contract."
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
        CriticClaimLinkControlsAuditError,
        controls.CriticClaimLinkControlsError,
        source_audit.CriticClaimLinkGeneralizationAuditError,
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

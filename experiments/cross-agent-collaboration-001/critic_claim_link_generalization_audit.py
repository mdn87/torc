"""Audit the new-fixture compact claim-link capability without a model call."""

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

import critic_claim_link_generalization as generalization  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
RUN_ROOT = EXPERIMENT_ROOT / "runs" / "critic-claim-link-generalization-006" / "01-header-first"
PRIOR_ANALYSIS = EXPERIMENT_ROOT / "critic-claim-link-confirmation-005-analysis.json"


class CriticClaimLinkGeneralizationAuditError(RuntimeError):
    """Raised when capability evidence is incomplete or inconsistent."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkGeneralizationAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkGeneralizationAuditError(f"expected a JSON object: {path}")
    return value


def build_analysis() -> dict[str, Any]:
    """Revalidate the frozen capability run and summarize its narrow result."""
    plan = _object(generalization.PLAN_PATH)
    probe = generalization.build_probe()
    committed_probe = _object(RUN_ROOT / "probe-plan.json")
    expected_probe = {key: value for key, value in probe.items() if key != "prompt"}
    if committed_probe != expected_probe:
        raise CriticClaimLinkGeneralizationAuditError("committed probe plan drifted")

    output = _object(RUN_ROOT / "batch-output.json")
    validated = generalization.validate_output(output, plan=plan)
    result = _object(RUN_ROOT / "result.json")
    worker = _object(RUN_ROOT / "phase" / "worker-run.json")
    controls = plan["provider_controls"]
    if (
        worker.get("provider") != controls["provider"]
        or worker.get("model") != controls["model"]
        or worker.get("effort") != controls["effort"]
        or worker.get("tool_mode") != controls["tool_mode"]
        or worker.get("harness_version") != controls["harness_version"]
    ):
        raise CriticClaimLinkGeneralizationAuditError("provider controls drifted")
    if (
        result.get("status") != "capability_confirmed"
        or not result.get("quality_passed")
        or result.get("usage") != worker.get("usage")
        or result.get("timing") != worker.get("timing")
        or result.get("prompt_sha256") != probe["prompt_sha256"]
    ):
        raise CriticClaimLinkGeneralizationAuditError("recorded result drifted")
    if not all(
        item["claim_map_correct"]
        and item["verdict_correct"]
        and item["structured_finding_linkage_complete"]
        for item in validated
    ):
        raise CriticClaimLinkGeneralizationAuditError("structured quality did not pass")

    prior = _object(PRIOR_ANALYSIS)["primary_cost_result"]
    input_tokens = worker["usage"]["input_tokens"]
    completion_ms = worker["timing"]["completion_ms"]
    findings = [finding for candidate in validated for finding in candidate["critique"]["findings"]]
    claim_count = sum(len(item["claim_links"]) for item in validated)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed",
        "design": {
            "fresh_batch_calls": 1,
            "new_fixture_shapes": [
                "Python implementation defect",
                "JSON architecture and cutover plan",
            ],
            "candidate_order": probe["candidate_order"],
            "matched_direct_controls_available": False,
        },
        "structured_quality": {
            "correct_claim_status_count": claim_count,
            "reviewable_claim_status_count": claim_count,
            "correct_verdict_count": len(validated),
            "candidate_count": len(validated),
            "linked_finding_count": len(findings),
            "unlinked_finding_count": sum(len(item["unlinked_finding_ids"]) for item in validated),
        },
        "descriptive_cost": {
            "prompt_bytes": probe["prompt_bytes"],
            "input_tokens": input_tokens,
            "output_tokens": worker["usage"]["output_tokens"],
            "completion_ms": completion_ms,
            "input_difference_percent_vs_prior_confirmed_batch_median": round(
                (input_tokens / prior["median_batch_input_tokens"] - 1) * 100,
                3,
            ),
            "completion_difference_percent_vs_prior_confirmed_batch_median": round(
                (completion_ms / prior["median_batch_completion_ms"] - 1) * 100,
                3,
            ),
            "batch_savings_claim_allowed": False,
        },
        "interpretation": (
            "The compact claim-link contract preserved complete structured quality in one "
            "batch spanning two new fixture shapes. Its absolute cost was close to the prior "
            "confirmed two-fixture batch, but no savings claim is valid without matched direct "
            "controls for these candidates."
        ),
        "next_gate": (
            "Collect one compact claim-link direct control per new candidate, then a reversed-"
            "order batch; repeat only if quality and usage gates justify a confirmation series."
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
        CriticClaimLinkGeneralizationAuditError,
        generalization.CriticClaimLinkGeneralizationError,
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

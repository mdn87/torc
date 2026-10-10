from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_controls_audit as audit  # noqa: E402

ANALYSIS = EXPERIMENT / "critic-claim-link-controls-007-analysis.json"


def test_controls_audit_revalidates_quality_in_both_orders() -> None:
    analysis = audit.build_analysis()

    assert analysis["status"] == "capability_confirmed"
    assert analysis["structured_quality"]["both_batch_orders"] == {
        "correct_claim_status_count": 24,
        "correct_verdict_count": 4,
        "linked_finding_count": 10,
        "unlinked_finding_count": 0,
    }
    assert analysis["structured_quality"]["each_candidate_passed_in_each_batch_position"]


def test_controls_audit_preserves_matched_cost_result() -> None:
    analysis = audit.build_analysis()
    direct = analysis["direct_controls"]
    batches = analysis["batch_results"]

    assert direct["summed_input_tokens"] == 27671
    assert direct["summed_completion_ms"] == 28964.679
    assert batches["input_tokens_identical_across_orders"] is True
    assert batches["cutover_first_fresh"]["input_reduction_percent_vs_summed_direct"] == 47.172
    assert batches["cutover_first_fresh"]["completion_reduction_percent_vs_summed_direct"] == 9.322


def test_committed_analysis_matches_revalidated_evidence() -> None:
    committed = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    assert committed == audit.build_analysis()

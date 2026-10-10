from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_confirmation_audit as audit  # noqa: E402

ANALYSIS = EXPERIMENT / "critic-claim-link-confirmation-005-analysis.json"


def test_confirmation_audit_revalidates_all_structured_quality() -> None:
    analysis = audit.build_analysis()

    assert analysis["status"] == "confirmed"
    assert analysis["design"]["fresh_batch_calls"] == 4
    assert analysis["structured_quality"]["correct_claim_status_count"] == 52
    assert analysis["structured_quality"]["candidate_position_quality_passes"] == 8
    assert analysis["structured_quality"]["unlinked_finding_count"] == 0


def test_confirmation_audit_preserves_primary_cost_result() -> None:
    cost = audit.build_analysis()["primary_cost_result"]

    assert cost["median_batch_input_tokens"] == 14539.5
    assert cost["median_input_reduction_percent_vs_summed_direct"] == 42.09
    assert cost["median_batch_completion_ms"] == 18808.315
    assert cost["median_completion_reduction_percent_vs_summed_direct"] == 19.615
    assert cost["all_frozen_thresholds_passed"] is True


def test_confirmation_audit_balances_positions() -> None:
    order = audit.build_analysis()["order_check"]

    assert order["quality_changed_by_position"] is False
    assert order["by_order"]["refactor_first"]["run_count"] == 2
    assert order["by_order"]["release_first"]["run_count"] == 2


def test_committed_analysis_matches_revalidated_evidence() -> None:
    committed = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    assert committed == audit.build_analysis()

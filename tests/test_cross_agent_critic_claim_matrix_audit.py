from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_matrix_audit as audit  # noqa: E402


def test_structured_capability_audit_preserves_rejection_and_quality() -> None:
    analysis = audit.build_analysis()

    assert analysis["status"] == "complete_rejected_on_time"
    assert analysis["frozen_result_unchanged"] is True
    assert analysis["quality"] == {
        "passed": True,
        "candidate_count": 2,
        "claim_assessment_count": 13,
        "correct_claim_assessment_count": 13,
        "full_legacy_defect_recall_candidates": 2,
        "linked_finding_count": 6,
        "unlinked_finding_count": 0,
    }
    assert analysis["frozen_capability_gates"]["input_gate_passed"] is True
    assert analysis["frozen_capability_gates"]["completion_gate_passed"] is False
    assert analysis["frozen_capability_gates"]["overall_passed"] is False


def test_structured_capability_audit_quantifies_output_overhead() -> None:
    overhead = audit.build_analysis()["post_hoc_output_overhead_audit"]

    assert overhead["structured_input_tokens"] == 14906
    assert overhead["structured_output_tokens"] == 1081
    assert overhead["structured_input_increase_percent"] < 5
    assert overhead["structured_output_increase_percent"] > 100
    assert overhead["structured_completion_increase_percent"] > 50


def test_structured_capability_audit_selects_new_compact_contract() -> None:
    next_gate = audit.build_analysis()["next_gate"]

    assert next_gate["contract"] == "compact_claim_link_map"
    assert next_gate["classification"] == "new contract capability test, not a retry"

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_generalization_audit as audit  # noqa: E402

ANALYSIS = EXPERIMENT / "critic-claim-link-generalization-006-analysis.json"


def test_generalization_audit_revalidates_structured_quality() -> None:
    analysis = audit.build_analysis()

    assert analysis["status"] == "capability_confirmed"
    assert analysis["structured_quality"] == {
        "correct_claim_status_count": 12,
        "reviewable_claim_status_count": 12,
        "correct_verdict_count": 2,
        "candidate_count": 2,
        "linked_finding_count": 5,
        "unlinked_finding_count": 0,
    }


def test_generalization_audit_keeps_cost_descriptive() -> None:
    cost = audit.build_analysis()["descriptive_cost"]

    assert cost["input_tokens"] == 14618
    assert cost["output_tokens"] == 666
    assert cost["completion_ms"] == 19253.713
    assert cost["batch_savings_claim_allowed"] is False


def test_committed_analysis_matches_revalidated_evidence() -> None:
    committed = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    assert committed == audit.build_analysis()

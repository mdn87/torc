from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_confirmation_audit as audit  # noqa: E402


def test_stopped_batch_confirmation_audit_preserves_strict_failure() -> None:
    analysis = audit.build_analysis()

    assert analysis["status"] == "stopped_quality_failure"
    assert analysis["preregistered_result"] == {
        "completed_batch_calls": 3,
        "scheduled_batch_calls": 4,
        "strict_confirmation_passed": False,
        "reason": ("one release-policy critique scored 0.75 deterministic defect-area recall"),
        "fourth_call_permitted": False,
    }
    assert analysis["descriptive_quality"] == {
        "candidate_critiques": 6,
        "correct_changes_requested_verdicts": 6,
        "full_deterministic_recall_critiques": 5,
        "unsupported_finding_count": 0,
    }


def test_stopped_batch_confirmation_cost_is_descriptive_only() -> None:
    analysis = audit.build_analysis()
    cost = analysis["descriptive_cost_not_a_confirmation_claim"]

    assert cost["median_batch_input_tokens"] == 14364
    assert cost["median_input_reduction_percent"] > 42
    assert cost["median_completion_reduction_percent"] > 35


def test_post_hoc_audit_exposes_claim_citation_and_lexical_inflection() -> None:
    analysis = audit.build_analysis()
    misses = analysis["post_hoc_scorer_audit"]["misses"]

    assert len(misses) == 1
    assert misses[0]["candidate_id"] == "release-policy-baseline-v1"
    area = misses[0]["missed_areas"][0]
    assert area["area_id"] == "malformed_and_unknown_records_not_fail_closed"
    assert area["acceptable_claim_ids"] == ["x5"]
    assert len(area["related_findings"]) == 2
    assert area["fail_closed_inflection_observed"] is True
    assert area["any_single_finding_matches_frozen_area"] is False

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_audit as audit  # noqa: E402


def test_compact_claim_link_audit_confirms_quality_and_gates() -> None:
    analysis = audit.build_analysis()

    assert analysis["status"] == "capability_confirmed"
    assert analysis["quality"]["correct_claim_status_count"] == 13
    assert analysis["quality"]["full_legacy_defect_recall_candidates"] == 2
    assert analysis["quality"]["unlinked_finding_count"] == 0
    assert analysis["frozen_capability_gates"]["all_passed"] is True


def test_compact_claim_link_audit_reduces_verbose_output_and_time() -> None:
    comparison = audit.build_analysis()["compact_vs_verbose_matrix"]

    assert comparison["prompt_byte_reduction_percent"] > 15
    assert comparison["output_token_reduction_percent"] > 40
    assert comparison["completion_reduction_percent"] > 30


def test_compact_claim_link_audit_preserves_legacy_scorer_as_descriptive() -> None:
    quality = audit.build_analysis()["quality"]

    assert quality["legacy_lexical_unsupported_finding_count_descriptive_only"] == 1

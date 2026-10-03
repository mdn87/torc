from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_transport_report as report  # noqa: E402


def test_confirmation_report_rescores_committed_evidence() -> None:
    result = report.build_report()

    assert result["status"] == "paused_usage_guard"
    assert result["completed_call_count"] == 1
    assert result["expected_call_count"] == 12
    assert result["remaining_call_count"] == 11
    assert result["groups"][0]["critic_context"] == (
        "claim-capsule-candidate-v1"
    )
    assert result["groups"][0]["median_defect_area_recall"] == 1.0
    assert result["comparisons"] == []
    assert result["usage_checkpoints"][-1]["primary"]["used_percent"] == 90


def test_confirmation_report_rejects_order_drift() -> None:
    plan = report._object(report.DEFAULT_PLAN)
    scores = [
        {
            "candidate_id": "refactor-baseline-v1",
            "critic_context": "full-visible-bundle-v1",
        }
    ]

    with pytest.raises(report.CriticTransportReportError, match="order drift"):
        report._validate_order(plan, scores)

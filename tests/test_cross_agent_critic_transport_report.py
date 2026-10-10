from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_transport_report as report  # noqa: E402

ANALYSIS = EXPERIMENT / "critic-transport-series-002-analysis.json"


def test_confirmation_report_rescores_committed_evidence() -> None:
    result = report.build_report()

    assert result["status"] == "complete"
    assert result["completed_call_count"] == 12
    assert result["expected_call_count"] == 12
    assert result["remaining_call_count"] == 0
    assert result["groups"][0]["critic_context"] == (
        "claim-capsule-candidate-v1"
    )
    assert result["groups"][0]["median_defect_area_recall"] == 1.0
    assert result["comparisons"][0]["compact_call_count"] == 3
    assert result["comparisons"][0]["full_call_count"] == 3
    release_groups = [
        group
        for group in result["groups"]
        if group["candidate_id"] == "release-policy-baseline-v1"
    ]
    assert len(release_groups) == 2
    assert sorted(group["call_count"] for group in release_groups) == [3, 3]
    assert all(group["median_defect_area_recall"] == 1.0 for group in release_groups)
    compact_scores = [
        score
        for score in result["scores"]
        if score["critic_context"] == "claim-capsule-candidate-v1"
    ]
    full_scores = [
        score
        for score in result["scores"]
        if score["critic_context"] == "full-visible-bundle-v1"
    ]
    assert sum(score["defect_area_recall"] == 1.0 for score in compact_scores) == 6
    assert sum(score["defect_area_recall"] == 1.0 for score in full_scores) == 5
    assert sum(score["unsupported_finding_count"] for score in compact_scores) == 0
    assert sum(score["unsupported_finding_count"] for score in full_scores) == 2
    assert {
        checkpoint["primary"]["used_percent"]
        for checkpoint in result["usage_checkpoints"]
    } == {1, 5, 12, 20, 28, 90}


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


def test_confirmation_analysis_matches_deterministic_report() -> None:
    result = report.build_report()
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    compact = [
        score
        for score in result["scores"]
        if score["critic_context"] == "claim-capsule-candidate-v1"
    ]
    full = [
        score
        for score in result["scores"]
        if score["critic_context"] == "full-visible-bundle-v1"
    ]

    assert analysis["status"] == result["status"]
    assert analysis["design"]["total_call_count"] == result["completed_call_count"]
    assert analysis["primary_results"]["total_prompt_bytes"][
        "claim-capsule-candidate-v1"
    ] == sum(score["prompt_bytes"] for score in compact)
    assert analysis["primary_results"]["total_prompt_bytes"][
        "full-visible-bundle-v1"
    ] == sum(score["prompt_bytes"] for score in full)
    assert analysis["primary_results"]["total_reported_input_tokens"][
        "claim-capsule-candidate-v1"
    ] == sum(score["usage"]["input_tokens"] for score in compact)
    assert analysis["primary_results"]["total_reported_input_tokens"][
        "full-visible-bundle-v1"
    ] == sum(score["usage"]["input_tokens"] for score in full)

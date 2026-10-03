from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import native_context_pilot_report as report  # noqa: E402
import native_context_request as request_builder  # noqa: E402


def _evidence(
    arm: str,
    *,
    uncached_input: int,
    completion_ms: float,
    recall: float = 1.0,
    unsupported: int = 0,
) -> dict[str, Any]:
    request = request_builder.request_plan(
        candidate_id="refactor-baseline-v1",
        arm=arm,
        model="gpt-6.1-sol",
    )
    return {
        "schema_version": 1,
        "series_id": "critic-transport-series-003",
        "status": "validated",
        "candidate_id": "refactor-baseline-v1",
        "arm": arm,
        "model": "gpt-6.1-sol",
        "response_id": f"resp-{arm}",
        "request": {
            "input_bytes": request["request_input_bytes"],
            "input_sha256": request["request_input_sha256"],
            "body_sha256": request["request_body_sha256"],
            "plan_sha256": request["plan_sha256"],
        },
        "usage": {
            "input_tokens": uncached_input + 200,
            "cached_input_tokens": 200,
            "uncached_input_tokens": uncached_input,
            "output_tokens": 300,
            "reasoning_output_tokens": 100,
            "total_tokens": uncached_input + 500,
        },
        "timing": {"completion_ms": completion_ms},
        "transport": {
            "spawn_call_count": 0 if arm == "portable_direct" else 1,
        },
        "score": {
            "arm": arm,
            "candidate_id": "refactor-baseline-v1",
            "defect_area_recall": recall,
            "unsupported_finding_count": unsupported,
            "changes_requested_correct": True,
        },
    }


def test_incomplete_report_lists_missing_arms() -> None:
    result = report.build_report(
        [_evidence("portable_direct", uncached_input=1000, completion_ms=1000)]
    )

    assert result["status"] == "incomplete"
    assert result["missing_arms"] == ["native_isolated", "native_inherited"]
    assert result["recommendation"] == "collect_missing_pilot_arms"


def test_complete_report_applies_pilot_and_full_win_thresholds() -> None:
    result = report.build_report(
        [
            _evidence("portable_direct", uncached_input=1000, completion_ms=1000),
            _evidence("native_isolated", uncached_input=800, completion_ms=1100),
            _evidence("native_inherited", uncached_input=1200, completion_ms=900),
        ]
    )

    assert result["status"] == "pilot_complete"
    assert result["surviving_native_arms"] == ["native_isolated"]
    assert result["recommendation"] == "continue_surviving_arms_to_repeats"
    isolated, inherited = result["comparisons"]
    assert isolated["uncached_input_savings_percent"] == 20.0
    assert isolated["meets_full_series_win_threshold_on_pilot"] is True
    assert inherited["uncached_input_savings_percent"] == -20.0
    assert inherited["pilot_survives"] is False


def test_quality_loss_stops_an_otherwise_cheaper_native_arm() -> None:
    result = report.build_report(
        [
            _evidence("portable_direct", uncached_input=1000, completion_ms=1000),
            _evidence(
                "native_isolated",
                uncached_input=700,
                completion_ms=900,
                recall=0.5,
            ),
            _evidence(
                "native_inherited",
                uncached_input=700,
                completion_ms=900,
                unsupported=1,
            ),
        ]
    )

    assert result["surviving_native_arms"] == []
    assert result["recommendation"] == "stop_native_context_series"


def test_duplicate_arm_is_rejected() -> None:
    evidence = _evidence("portable_direct", uncached_input=1000, completion_ms=1000)
    with pytest.raises(report.NativeContextPilotReportError, match="duplicate"):
        report.build_report([evidence, evidence])


def test_model_drift_is_rejected() -> None:
    direct = _evidence("portable_direct", uncached_input=1000, completion_ms=1000)
    isolated = _evidence("native_isolated", uncached_input=800, completion_ms=1000)
    isolated["model"] = "different-model"

    with pytest.raises(report.NativeContextPilotReportError, match="frozen provider"):
        report.build_report([direct, isolated])

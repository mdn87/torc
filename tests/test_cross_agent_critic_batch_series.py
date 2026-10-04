from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_series as series  # noqa: E402


def _plan() -> dict[str, object]:
    return json.loads(series.PLAN_PATH.read_text(encoding="utf-8"))


def _candidate_result(candidate_id: str) -> dict[str, object]:
    required = 2 if candidate_id == "refactor-baseline-v1" else 4
    return {
        "candidate_id": candidate_id,
        "score": {
            "changes_requested_correct": True,
            "defect_area_recall": 1.0,
            "unsupported_finding_count": 0,
            "required_defect_area_count": required,
        },
    }


def _result(run: dict[str, object], input_tokens: int, completion_ms: float) -> dict[str, object]:
    order = run["candidate_order"]
    assert isinstance(order, list)
    return {
        "schema_version": 1,
        "series_id": "critic-batch-confirmation-004",
        "status": "completed",
        "run_index": run["run_index"],
        "run_id": run["run_id"],
        "candidate_order": order,
        "candidate_results": [_candidate_result(item) for item in order],
        "quality_passed": True,
        "usage": {"input_tokens": input_tokens},
        "timing": {"completion_ms": completion_ms},
    }


def test_series_builds_counterbalanced_prompts_without_oracle() -> None:
    plans = [series.build_run(index) for index in range(1, 5)]

    assert [item["candidate_order"] for item in plans] == [
        ["refactor-baseline-v1", "release-policy-baseline-v1"],
        ["release-policy-baseline-v1", "refactor-baseline-v1"],
        ["release-policy-baseline-v1", "refactor-baseline-v1"],
        ["refactor-baseline-v1", "release-policy-baseline-v1"],
    ]
    assert plans[0]["prompt_sha256"] == plans[3]["prompt_sha256"]
    assert plans[1]["prompt_sha256"] == plans[2]["prompt_sha256"]
    assert plans[0]["prompt_sha256"] != plans[1]["prompt_sha256"]
    assert all("oracle.json" not in item["prompt"] for item in plans)
    assert all("required_defect_areas" not in item["prompt"] for item in plans)


def test_series_rejects_out_of_schedule_run_index() -> None:
    with pytest.raises(series.CriticBatchSeriesError, match="outside"):
        series.build_run(5)


def test_summary_confirms_balanced_quality_and_median_savings() -> None:
    plan = _plan()
    schedule = plan["counterbalanced_schedule"]
    results = [
        _result(run, input_tokens, completion_ms)
        for run, input_tokens, completion_ms in zip(
            schedule,
            [14300, 14400, 14500, 14600],
            [15000.0, 15100.0, 15200.0, 15300.0],
            strict=True,
        )
    ]

    report = series.summarize_results(plan, results)

    assert report["status"] == "confirmed"
    assert report["median_batch_input_tokens"] == 14450.0
    assert report["confirmation_thresholds_passed"] is True
    for positions in report["per_candidate_position"].values():
        assert positions == {
            "1": {"runs": 2, "quality_passes": 2},
            "2": {"runs": 2, "quality_passes": 2},
        }


def test_summary_stops_on_quality_failure_before_cost_claim() -> None:
    plan = _plan()
    first = _result(plan["counterbalanced_schedule"][0], 14300, 15000.0)
    failed = copy.deepcopy(first)
    failed["quality_passed"] = False
    failed["candidate_results"][0]["score"]["defect_area_recall"] = 0.5

    report = series.summarize_results(plan, [failed])

    assert report["status"] == "stopped_quality_failure"
    assert "median_batch_input_tokens" not in report


def test_summary_rejects_confirmation_when_median_savings_are_too_small() -> None:
    plan = _plan()
    results = [_result(run, 19000, 15000.0) for run in plan["counterbalanced_schedule"]]

    report = series.summarize_results(plan, results)

    assert report["status"] == "rejected"
    assert report["input_threshold_passed"] is False
    assert report["completion_threshold_passed"] is True

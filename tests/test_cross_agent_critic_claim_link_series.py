from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_series as series  # noqa: E402


def _plan() -> dict[str, object]:
    return json.loads(series.PLAN_PATH.read_text(encoding="utf-8"))


def _candidate_result(candidate_id: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "claim_map_correct": True,
        "structured_finding_linkage_complete": True,
        "score": {
            "changes_requested_correct": True,
            "defect_area_recall": 1.0,
            "unsupported_finding_count": 0,
        },
    }


def _result(run: dict[str, object], input_tokens: int, completion_ms: float) -> dict[str, object]:
    order = run["candidate_order"]
    assert isinstance(order, list)
    return {
        "schema_version": 1,
        "series_id": "critic-claim-link-confirmation-005",
        "status": "completed",
        "run_index": run["run_index"],
        "run_id": run["run_id"],
        "candidate_order": order,
        "candidate_results": [_candidate_result(item) for item in order],
        "quality_passed": True,
        "usage": {"input_tokens": input_tokens, "output_tokens": 600},
        "timing": {"completion_ms": completion_ms},
    }


def test_claim_link_series_builds_counterbalanced_compact_prompts() -> None:
    probes = [series.build_run(index) for index in range(1, 5)]

    assert [item["candidate_order"] for item in probes] == [
        ["refactor-baseline-v1", "release-policy-baseline-v1"],
        ["release-policy-baseline-v1", "refactor-baseline-v1"],
        ["release-policy-baseline-v1", "refactor-baseline-v1"],
        ["refactor-baseline-v1", "release-policy-baseline-v1"],
    ]
    assert probes[0]["prompt_sha256"] == probes[3]["prompt_sha256"]
    assert probes[1]["prompt_sha256"] == probes[2]["prompt_sha256"]
    assert probes[0]["prompt_sha256"] != probes[1]["prompt_sha256"]
    assert all(item["prompt_bytes"] < 7000 for item in probes)
    assert all("required_defect_areas" not in item["prompt"] for item in probes)


def test_claim_link_series_summary_confirms_balanced_savings() -> None:
    plan = _plan()
    results = [
        _result(run, tokens, elapsed)
        for run, tokens, elapsed in zip(
            plan["counterbalanced_schedule"],
            [14500, 14600, 14700, 14800],
            [16000.0, 17000.0, 18000.0, 19000.0],
            strict=True,
        )
    ]

    report = series.summarize_results(plan, results)

    assert report["status"] == "confirmed"
    assert report["median_batch_input_tokens"] == 14650.0
    assert report["confirmation_thresholds_passed"] is True
    for positions in report["per_candidate_position"].values():
        assert positions == {
            "1": {"runs": 2, "quality_passes": 2},
            "2": {"runs": 2, "quality_passes": 2},
        }


def test_claim_link_series_dry_report_is_not_available_before_freeze() -> None:
    plan = _plan()

    assert plan["status"] == "draft"

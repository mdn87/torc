from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import experiment_report as report  # noqa: E402


def _write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _record(
    provider: str,
    input_tokens: int,
    *,
    role: str = "implementer",
    prompt_bytes: int = 1200,
    completion_ms: float = 500.0,
) -> dict[str, object]:
    return {
        "provider": provider,
        "role": role,
        "tool_mode": "none",
        "prompt_bytes": prompt_bytes,
        "usage": {
            "input_tokens": input_tokens,
            "cached_input_tokens": 0,
            "reasoning_output_tokens": 10,
            "output_tokens": 20,
        },
        "timing": {"completion_ms": completion_ms},
    }


def test_report_separates_valid_runs_and_provider_usage(tmp_path: Path) -> None:
    valid = tmp_path / "01-valid"
    _write(valid / "phases" / "01-primary" / "worker-run.json", _record("codex", 100))
    _write(
        valid / "workflow-result.json",
        {
            "fixture_id": "fixture-a",
            "workflow_id": "codex-solo",
            "worker_interface": "patch-artifact-v1",
            "accepted_final": True,
            "phases": [{"record": "phases/01-primary/worker-run.json"}],
        },
    )
    excluded = tmp_path / "02-excluded"
    _write(
        excluded / "phases" / "01-primary" / "worker-run.json",
        _record("codex", 50),
    )
    _write(
        excluded / "workflow-result.json",
        {
            "fixture_id": "fixture-a",
            "workflow_id": "codex-solo",
            "worker_interface": "patch-artifact-v1",
            "accepted_final": False,
            "phases": [{"record": "phases/01-primary/worker-run.json"}],
        },
    )
    _write(
        excluded / "disposition.json",
        {
            "valid_attempt": False,
            "category": "harness_failure",
            "comparative_use": "excluded",
        },
    )
    reviewed = tmp_path / "03-reviewed"
    _write(
        reviewed / "phases" / "01-primary" / "worker-run.json",
        _record("codex", 150),
    )
    _write(
        reviewed / "phases" / "02-critic" / "worker-run.json",
        _record("codex", 50),
    )
    _write(
        reviewed / "workflow-result.json",
        {
            "fixture_id": "fixture-a",
            "workflow_id": "codex-review",
            "worker_interface": "patch-artifact-v1",
            "accepted_final": True,
            "critic_verdict": "approve",
            "revision_performed": False,
            "phases": [
                {"record": "phases/01-primary/worker-run.json"},
                {"record": "phases/02-critic/worker-run.json"},
            ],
        },
    )

    result = report.build_report(tmp_path)

    assert result["run_count"] == 3
    assert result["valid_run_count"] == 2
    assert result["accepted_valid_run_count"] == 2
    assert result["excluded_run_count"] == 1
    usage = result["usage_by_interface_and_provider"]
    assert {item["provider"] for item in usage} == {"codex"}
    assert {item["valid_attempt"] for item in usage} == {True, False}
    assert not any("total_tokens" in item for item in usage)
    codex = next(item for item in usage if item["valid_attempt"])
    excluded_codex = next(item for item in usage if not item["valid_attempt"])
    assert codex["mean_input_tokens_per_reported_phase"] == 100.0
    assert excluded_codex["mean_input_tokens_per_reported_phase"] == 50.0
    comparison = result["matched_workflow_comparisons"][0]
    assert comparison["quality_delta"] == 0
    assert comparison["review_critic_verdict"] == "approve"
    assert comparison["review_critic_context"] == "full-visible-bundle-v1"
    assert comparison["review_revision_performed"] is False
    assert comparison["input_ratio"] == 2.0
    assert comparison["completion_ratio"] == 2.0
    assert result["approved_without_revision_summary"] == {
        "comparison_count": 1,
        "fixture_ids": ["fixture-a"],
        "quality_improvement_count": 0,
        "quality_regression_count": 0,
        "quality_unchanged_count": 1,
        "median_input_ratio": 2.0,
        "median_completion_ratio": 2.0,
    }


def test_report_rejects_evidence_free_run(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    try:
        report.build_report(tmp_path)
    except report.ExperimentReportError as exc:
        assert "no evidence" in str(exc)
    else:
        raise AssertionError("evidence-free run should be rejected")


def test_report_matches_critic_transports_by_candidate_hash(tmp_path: Path) -> None:
    candidate_hash = "a" * 64
    full = tmp_path / "01-full"
    compact = tmp_path / "02-compact"
    _write(
        full / "phases" / "01-critic" / "worker-run.json",
        _record(
            "codex",
            100,
            role="critic",
            prompt_bytes=1000,
            completion_ms=500.0,
        ),
    )
    _write(
        compact / "phases" / "02-critic" / "worker-run.json",
        _record(
            "codex",
            50,
            role="critic",
            prompt_bytes=500,
            completion_ms=1000.0,
        ),
    )
    for run, score_name in (
        (full, "score-candidate.json"),
        (compact, "score-after-primary.json"),
    ):
        _write(
            run / score_name,
            {
                "fixture_id": "fixture-a",
                "workspace_tree_sha256": candidate_hash,
                "accepted": True,
            },
        )
    _write(
        full / "workflow-result.json",
        {
            "fixture_id": "fixture-a",
            "workflow_id": "critic-replay",
            "worker_interface": "patch-artifact-v1",
            "accepted_final": True,
            "critic_context": "full-visible-bundle-v1",
            "critic_verdict": "approve",
            "critic_finding_count": 0,
            "phases": [{"record": "phases/01-critic/worker-run.json"}],
        },
    )
    _write(
        compact / "workflow-result.json",
        {
            "fixture_id": "fixture-a",
            "workflow_id": "codex-review-compact",
            "worker_interface": "patch-artifact-v1",
            "accepted_final": True,
            "critic_context": "claim-capsule-candidate-v1",
            "critic_verdict": "changes_requested",
            "critic_finding_count": 2,
            "phases": [{"record": "phases/02-critic/worker-run.json"}],
        },
    )

    result = report.build_report(tmp_path)

    comparison = result["critic_transport_comparisons"][0]
    assert comparison["candidate_workspace_tree_sha256"] == candidate_hash
    assert comparison["full_sample_count"] == 1
    assert comparison["compact_sample_count"] == 1
    assert comparison["full_changes_requested_count"] == 0
    assert comparison["compact_changes_requested_count"] == 1
    assert comparison["full_total_findings"] == 0
    assert comparison["compact_total_findings"] == 2
    assert comparison["full_verdict"] == "approve"
    assert comparison["compact_verdict"] == "changes_requested"
    assert comparison["compact_finding_count"] == 2
    assert comparison["compact_prompt_byte_ratio"] == 0.5
    assert comparison["compact_input_ratio"] == 0.5
    assert comparison["compact_completion_ratio"] == 2.0
    assert comparison["compact_median_prompt_byte_ratio"] == 0.5
    assert comparison["compact_median_input_ratio"] == 0.5
    assert comparison["compact_median_completion_ratio"] == 2.0


def test_committed_critic_transport_analysis_matches_run_evidence() -> None:
    result = report.build_report()
    comparison = result["critic_transport_comparisons"][0]
    analysis = json.loads(
        (EXPERIMENT / "critic-transport-analysis.json").read_text(encoding="utf-8")
    )

    assert analysis["candidate_workspace_tree_sha256"] == comparison[
        "candidate_workspace_tree_sha256"
    ]
    assert analysis["full_context"]["run_ids"] == comparison["full_run_ids"]
    assert analysis["compact_context"]["run_ids"] == comparison["compact_run_ids"]
    assert analysis["full_context"]["changes_requested_count"] == comparison[
        "full_changes_requested_count"
    ]
    assert analysis["compact_context"]["changes_requested_count"] == comparison[
        "compact_changes_requested_count"
    ]
    assert analysis["full_context"]["finding_count"] == comparison[
        "full_total_findings"
    ]
    assert analysis["compact_context"]["finding_count"] == comparison[
        "compact_total_findings"
    ]
    assert analysis["compact_to_full_ratios"] == {
        "median_prompt_bytes": comparison["compact_median_prompt_byte_ratio"],
        "median_input_tokens": comparison["compact_median_input_ratio"],
        "median_completion_ms": comparison["compact_median_completion_ratio"],
    }

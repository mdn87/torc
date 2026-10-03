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


def _record(provider: str, input_tokens: int) -> dict[str, object]:
    return {
        "provider": provider,
        "role": "implementer",
        "tool_mode": "none",
        "prompt_bytes": 1200,
        "usage": {
            "input_tokens": input_tokens,
            "cached_input_tokens": 0,
            "reasoning_output_tokens": 10,
            "output_tokens": 20,
        },
        "timing": {"completion_ms": 500.0},
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
    assert comparison["review_revision_performed"] is False
    assert comparison["input_ratio"] == 2.0
    assert comparison["completion_ratio"] == 2.0


def test_report_rejects_evidence_free_run(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    try:
        report.build_report(tmp_path)
    except report.ExperimentReportError as exc:
        assert "no evidence" in str(exc)
    else:
        raise AssertionError("evidence-free run should be rejected")

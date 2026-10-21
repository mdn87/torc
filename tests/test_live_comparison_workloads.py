"""Real repository tasks need a sealed source and an independently held scorer."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/session-continuation-001/workloads.py"


def _module():
    spec = importlib.util.spec_from_file_location("continuation_workloads", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workload_staging_hides_solution_and_scoring(tmp_path):
    workloads = _module()
    first = workloads.stage("capsule-context", tmp_path / "one")
    second = workloads.stage("capsule-context", tmp_path / "two")
    assert first["workspace_sha256"] == second["workspace_sha256"]
    assert first["evidence_class"] == "historical_repository_task"
    assert not (tmp_path / "one/src/torc/continuation_context.py").exists()
    assert not (tmp_path / "one/tests/test_continuation_context.py").exists()
    assert (tmp_path / "one/src/torc/p5_capsules.py").exists()
    assert (tmp_path / "one/CONTINUATION_TASK.md").is_file()
    assert not any(p.name == ".git" for p in (tmp_path / "one").rglob("*"))
    with pytest.raises(ValueError, match="exists"):
        workloads.stage("capsule-context", tmp_path / "one")


def test_reference_scoring_proves_baseline_failure_and_real_solution(tmp_path):
    workloads = _module()
    report = workloads.verify_references(tmp_path / "references")
    assert report["live_model_trials"] == 0
    assert report["all_passed"]
    assert len(report["workloads"]) == 2
    for result in report["workloads"]:
        assert result["baseline"]["exit_status"] != 0
        assert result["reference"]["exit_status"] == 0
        assert result["mutant"]["exit_status"] == 1
        assert result["protected_change_rejected"]
    expected = json.loads((SCRIPT.parent / "reference-report.json").read_text())
    assert workloads.reference_summary(report) == expected


def test_scoring_packet_is_arm_blind_and_pins_the_candidate(tmp_path):
    workloads = _module()
    candidate = tmp_path / "candidate"
    workloads.stage("whole-task-usage", candidate)
    workload = workloads.specification("whole-task-usage")
    target = candidate / workload["editable_paths"][0]
    target.write_text("# deliberately incomplete candidate\n")
    job = workloads.prepare_score("whole-task-usage", candidate, tmp_path / "score")
    assert "arm" not in job and "context" not in job
    assert job["candidate_sha256"] == workloads.tree_sha256(candidate)
    assert job["worker_workspace_modified"] is False
    assert (tmp_path / "score/tests/test_continuation_usage.py").is_file()
    assert not (candidate / "tests/test_continuation_usage.py").exists()
    target.unlink()
    target.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        workloads.prepare_score("whole-task-usage", candidate, tmp_path / "reject")


def test_protected_sources_reject_before_scoring(tmp_path):
    workloads = _module()
    candidate = tmp_path / "candidate"
    workloads.stage("capsule-context", candidate)
    (candidate / "src/torc/p5_capsules.py").write_text("# forbidden replacement\n")
    with pytest.raises(ValueError, match="protected"):
        workloads.prepare_score("capsule-context", candidate, tmp_path / "score")
    assert not (tmp_path / "score").exists()

"""The trusted scorer qualification must remain separate from live admission."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[1]
          / "experiments/session-continuation-001/scoring_qualification.py")


def module():
    spec = importlib.util.spec_from_file_location("scoring_qualification", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec.loader.exec_module(result)
    finally:
        sys.path.pop(0)
    return result


def controls():
    return [{"task": task, "kind": kind, "timed_out": False, "interrupted": False,
             "runtime_unchanged": True, "inputs_unchanged": True,
             "exit_code": 0 if kind == "reference" else 1,
             "stdout": "......... [100%]" if kind == "reference" else "FAILED test_contract"}
            for task in ("capsule-context", "whole-task-usage")
            for kind in ("baseline", "reference", "mutant")]


def test_scorer_needs_complete_discriminating_control_set():
    scorer = module()
    rows = controls()
    assert scorer.controls_pass(rows)
    assert not scorer.controls_pass(rows[:-1])
    assert not scorer.controls_pass([*rows, rows[0]])
    rows[2]["exit_code"] = 0
    assert not scorer.controls_pass(rows)


@pytest.mark.parametrize("defect", ["timeout", "runtime", "inputs", "empty", "unknown"])
def test_scorer_rejects_incomplete_or_changed_reference_execution(defect):
    rows = controls()
    row = rows[1]
    field, value = {"timeout": ("timed_out", True), "runtime": ("runtime_unchanged", False),
                    "inputs": ("inputs_unchanged", False), "empty": ("stdout", ""),
                    "unknown": ("exit_code", None)}[defect]
    row[field] = value
    assert not module().controls_pass(rows)


def test_scorer_refuses_uninspected_owner_before_creating_output(tmp_path, monkeypatch):
    scorer = module()
    monkeypatch.setattr(scorer.sys, "platform", "darwin")
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="owner changed"):
        scorer.qualify(tmp_path / "uninspected", tmp_path / "runtime", destination)
    assert not destination.exists()


def test_retained_scorer_evidence_covers_every_attempt_and_current_source():
    import hashlib
    import json
    import zipfile

    report = json.loads(SCRIPT.with_name("scoring-qualification-report.json").read_text())
    archive = SCRIPT.parent / report["evidence_archive"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == report["archive_sha256"]
    assert report["owned_process_attempts"] == 74
    assert report["live_model_calls"] == 0
    assert report["latest_passed"] is True
    assert report["live_scoring_admitted"] is False
    assert report["runs"][0]["trusted_fixture_path_passed"] is False
    with zipfile.ZipFile(archive) as evidence:
        assert evidence.testzip() is None
        for run in report["runs"]:
            prefix = run["archive_prefix"]
            raw = evidence.read(prefix + "/scoring-qualification.json")
            assert hashlib.sha256(raw).hexdigest() == run["report_sha256"]
            for kind in ("start", "owner", "result"):
                members = [name for name in evidence.namelist()
                           if name.startswith(prefix + "/receipts/")
                           and name.endswith("-" + kind + ".json")]
                assert len(members) == run["attempt_count"]
        assert evidence.read("final-scoring_qualification.py") == SCRIPT.read_bytes()
    assert report["runs"][-1]["source_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()

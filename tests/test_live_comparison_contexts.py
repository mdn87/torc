"""Both context strategies must use the same task evidence without granting authority."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/session-continuation-001/contexts.py"


def _module():
    spec = importlib.util.spec_from_file_location("continuation_task_contexts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_contexts_reproduce_and_share_evidence(tmp_path):
    contexts = _module()
    first = contexts.prepare("capsule-context", tmp_path / "first", carry_limit=400)
    second = contexts.prepare("capsule-context", tmp_path / "second", carry_limit=400)
    assert first == second
    assert first["launch_authorized"] is False
    assert first["native_arms_ready"] is False
    assert first["state_store_unchanged_during_verification"] is True
    contexts.verify(tmp_path / "first", first, expected_manifest_id=first["manifest_id"])
    arms = first["arms"]
    assert set(arms) == {"compiled_prompt", "torc_capsule"}
    assert arms["compiled_prompt"]["report_sha256"] == arms["torc_capsule"]["report_sha256"]
    for arm in arms.values():
        prompt = (tmp_path / "first" / arm["prompt"]["path"]).read_bytes()
        context = (tmp_path / "first" / arm["context"]["path"]).read_bytes()
        start, end = arm["context_byte_span"]
        assert prompt[start:end] == context
        assert arm["binding_id"].startswith("sha256:")
    assert first["bridge"]["authority_transferred"] is False
    assert first["bridge"]["retry_authorized"] is False
    assert first["bridge"]["quiescence"] == "unknown"
    assert first["bridge"]["status"] == "held"


def test_context_or_report_substitution_and_wrong_pin_reject(tmp_path):
    contexts = _module()
    manifest = contexts.prepare("whole-task-usage", tmp_path / "prepared", carry_limit=400)
    with pytest.raises(ValueError, match="pin"):
        contexts.verify(tmp_path / "prepared", manifest, expected_manifest_id="0" * 64)
    path = tmp_path / "prepared" / manifest["arms"]["torc_capsule"]["context"]["path"]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash"):
        contexts.verify(tmp_path / "prepared", manifest,
                        expected_manifest_id=manifest["manifest_id"])


def test_actual_head_change_invalidates_prepared_context(tmp_path):
    from torc.store import Store

    contexts = _module()
    root = tmp_path / "prepared"
    manifest = contexts.prepare("capsule-context", root, carry_limit=400)
    with Store(root / manifest["state_dir"]) as store:
        lineage = store.get_lineage(manifest["lineage_id"])
        state = store.get_revision(lineage["head_revision_id"])["canonical_state"]
        store.append_revision(manifest["lineage_id"], state, event_type="checkpoint",
                              activation_id=manifest["source_activation_id"])
    with pytest.raises(ValueError, match="stale"):
        contexts.verify(root, manifest, expected_manifest_id=manifest["manifest_id"])


def test_prepared_workspace_still_uses_original_independent_scorer(tmp_path):
    contexts = _module()
    root = tmp_path / "prepared"
    manifest = contexts.prepare("whole-task-usage", root, carry_limit=400)
    job = contexts.workloads.prepare_score("whole-task-usage", root / "workspace",
                                          tmp_path / "score")
    assert job["candidate_sha256"] == manifest["workspace_sha256"]
    assert not (root / "workspace/tests/test_continuation_usage.py").exists()
    state = json.loads((root / manifest["canonical_state"]["path"]).read_text())
    for decision in state["self_model"]["settled_decisions"]:
        assert decision in (root / "workspace/CONTINUATION_TASK.md").read_text().replace("\n", " ")


def test_replay_and_public_verify_command(tmp_path):
    import subprocess

    contexts = _module()
    actual = contexts.replay(tmp_path / "replay")
    expected = json.loads((SCRIPT.parent / "contexts-report.json").read_text())
    assert actual == expected
    root = tmp_path / "replay/capsule-context"
    manifest_id = actual["tasks"]["capsule-context"]["manifest_id"]
    run = subprocess.run([sys.executable, str(SCRIPT), "verify", "--root", str(root),
                          "--expected-manifest-id", manifest_id], capture_output=True,
                         text=True, check=True)
    assert json.loads(run.stdout)["torc_capsule"]["retry_authorized"] is False


def test_too_small_capsule_budget_does_not_publish_a_manifest(tmp_path):
    from torc.errors import ProjectionBudgetError

    contexts = _module()
    with pytest.raises(ProjectionBudgetError):
        contexts.prepare("capsule-context", tmp_path / "prepared", carry_limit=1)
    assert not (tmp_path / "prepared/contexts-manifest.json").exists()

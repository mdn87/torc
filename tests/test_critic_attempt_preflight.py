"""Frozen configuration failures must not consume an experiment attempt."""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments/cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_probe as batch  # noqa: E402
import critic_batch_series as series  # noqa: E402


@pytest.fixture(params=[batch, series], ids=["probe", "series"])
def attempt(request, tmp_path, monkeypatch):
    runner = request.param
    plan = json.loads(runner.PLAN_PATH.read_text(encoding="utf-8"))
    plan["status"] = "ready" if runner is batch else "frozen_before_live_runs"
    plan_path = tmp_path / "plan.json"
    root = tmp_path / "experiment"
    if runner is batch:
        baseline_path = Path("runs/critic-transport-002")
        shutil.copytree(EXPERIMENT / baseline_path, root / baseline_path)
    monkeypatch.setattr(runner, "PLAN_PATH", plan_path)
    monkeypatch.setattr(runner, "EXPERIMENT_ROOT", root)
    manifest = copy.deepcopy(batch.workflow.load_manifest())
    manifest["timeout_seconds"] = 731
    manifest["providers"]["codex"]["model"] = "preflight-sentinel"
    monkeypatch.setattr(batch.workflow, "load_manifest", lambda: manifest)
    monkeypatch.setattr(batch.workflow, "_apparatus_revision", lambda: "fixture-revision")
    calls = {"snapshot": 0, "worker": [], "apparatus": 0}

    def snapshot(**kwargs):
        calls["snapshot"] += 1
        return {"decision": "proceed"}

    def worker(**kwargs):
        calls["worker"].append(kwargs)
        raise batch.worker_runner.WorkerRunnerError("host lookup failed")

    def apparatus(plan):
        calls["apparatus"] += 1

    monkeypatch.setattr(batch.codex_usage_snapshot, "read_snapshot", snapshot)
    monkeypatch.setattr(batch.worker_runner, "execute_worker", worker)
    monkeypatch.setattr(series, "_verify_apparatus", apparatus)

    def execute():
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        probe = runner.build_probe() if runner is batch else runner.build_run(1)
        if runner is batch:
            run_dir = root / plan["call_budget"]["run_directory"]
            kwargs = {}
            error = batch.CriticBatchProbeError
        else:
            run_dir = series._resolve_run_dir(plan, plan["counterbalanced_schedule"][0])
            kwargs = {"run_index": 1}
            error = series.CriticBatchSeriesError
        invoke = runner.execute_probe if runner is batch else runner.execute_run
        return run_dir, error, lambda: invoke(
            run_dir=run_dir, expected_plan_sha256=probe["plan_sha256"],
            expected_prompt_sha256=probe["prompt_sha256"], **kwargs,
        )

    return runner, plan, manifest, calls, execute


@pytest.mark.parametrize("field,value", [
    ("provider", "claude-code"), ("transport", "unknown"),
    ("executable", "bad\x00path"), ("model", " "), ("model", "x" * 257),
    ("harness_version", " version "), ("harness_version", "x" * 201),
    ("timeout_seconds", True), ("timeout_seconds", "1"),
    ("timeout_seconds", float("nan")), ("timeout_seconds", float("inf")),
    ("timeout_seconds", 10**400), ("timeout_seconds", 0.0009),
    ("timeout_seconds", 4294967.295),
    ("effort", ""), ("effort", "x" * 257), ("series_id", "bad\ud800"),
])
def test_bad_frozen_input_does_not_reserve_attempt(attempt, field, value):
    runner, plan, manifest, calls, execute = attempt
    if field == "timeout_seconds":
        manifest[field] = value
    elif field == "effort":
        plan["provider_controls"][field] = value
    elif field == "series_id":
        plan[field] = value
    else:
        manifest["providers"]["codex"][field] = value
    run_dir, error, invoke = execute()
    with pytest.raises(error, match="preflight:"):
        invoke()
    assert not run_dir.exists()
    assert calls["snapshot"] == 0
    assert calls["worker"] == []
    if runner is series:
        assert calls["apparatus"] == 1


def test_missing_provider_does_not_reserve_attempt(attempt):
    _, _, manifest, calls, execute = attempt
    del manifest["providers"]["codex"]
    run_dir, error, invoke = execute()
    with pytest.raises(error, match="preflight:"):
        invoke()
    assert not run_dir.exists()
    assert calls["snapshot"] == 0
    assert calls["worker"] == []


def test_host_failure_keeps_excluded_attempt_and_frozen_settings(attempt):
    _, _, _, calls, execute = attempt
    run_dir, error, invoke = execute()
    with pytest.raises(error, match="excluded"):
        invoke()
    disposition = json.loads((run_dir / "disposition.json").read_text())
    assert disposition["model_call_may_have_started"] is False
    assert disposition["retry_allowed"] is False
    assert calls["snapshot"] == 1
    assert len(calls["worker"]) == 1
    assert calls["worker"][0]["model"] == "preflight-sentinel"
    assert calls["worker"][0]["timeout_seconds"] == 731
    with pytest.raises(error, match="already exists"):
        invoke()


def test_missing_series_revision_and_probe_baseline_fail_before_reservation(attempt):
    runner, plan, _, calls, execute = attempt
    if runner is series:
        del plan["apparatus_revision"]
    else:
        plan["matched_direct_baseline"]["summed_median_input_tokens"] = 0
    run_dir, error, invoke = execute()
    with pytest.raises(error, match="preflight:"):
        invoke()
    assert not run_dir.exists()
    assert calls["snapshot"] == 0
    assert calls["worker"] == []

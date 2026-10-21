"""Frozen comparisons must not silently lose trials, evidence or uncertainty."""

import copy
import hashlib
import json

import pytest

from torc.canonical import payload_sha256


def _plan(root, count=2):
    from torc.continuation_trials import file_ref

    def asset(name, content):
        (root / name).write_text(content)
        return file_ref(root, name)

    common = asset("common.txt", "same instructions, history access and tools")
    scorer = asset("scorer.txt", "hidden independent scoring contract")
    report = asset("report.json", '{"retry_authorized":false}')
    return {
        "cohort_id": "offline-example", "experiment": "A", "purpose": "pilot",
        "seed": 37, "repetitions": 2, "arms": ["compiled_prompt", "torc_capsule"],
        "lane": {"provider": None, "model": None, "effort": None, "harness_version": None,
                 "billing_mode": "subscription", "qualification_ref": None},
        "resources": {"authorization_ref": None, "max_arm_runs": 12,
                      "max_total_seconds": 7200, "max_api_usd": 0},
        "telemetry": {"exporter_version": None, "semantics_ref": None,
                      "proxy_compatible": False},
        "instructions_ref": common, "execution_contract_ref": common,
        "sampling_plan_ref": common,
        "workloads": [
            {"workload_id": f"w{i}", "stratum": "cold", "evidence_class": "calibration",
             "history_refs": [common], "workspace_refs": [common], "report_ref": report,
             "scoring_refs": [scorer], "contexts": {
                 "compiled_prompt": asset(f"prompt-{i}.txt", "history-informed prompt"),
                 "torc_capsule": asset(f"capsule-{i}.json", '{"synthetic":true}')},
             "capsule_verification_ref": None}
            for i in range(count)
        ],
    }


def _result(manifest, row, *, success=True, tokens=100, missing=False):
    from test_continuation_usage import _task

    task = _task()
    task.update(task_id=row["trial_id"], arm=row["arm"])
    for group in task["usage_groups"]:
        group["observations"][0]["usage"]["input_tokens"] = tokens
    if missing:
        del task["usage_groups"][0]["observations"][0]["usage"]["output_tokens"]
    candidate = hashlib.sha256(row["trial_id"].encode()).hexdigest()
    return {"manifest_id": manifest["manifest_id"], "trial_id": row["trial_id"],
            "candidate_sha256": candidate, "accounting_input": task,
            "score": {"trial_id": row["trial_id"], "candidate_sha256": candidate,
                      "source": "independent_scorer", "blinded": True,
                      "evidence_ref": "fixture-test-receipt", "verified_success": success,
                      "critical_failures": []},
            "metrics": {"elapsed_seconds": 10, "repeated_investigation_count": 2,
                        "operator_seconds": 0}}


def test_manifest_deterministic_and_missing_live_inputs_block(tmp_path):
    from torc.continuation_trials import prepare_manifest, verify_manifest

    plan = _plan(tmp_path)
    manifest = prepare_manifest(plan, tmp_path)
    assert manifest == prepare_manifest(plan, tmp_path)
    assert len(manifest["schedule"]) == 8
    assert len({r["trial_id"] for r in manifest["schedule"]}) == 8
    assert manifest["state"] == "draft"
    assert manifest["launch_authorized"] is False
    verify_manifest(manifest, tmp_path, expected_manifest_id=manifest["manifest_id"])
    with pytest.raises(ValueError, match="not ready"):
        prepare_manifest(plan, tmp_path, require_ready=True)
    changed = copy.deepcopy(manifest)
    changed["plan"]["seed"] = 99
    with pytest.raises(ValueError):
        verify_manifest(changed, tmp_path, expected_manifest_id=manifest["manifest_id"])
    (tmp_path / "common.txt").write_text("substituted evidence")
    with pytest.raises(ValueError, match="hash"):
        verify_manifest(manifest, tmp_path, expected_manifest_id=manifest["manifest_id"])


def test_unbounded_or_leaky_plan_rejected(tmp_path):
    from torc.continuation_trials import prepare_manifest

    plan = _plan(tmp_path)
    plan["resources"]["max_arm_runs"] = 7
    with pytest.raises(ValueError, match="budget"):
        prepare_manifest(plan, tmp_path)
    plan["resources"]["max_arm_runs"] = 12
    plan["workloads"][0]["history_refs"] += plan["workloads"][0]["scoring_refs"]
    with pytest.raises(ValueError, match="scoring"):
        prepare_manifest(plan, tmp_path)


def test_missing_trials_and_usage_prevent_headline_savings(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    rows = [_result(manifest, r, tokens=20 if r["arm"] == "torc_capsule" else 100)
            for r in manifest["schedule"]]
    report = analyze(manifest, rows, tmp_path, expected_manifest_id=manifest["manifest_id"])
    comparison = report["comparisons"][0]
    assert comparison["primary_workload_pairs"] == 2
    assert comparison["median_savings_fraction"] > 0.2
    assert comparison["success_noninferiority_passed"] is False
    assert report["adoption_authorized"] is False
    assert report["trial_count"] == 8
    assert report["attempt_count"] == 16
    primary = next(i for i, r in enumerate(manifest["schedule"]) if r["repetition"] == 0)
    removed = rows.pop(primary)
    report = analyze(manifest, rows, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["comparisons"][0]["median_savings_fraction"] is None
    assert report["missing_trial_ids"] == [removed["trial_id"]]
    rows.append(_result(manifest, manifest["schedule"][primary], missing=True))
    report = analyze(manifest, rows, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["comparisons"][0]["median_savings_fraction"] is None


def test_scoring_binding_and_duplicate_trials_reject(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest, scoring_packet

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    row = manifest["schedule"][0]
    result = _result(manifest, row)
    packet = scoring_packet(manifest, row["trial_id"], result["candidate_sha256"])
    assert "arm" not in packet and "accounting_input" not in packet
    assert "context" not in json.dumps(packet)
    with pytest.raises(ValueError, match="duplicate"):
        analyze(manifest, [result, result], tmp_path,
                expected_manifest_id=manifest["manifest_id"])
    result["score"]["candidate_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="score"):
        analyze(manifest, [result], tmp_path, expected_manifest_id=manifest["manifest_id"])


def test_false_verified_completion_retains_cost_and_fails_critical_gate(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    results = [_result(manifest, r) for r in manifest["schedule"]]
    results[0]["score"]["verified_success"] = False
    report = analyze(manifest, results, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["attempt_count"] == 16
    assert report["critical_failure_count"] == 1
    assert report["criteria_met"] is False
    assert payload_sha256(results) == report["results_sha256"]


def test_exact_bound_has_known_zero_loss_limit_and_repetitions_are_not_samples():
    from torc.continuation_analysis import success_difference_lower_bound

    assert success_difference_lower_bound(0, 0, 100, 0.05) == pytest.approx(
        -(1 - 0.025 ** (1 / 100)))
    assert success_difference_lower_bound(0, 0, 2, 0.05) < -0.05


def test_repetition_missingness_and_missing_scores_stay_visible(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    results = [_result(manifest, row) for row in manifest["schedule"]]
    repeated = next(i for i, row in enumerate(manifest["schedule"]) if row["repetition"] == 1)
    results[repeated]["score"] = None
    report = analyze(manifest, results, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["comparisons"][0]["success_difference_lower_bound"] is None
    assert report["missing_score_trial_ids"] == [results[repeated]["trial_id"]]
    results[repeated]["accounting_input"] = None
    report = analyze(manifest, results, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["comparisons"][0]["median_savings_fraction"] is None
    assert report["attempt_count"] is None
    assert report["known_attempt_count"] == 14


def test_setup_exclusion_never_becomes_free_success_or_replacement(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    results = [_result(manifest, row) for row in manifest["schedule"]]
    row = next(r for r in results if r["accounting_input"]["arm"] == "torc_capsule")
    task = row["accounting_input"]
    task["outcome"] = "declared_failure"
    task["usage_groups"] = []
    task["attempts"] = [{"attempt_id": "setup", "status": "failed",
                         "context_delivered": False, "arm_independent_setup_failure": True,
                         "requests_complete": True, "requests": [], "fallback_from": None,
                         "exclusion_reason": "fixture arm-independent setup failure"}]
    row["score"]["verified_success"] = False
    report = analyze(manifest, results, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["trial_count"] == 8
    assert report["attempt_count"] == 15
    assert report["excluded_attempt_count"] == 1
    assert report["setup_excluded_trial_ids"] == [row["trial_id"]]
    assert report["comparisons"][0]["median_savings_fraction"] is None
    assert not report["comparisons"][0]["success_noninferiority_passed"]


def test_all_declared_baselines_get_multiplicity_correction(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    plan = _plan(tmp_path)
    plan["arms"].append("native_cold")
    for workload in plan["workloads"]:
        workload["contexts"]["native_cold"] = workload["contexts"]["compiled_prompt"]
    manifest = prepare_manifest(plan, tmp_path)
    report = analyze(manifest, [_result(manifest, r) for r in manifest["schedule"]], tmp_path,
                     expected_manifest_id=manifest["manifest_id"])
    assert [r["baseline"] for r in report["comparisons"]] == ["compiled_prompt", "native_cold"]
    assert all(r["primary_workload_pairs"] == 2 and r["alpha"] == 0.025
               for r in report["comparisons"])


def test_missing_primary_success_has_worst_and_best_sensitivity(tmp_path):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    results = [_result(manifest, row) for row in manifest["schedule"]]
    trial = next(row["trial_id"] for row in manifest["schedule"]
                 if row["repetition"] == 0 and row["arm"] == "torc_capsule")
    next(r for r in results if r["trial_id"] == trial)["score"] = None
    report = analyze(manifest, results, tmp_path, expected_manifest_id=manifest["manifest_id"])
    assert report["comparisons"][0]["success_point_sensitivity"] == {"worst": -0.5, "best": 0}


def test_exact_bound_interior_case_and_invalid_counts():
    from torc.continuation_analysis import success_difference_lower_bound

    assert success_difference_lower_bound(1, 0, 2, 0.05) == pytest.approx(
        0.025 ** 0.5 - 0.975 ** 0.5)
    assert success_difference_lower_bound(0, 2, 2, 0.05) == -1
    with pytest.raises(ValueError):
        success_difference_lower_bound(2, 1, 2, 0.05)


def test_external_pin_and_sources_cannot_be_replaced(tmp_path, monkeypatch):
    from torc import continuation_trials as trials

    manifest = trials.prepare_manifest(_plan(tmp_path), tmp_path)
    with pytest.raises(ValueError, match="external pin"):
        trials.verify_manifest(manifest, tmp_path, expected_manifest_id="0" * 64)
    monkeypatch.setattr(trials, "_implementation", lambda: {"modified": "0" * 64})
    with pytest.raises(ValueError, match="implementation"):
        trials.verify_manifest(manifest, tmp_path, expected_manifest_id=manifest["manifest_id"])


def test_assets_cannot_escape_root_and_hidden_copies_are_rejected(tmp_path):
    from torc.continuation_trials import file_ref, prepare_manifest

    plan = _plan(tmp_path)
    with pytest.raises(ValueError, match="relative"):
        file_ref(tmp_path, "../escape")
    (tmp_path / "visible-copy.txt").write_bytes((tmp_path / "scorer.txt").read_bytes())
    plan["workloads"][1]["contexts"]["compiled_prompt"] = file_ref(tmp_path, "visible-copy.txt")
    with pytest.raises(ValueError, match="scoring"):
        prepare_manifest(plan, tmp_path)


@pytest.mark.parametrize("field,value", [("elapsed_seconds", float("nan")),
                                         ("operator_seconds", -1),
                                         ("repeated_investigation_count", 2.5)])
def test_invalid_metrics_reject(tmp_path, field, value):
    from torc.continuation_analysis import analyze
    from torc.continuation_trials import prepare_manifest

    manifest = prepare_manifest(_plan(tmp_path), tmp_path)
    result = _result(manifest, manifest["schedule"][0])
    result["metrics"][field] = value
    with pytest.raises(ValueError, match="metric|integer"):
        analyze(manifest, [result], tmp_path, expected_manifest_id=manifest["manifest_id"])

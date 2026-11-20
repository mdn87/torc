import hashlib
import json
from pathlib import Path

import pytest

from torc.canonical import payload_sha256
from torc.claude_continuation_analysis import VERSION
from torc.claude_continuation_evidence import OWNER, analyze, owner_metrics

MODEL = "fixture-model"
SHA = "1" * 64
TERMS = {
    "inputTokens": 2,
    "cacheCreationInputTokens": 3,
    "cacheReadInputTokens": 5,
    "outputTokens": 7,
}
USAGE = {
    "input_tokens": 2,
    "cache_creation_input_tokens": 3,
    "cache_read_input_tokens": 5,
    "output_tokens": 7,
    "cache_creation": {"ephemeral_5m_input_tokens": 2, "ephemeral_1h_input_tokens": 1},
}
SETTINGS = {"service_tier": "standard", "speed": "standard", "inference_geo": "global"}
POLICY = {
    "client_version": "fixture",
    "main_model": MODEL,
    "auxiliary_models": [],
    "launch_sha256": SHA,
    "cache_sharing_scope": "unknown",
    "prices": {
        "as_of": "2026-11-20",
        "usage_settings": {k: [v] for k, v in SETTINGS.items()},
        "models": {
            MODEL: [
                {"through": None, "fresh": 3, "write_5m": 4, "write_1h": 6, "read": 1, "output": 15}
            ]
        },
    },
}


def usage(spec):
    binding = dict(
        correlation_id=spec["trial_id"],
        task_sha256=spec["prompt_sha256"],
        version="fixture",
        run_id="r",
        assignment_id="a",
        launch_sha256=SHA,
    )
    call = dict(
        **binding,
        attempt_id="attempt-one",
        role="worker",
        status="returned",
        issues=[],
        terminal={
            "usage": USAGE.copy(),
            "modelUsage": {MODEL: TERMS},
            "total_cost_usd": 0.01,
            **SETTINGS,
        },
        requests=[{"id": "msg_1", "model": MODEL, "usage": USAGE.copy()}],
        first_request_input=10,
        total_context_tokens=10,
        aggregate_only_models=[],
        diagnostics=[],
        evidence_sha256=SHA,
        reserved_at="2026-11-20T09:00:00Z",
        completed_at="2026-11-20T09:00:01Z",
        elapsed_seconds=1,
    )
    return {
        "contract": OWNER,
        "calls": [call],
        "complete": True,
        "issues": [],
        "completion": {
            "calls": 1,
            "status": "incomplete",
            "reason": "invalid_or_failed_check",
            "task_sha256": spec["prompt_sha256"],
        },
        "first_request_input": 10,
        "total_context_tokens": 10,
        "observed_input_lower_bound": 10,
    }


def test_prices_require_known_ttl_and_settings_and_keep_cli_estimate():
    spec = {"trial_id": "toy", "prompt_sha256": SHA}
    owner = usage(spec)
    metrics = owner_metrics(owner, spec, POLICY)
    assert metrics["estimated_input_usd"] == 25 / 1_000_000
    assert metrics["estimated_output_usd"] == 105 / 1_000_000
    assert metrics["cli_estimate_usd"] == 0.01 and metrics["total_context_tokens"] == 10
    del owner["calls"][0]["requests"][0]["usage"]["cache_creation"]
    assert owner_metrics(owner, spec, POLICY)["estimated_input_usd"] is None
    owner["calls"][0]["terminal"]["speed"] = "fast"
    assert owner_metrics(owner, spec, POLICY)["estimated_output_usd"] is None
    with pytest.raises(ValueError, match="different trial"):
        owner_metrics(owner, {**spec, "trial_id": "other"}, POLICY)


def test_missing_rows_stay_in_cohort_and_artifacts_are_bound(tmp_path):
    prep = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "docs/evidence/2026-11-20-continuation-scorer-preparation.json"
        ).read_bytes()
    )
    trials = [
        dict(
            trial_id=f"{case['case']}-{arm}-{rep}",
            case=case["case"],
            arm=arm,
            prompt_sha256=case["prompt_sha256"][arm],
            repetition=rep,
            position=position,
        )
        for case in prep["cases"]
        for rep in (1, 2)
        for position, arm in enumerate(
            ("compiled", "torc") if rep == 1 else ("torc", "compiled"), 1
        )
    ]
    schedule = {
        "contract": VERSION,
        "policy": POLICY,
        "order_seed": "offline-test",
        "trials": trials,
    }
    results = {"schedule_sha256": payload_sha256(schedule), "trials": []}
    blank = analyze(schedule, prep, results, tmp_path)
    assert blank["unresolved_tasks"] == 8 and blank["acceptance"]["compiled"]["unscored"] == 16
    owner_bytes = json.dumps(usage(trials[0])).encode()
    (tmp_path / "usage.json").write_bytes(owner_bytes)
    ref = {"path": "usage.json", "sha256": hashlib.sha256(owner_bytes).hexdigest()}
    results["trials"].append({"trial_id": trials[0]["trial_id"], "usage": ref})
    assert (
        analyze(schedule, prep, results, tmp_path)["by_task"][0]["observed_input_lower_bounds"][
            "compiled"
        ]
        == 10
    )
    ref["sha256"] = SHA
    with pytest.raises(ValueError, match="Evidence bytes"):
        analyze(schedule, prep, results, tmp_path)


def test_timeout_missing_terminal_and_fallback():
    spec = {"trial_id": "toy", "prompt_sha256": SHA}
    owner = usage(spec)
    owner["completion"]["reason"] = "deadline"
    assert owner_metrics(owner, spec, POLICY)["total_context_tokens"] is None
    owner = usage(spec)
    owner["calls"][0].update(terminal={}, issues=["missing_terminal"])
    metrics = owner_metrics(owner, spec, POLICY)
    assert metrics["total_context_tokens"] is None and metrics["observed_input_lower_bound"] == 10
    changed = {**POLICY, "main_model": "different"}
    assert "unexpected_main_model" in owner_metrics(usage(spec), spec, changed)["deviations"]

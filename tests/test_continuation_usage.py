"""Whole-task totals retain failures, unknowns and exporter provenance."""

from copy import deepcopy

import pytest

from torc.experiment_usage import TOKEN_FIELDS


def _raw(n=10):
    return dict(zip(TOKEN_FIELDS, (n, 20, 3, 2, 5), strict=True))


def _group(group_id, requests, mode="cumulative"):
    return {
        "group_id": group_id, "request_ids": requests, "mode": mode, "complete": True,
        "source": "synthetic", "exporter_version": "fixture-v1",
        "semantics": {"evidence_ref": "fixture-counter-contract-v1", "proxy_compatible": True,
                      "input_cache_nonoverlap": True},
        "observations": [{"observation_id": group_id + "-1", "sequence": 1,
                          "usage": _raw(), "evidence_ref": "fixture-raw-1"}],
    }


def _task():
    return {
        "task_id": "fixture-task", "arm": "torc_capsule", "outcome": "verified_completion",
        "completion_evidence_ref": "independent-fixture-test",
        "attempts": [
            {"attempt_id": "failed-start", "status": "failed", "context_delivered": True,
             "arm_independent_setup_failure": False, "requests_complete": True,
             "fallback_from": None, "requests": [
                 {"request_id": "r1", "role": "root", "phase": "reconstruction"}]},
            {"attempt_id": "fallback", "status": "completed", "context_delivered": True,
             "arm_independent_setup_failure": False, "requests_complete": True,
             "fallback_from": "failed-start", "requests": [
                 {"request_id": "r2", "role": "subagent", "phase": "fallback"}]},
        ],
        "usage_groups": [_group("failed", ["r1"]), _group("fallback", ["r2"])],
    }


def test_failed_start_and_fallback_are_charged_to_originating_arm():
    from torc.continuation_usage import account_task

    task = _task()
    before = deepcopy(task)
    report = account_task(task)
    assert task == before
    assert report["attempt_count"] == 2
    assert report["failed_attempt_count"] == 1
    assert report["fallback_attempt_count"] == 1
    assert report["request_count"] == 2
    assert report["totals"]["input_tokens"] == 20
    assert report["totals"]["cached_input_tokens"] == 40
    assert report["uncached_processed_token_proxy"] == 36
    assert report["total_context_tokens"] == 66
    assert report["attempts"][1]["totals"]["input_tokens"] == 10
    assert report["api_cost"] is None
    assert report["groups"][0]["observations"][0]["normalized"]["provider_usage"] == _raw()


@pytest.mark.parametrize("field", TOKEN_FIELDS)
def test_missing_counter_stays_missing(field):
    from torc.continuation_usage import account_task

    task = _task()
    del task["usage_groups"][0]["observations"][0]["usage"][field]
    result = account_task(task)
    assert result["totals"][field] is None
    assert result["known_subtotals"][field] == _raw()[field]
    if field in {"input_tokens", "cache_write_input_tokens", "output_tokens"}:
        assert result["uncached_processed_token_proxy"] is None


def test_cumulative_updates_duplicates_and_missing_final_fields():
    from torc.continuation_usage import account_task

    task = _task()
    observations = task["usage_groups"][0]["observations"]
    observations.extend([deepcopy(observations[0]),
                         {"observation_id": "final", "sequence": 2,
                          "usage": {"input_tokens": 30}, "evidence_ref": "final-ref"}])
    # Out-of-order export is sorted by explicit sequence, not list position.
    observations.reverse()
    report = account_task(task)
    assert report["totals"]["input_tokens"] == 40
    assert report["totals"]["output_tokens"] is None
    assert report["groups"][0]["duplicate_observation_count"] == 1
    assert len(report["groups"][0]["observations"]) == 3


def test_deltas_are_summed_once_and_session_total_is_an_alternative():
    from torc.continuation_usage import account_task

    task = _task()
    group = _group("session", ["r1", "r2"], "deltas")
    group["observations"].append({"observation_id": "delta-2", "sequence": 2,
                                  "usage": _raw(30), "evidence_ref": "delta-ref"})
    group["observations"].append(deepcopy(group["observations"][0]))
    task["usage_groups"] = [group]
    report = account_task(task)
    assert report["totals"]["input_tokens"] == 40
    assert report["attempts"][0]["totals"]["input_tokens"] is None
    assert report["attempts"][0]["unallocated_group_ids"] == ["session"]
    task["usage_groups"].append(_group("session-total", ["r1", "r2"]))
    with pytest.raises(ValueError, match="overlapping"):
        account_task(task)


def test_explicit_mixed_observation_modes_reject():
    from torc.continuation_usage import account_task

    task = _task()
    task["usage_groups"][0]["observations"][0]["mode"] = "deltas"
    with pytest.raises(ValueError, match="mixed"):
        account_task(task)


@pytest.mark.parametrize("change", ["uncovered", "unknown_inventory", "partial", "empty"])
def test_incomplete_usage_is_not_zero(change):
    from torc.continuation_usage import account_task

    task = _task()
    if change == "uncovered":
        task["usage_groups"].pop()
    elif change == "unknown_inventory":
        task["attempts"][0]["requests_complete"] = False
    elif change == "partial":
        task["usage_groups"][0]["complete"] = False
    else:
        task["usage_groups"][0]["observations"] = []
    report = account_task(task)
    assert all(value is None for value in report["totals"].values())
    assert report["uncached_processed_token_proxy"] is None


def test_unknown_semantics_do_not_create_proxy_or_context_total():
    from torc.continuation_usage import account_task

    task = _task()
    task["usage_groups"][0]["semantics"] = {
        "evidence_ref": None, "proxy_compatible": False, "input_cache_nonoverlap": False}
    report = account_task(task)
    assert report["totals"]["input_tokens"] == 20
    assert report["uncached_processed_token_proxy"] is None
    assert report["total_context_tokens"] is None


def test_absent_raw_usage_and_repeated_cumulative_totals_remain_honest():
    from torc.continuation_usage import account_task

    task = _task()
    group = task["usage_groups"][0]
    group["observations"].append({**deepcopy(group["observations"][0]),
                                  "observation_id": "repeated-total", "sequence": 2})
    assert account_task(task)["totals"]["input_tokens"] == 20
    group["observations"][-1]["usage"] = None
    result = account_task(task)
    assert result["totals"]["input_tokens"] is None
    assert result["groups"][0]["observations"][-1]["normalized"]["supplied"] is False


def test_unknown_cache_overlap_does_not_prevent_an_independently_valid_proxy():
    from torc.continuation_usage import account_task

    task = _task()
    task["usage_groups"][0]["semantics"]["input_cache_nonoverlap"] = False
    result = account_task(task)
    assert result["uncached_processed_token_proxy"] == 36
    assert result["total_context_tokens"] is None


def test_only_pre_context_arm_independent_setup_failure_is_excludable():
    from torc.continuation_usage import account_task

    task = _task()
    setup = deepcopy(task["attempts"][0])
    setup.update(attempt_id="setup", requests=[], context_delivered=False,
                 arm_independent_setup_failure=True, exclusion_reason="fixture setup unavailable")
    task["attempts"].insert(0, setup)
    report = account_task(task)
    assert report["attempt_count"] == 3
    assert report["excluded_attempt_count"] == 1
    assert report["totals"]["input_tokens"] == 20
    setup["context_delivered"] = True
    with pytest.raises(ValueError, match="exclusion"):
        account_task(task)


@pytest.mark.parametrize("change", ["conflict", "sequence", "decrease", "boolean", "negative",
                                   "request_id", "fallback", "mode", "evidence"])
def test_ambiguous_or_invalid_evidence_rejects(change):
    from torc.continuation_usage import account_task

    task = _task()
    group = task["usage_groups"][0]
    obs = deepcopy(group["observations"][0])
    if change in {"conflict", "sequence", "decrease"}:
        obs["usage"] = _raw(1)
        if change != "conflict":
            obs["observation_id"] = "new"
        if change == "decrease":
            obs["sequence"] = 2
        group["observations"].append(obs)
    elif change in {"boolean", "negative"}:
        group["observations"][0]["usage"]["input_tokens"] = True if change == "boolean" else -1
    elif change == "request_id":
        task["attempts"][1]["requests"][0]["request_id"] = "r1"
    elif change == "fallback":
        task["attempts"][1]["fallback_from"] = "absent"
    elif change == "mode":
        group["mode"] = "unknown"
    else:
        group["semantics"]["evidence_ref"] = None
    with pytest.raises(ValueError):
        account_task(task)

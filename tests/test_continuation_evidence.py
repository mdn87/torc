"""Reported continuation counters stay diagnostic and preserve unknowns."""

from copy import deepcopy

import pytest

from torc.canonical import payload_sha256
from torc.experiment_usage import TOKEN_FIELDS


def _usage(input_tokens, output_tokens=5):
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": 100,
        "output_tokens": output_tokens,
    }


def _response(response_id, attempt_id, total, *, baseline=None, epoch="epoch-1"):
    return {
        "response_id": response_id,
        "attempt_id": attempt_id,
        "evidence_ref": f"evidence:{response_id}",
        "counter_epoch": epoch,
        "cumulative_usage": total,
        "baseline_usage": baseline,
        "baseline_evidence_ref": None if baseline is None else f"baseline:{response_id}",
    }


def test_seed_baseline_and_fork_total_yield_reported_increment_without_mutation():
    from torc.continuation_evidence import import_responses

    records = [_response("fork", "attempt-1", _usage(19569),
                         baseline=_usage(9240))]
    before = deepcopy(records)
    report = import_responses(records, owned_attempt_ids={"attempt-1"})

    assert records == before
    assert report["input"] == records
    assert report["input_sha256"] == payload_sha256(records)
    assert report["responses"][0]["incremental_usage"]["input_tokens"] == 10329
    assert report["observed_incremental_sums"]["input_tokens"] == 10329
    assert report["responses"][0]["normalized_cumulative_usage"]["provider_usage"] == _usage(19569)
    assert report["provider_coverage_complete"] is None
    assert report["proxy_compatible"] is None
    assert report["api_cost"] is None
    assert report["savings_eligible"] is None
    assert report["whole_task_savings_available"] is False
    assert "hidden_retries" in report["whole_task_savings_unavailable_reason"]


def test_resume_uses_preceding_unique_total_without_double_counting_inherited_usage():
    from torc.continuation_evidence import import_responses

    records = [
        _response("r1", "attempt-1", _usage(150), baseline=_usage(100)),
        _response("r2", "attempt-1", _usage(190)),
        _response("r3", "attempt-1", _usage(225)),
    ]
    report = import_responses(records, owned_attempt_ids=["attempt-1"])

    assert [r["incremental_usage"]["input_tokens"] for r in report["responses"]] == [50, 40, 35]
    assert report["observed_incremental_sums"]["input_tokens"] == 125
    assert report["attempts"][0]["observed_incremental_sums"]["input_tokens"] == 125


def test_reusing_seed_baseline_on_later_response_cannot_charge_history_twice():
    from torc.continuation_evidence import import_responses

    records = [
        _response("r1", "attempt-1", _usage(150), baseline=_usage(100)),
        _response("r2", "attempt-1", _usage(190), baseline=_usage(100)),
    ]
    with pytest.raises(ValueError, match="overlap"):
        import_responses(records, owned_attempt_ids=["attempt-1"])


def test_exact_duplicates_are_retained_as_input_but_counted_once_and_conflicts_reject():
    from torc.continuation_evidence import import_responses

    record = _response("r1", "attempt-1", _usage(150), baseline=_usage(100))
    report = import_responses([record, deepcopy(record)], owned_attempt_ids={"attempt-1"})
    assert len(report["input"]) == 2
    assert len(report["responses"]) == 1
    assert report["duplicate_response_count"] == 1
    assert report["observed_incremental_sums"]["input_tokens"] == 50

    conflict = deepcopy(record)
    conflict["cumulative_usage"]["input_tokens"] = 151
    with pytest.raises(ValueError, match="conflicting repeated response ID"):
        import_responses([record, conflict], owned_attempt_ids={"attempt-1"})


def test_first_missing_baseline_and_owned_attempt_without_responses_stay_unknown():
    from torc.continuation_evidence import import_responses

    report = import_responses(
        [_response("r1", "attempt-1", _usage(150))],
        owned_attempt_ids={"attempt-1", "failed-attempt"},
    )
    assert all(report["responses"][0]["incremental_usage"][f] is None for f in TOKEN_FIELDS)
    assert all(report["observed_incremental_sums"][f] is None for f in TOKEN_FIELDS)
    assert report["missing_attempt_ids"] == ["failed-attempt"]
    failed = next(a for a in report["attempts"] if a["attempt_id"] == "failed-attempt")
    assert failed["response_count"] == 0
    assert failed["response_evidence_missing"] is True
    assert all(failed["observed_incremental_sums"][f] is None for f in TOKEN_FIELDS)


def test_missing_counter_makes_its_sum_unknown_without_erasing_other_fields():
    from torc.continuation_evidence import import_responses

    baseline = _usage(100)
    del baseline["output_tokens"]
    report = import_responses(
        [_response("r1", "attempt-1", _usage(150), baseline=baseline)],
        owned_attempt_ids={"attempt-1"},
    )
    assert report["observed_incremental_sums"]["input_tokens"] == 50
    assert report["observed_incremental_sums"]["output_tokens"] is None


def test_new_epoch_requires_explicit_baseline_and_epochs_do_not_cross_subtract():
    from torc.continuation_evidence import import_responses

    first = _response("r1", "attempt-1", _usage(150), baseline=_usage(100))
    second = _response("r2", "attempt-1", _usage(30), epoch="epoch-2")
    with pytest.raises(ValueError, match="distinct counter epoch requires explicit baseline"):
        import_responses([first, second], owned_attempt_ids={"attempt-1"})

    second["baseline_usage"] = _usage(10)
    second["baseline_evidence_ref"] = "baseline:r2"
    report = import_responses([first, second], owned_attempt_ids={"attempt-1"})
    assert [r["incremental_usage"]["input_tokens"] for r in report["responses"]] == [50, 20]
    assert report["observed_incremental_sums"]["input_tokens"] == 70


@pytest.mark.parametrize("change", ["unknown_attempt", "invalid", "decrease", "large_baseline",
                                    "missing_baseline_ref"])
def test_invalid_or_ambiguous_counter_evidence_rejects(change):
    from torc.continuation_evidence import import_responses

    first = _response("r1", "attempt-1", _usage(150), baseline=_usage(100))
    records = [first]
    if change == "unknown_attempt":
        first["attempt_id"] = "not-owned"
    elif change == "invalid":
        first["cumulative_usage"]["input_tokens"] = -1
    elif change == "decrease":
        records.append(_response("r2", "attempt-1", _usage(149)))
    elif change == "large_baseline":
        first["baseline_usage"]["input_tokens"] = 151
    else:
        first["baseline_evidence_ref"] = None

    with pytest.raises(ValueError):
        import_responses(records, owned_attempt_ids={"attempt-1"})

"""The observation collector makes a conservative, blinded public projection."""

from copy import deepcopy

import pytest

from torc.canonical import canonical_json, payload_sha256
from torc.continuation_observations import collect_observations


def _trace():
    return {
        "trial_id": "trial-1",
        "attempt_id": "attempt-1",
        "candidate_sha256": "a" * 64,
        "workspace_sha256": "b" * 64,
        "complete": True,
        "owner_receipt_ref": "owner-receipt-1",
        "process_tree_absent": True,
        "events": [
            {
                "sequence": 1,
                "action": "Get-Content secret/session-alpha/context.txt",
                "result": "arm=capsule usage=4100 and private commentary",
                "action_kind": "read",
                "result_status": "success",
                "relative_seconds": 1.0,
                "evidence_ref": "private/session-alpha/raw-output",
                "classification": "necessary_orientation",
            },
            {
                "sequence": 2,
                "action": "Get-Content secret/session-alpha/context.txt",
                "result": "the same sensitive output",
                "action_kind": "read",
                "result_status": "success",
                "relative_seconds": 2.0,
                "evidence_ref": "private/session-alpha/second-output",
            },
        ],
        "intervals": [
            {"phase": "worker_execution", "start_monotonic": 10.0,
             "end_monotonic": 14.5, "clock_id": "clock-1"},
            {"phase": "verification", "start_monotonic": 14.5,
             "end_monotonic": 16.0, "clock_id": "clock-1"},
        ],
        "interventions": [
            {"reason": "operator supplied fixture", "relative_seconds": 3.0,
             "active_seconds": 0.5},
            {"reason": "operator clarified expected behavior", "relative_seconds": 8.0,
             "active_seconds": 1.25},
        ],
        "arm": "capsule",
        "session_id": "session-alpha",
        "context": "secret context",
        "usage": {"tokens": 4100},
    }


def test_collects_blinded_public_packet_and_hash_bound_private_provenance():
    trace = _trace()
    original = deepcopy(trace)

    public, private = collect_observations(trace, opaque_id="opaque-A")

    assert trace == original
    assert public["opaque_id"] == "opaque-A"
    assert public["candidate_sha256"] == "a" * 64
    assert public["capture_complete"] is True
    assert public["process_tree_absent"] is True
    assert public["timing"] == {
        "clock_id": "one_monotonic_clock",
        "duration_seconds": 6.0,
        "intervals": [
            {"phase": "worker_execution", "duration_seconds": 4.5},
            {"phase": "verification", "duration_seconds": 1.5},
        ],
    }
    assert public["interventions"] == {"count": 2, "active_seconds": 1.75}
    assert public["investigation"] == {
        "event_count": 2,
        "assessable_event_count": 0,
        "repeated_investigation_count": 0,
        "repeated_investigation_rate": None,
        "unknown_event_count": 2,
    }
    assert public["events"] == [
        {"sequence": 1, "action_kind": "read", "result_status": "success",
         "relative_seconds": 1.0, "classification": "unassessable"},
        {"sequence": 2, "action_kind": "read", "result_status": "success",
         "relative_seconds": 2.0, "classification": "unassessable"},
    ]
    assert public["redaction"] == {
        "content_redacted": True,
        "fields_retained_privately": ["action", "evidence_ref", "result"],
    }
    public_text = canonical_json(public)
    for secret in ("capsule", "session-alpha", "secret context", "4100", "Get-Content",
                   "private commentary", "raw-output"):
        assert secret not in public_text

    assert private["packet_sha256"] == payload_sha256(public)
    assert private["trial_id"] == "trial-1"
    assert private["attempt_id"] == "attempt-1"
    assert private["owner_receipt_ref"] == "owner-receipt-1"
    assert private["capture_complete"] is True
    assert private["process_tree_absent"] is True
    assert private["workspace_sha256"] == "b" * 64
    assert private["events"] == trace["events"]
    assert private["intervals"] == trace["intervals"]
    assert private["interventions"] == trace["interventions"]


def test_incomplete_trace_keeps_repeated_rate_unknown_and_does_not_infer_reads():
    trace = _trace()
    trace["complete"] = False
    trace["events"][0].pop("classification")
    trace["events"][1]["classification"] = "repeated_settled_investigation"
    trace["events"][1]["earlier_sequence"] = 1

    public, _ = collect_observations(trace, opaque_id="opaque-B")

    assert [event["classification"] for event in public["events"]] == [
        "unassessable", "unassessable"]
    assert public["investigation"]["repeated_investigation_count"] == 0
    assert public["investigation"]["repeated_investigation_rate"] is None


def test_incomplete_empty_intervention_trace_does_not_convert_silence_to_zero_time():
    trace = _trace()
    trace["complete"] = False
    trace["interventions"] = []

    public, _ = collect_observations(trace, opaque_id="opaque-B2")

    assert public["interventions"] == {"count": 0, "active_seconds": None}


@pytest.mark.parametrize(
    ("events", "match"),
    [
        ([{"sequence": 1, "relative_seconds": 0},
          {"sequence": 1, "relative_seconds": 1}], "ordered and unique"),
        ([{"sequence": 2, "relative_seconds": 0},
          {"sequence": 1, "relative_seconds": 1}], "ordered and unique"),
        ([{"sequence": 1, "relative_seconds": -1}], "nonnegative"),
        ([{"sequence": 1, "relative_seconds": 2},
          {"sequence": 2, "relative_seconds": 1}], "monotonic"),
    ],
)
def test_rejects_bad_event_order_and_time(events, match):
    trace = _trace()
    trace["events"] = [
        {"action": "raw", "result": "raw", "evidence_ref": "raw",
         "action_kind": "other", "result_status": "unknown", **event}
        for event in events
    ]
    with pytest.raises(ValueError, match=match):
        collect_observations(trace, opaque_id="opaque-C")


@pytest.mark.parametrize(
    "interval",
    [
        {"phase": "execution", "start_monotonic": 2, "end_monotonic": 1,
         "clock_id": "clock-1"},
        {"phase": "execution", "start_monotonic": float("inf"), "end_monotonic": 2,
         "clock_id": "clock-1"},
    ],
)
def test_rejects_inverted_or_nonfinite_intervals(interval):
    trace = _trace()
    trace["intervals"] = [interval]
    with pytest.raises(ValueError, match="interval"):
        collect_observations(trace, opaque_id="opaque-D")


@pytest.mark.parametrize("clock_ids", [[None, None], ["clock-1", "clock-2"]])
def test_unknown_or_mismatched_clocks_make_durations_unknown(clock_ids):
    trace = _trace()
    for interval, clock_id in zip(trace["intervals"], clock_ids, strict=True):
        interval["clock_id"] = clock_id

    public, _ = collect_observations(trace, opaque_id="opaque-E")

    assert public["timing"]["clock_id"] is None
    assert public["timing"]["duration_seconds"] is None
    assert all(item["duration_seconds"] is None for item in public["timing"]["intervals"])


def test_intervention_active_time_is_unknown_unless_every_entry_is_explicit():
    trace = _trace()
    trace["interventions"][1].pop("active_seconds")

    public, private = collect_observations(trace, opaque_id="opaque-F")

    assert public["interventions"] == {"count": 2, "active_seconds": None}
    assert private["interventions"] == trace["interventions"]


def test_missing_owner_evidence_remains_unknown():
    trace = _trace()
    trace.pop("owner_receipt_ref")
    trace.pop("process_tree_absent")

    public, private = collect_observations(trace, opaque_id="opaque-G")

    assert public["owner_receipt_ref"] is None
    assert public["process_tree_absent"] is None
    assert private["owner_receipt_ref"] is None
    assert private["process_tree_absent"] is None


def test_rejects_digest_fields_that_could_smuggle_public_content():
    trace = _trace()
    trace["candidate_sha256"] = "arm=capsule/session=secret"

    with pytest.raises(ValueError, match="candidate_sha256"):
        collect_observations(trace, opaque_id="opaque-H")


def test_owner_paths_phase_labels_and_clock_names_remain_private():
    trace = _trace()
    trace["owner_receipt_ref"] = "native_warm/session-secret/receipt.json"
    for interval in trace["intervals"]:
        interval["phase"] = "native_warm/session-secret/context"
        interval["clock_id"] = "native_warm/session-secret"
    public, private = collect_observations(trace, opaque_id="opaque-I")
    assert "native_warm" not in canonical_json(public)
    assert "session-secret" not in canonical_json(public)
    assert private["trace"] == trace


def test_overlapping_intervals_do_not_double_count_elapsed_time():
    trace = _trace()
    trace["intervals"][1].update(start_monotonic=12, end_monotonic=16)
    public, _ = collect_observations(trace, opaque_id="opaque-J")
    assert public["timing"]["duration_seconds"] == 6

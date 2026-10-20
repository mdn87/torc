"""The first capture slice observes evidence; it never grants a retry."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from torc.canonical import payload_sha256
from torc.harness_capture.manifest import build_capture
from torc.harness_capture.parser import parse_prefix
from torc.harness_capture.reconcile import reconcile

FIXTURES = (
    Path(__file__).resolve().parents[1] / "docs/experiments/session-continuation-001/fixtures"
)
BINDINGS = {
    "lineage_id": "lineage-fixture",
    "lineage_revision_id": "revision-1",
    "accepted_checkpoint_ref": "checkpoint-1",
    "accepted_checkpoint_sha256": "a" * 64,
    "workspace_identity": {"evidence_bundle_digest": "b" * 64},
}


def capture(data=None, **kwargs):
    if data is None:
        data = (FIXTURES / "interrupted.jsonl").read_bytes()
    return build_capture(
        data, prefix_length=kwargs.pop("prefix_length", len(data)),
        session_ref="session-1", session_incarnation=kwargs.pop("session_incarnation", "inc-1"),
        observed_at="2026-10-19T12:00:00Z", bindings=BINDINGS, **kwargs,
    )


def report(manifest, evidence=None, current=None):
    return reconcile(
        manifest,
        {"base_bindings": BINDINGS, "verified_operations": evidence or []},
        current_bindings=BINDINGS if current is None else current,
    )


def test_interrupted_replay_hashes_exact_prefix_and_holds():
    data = (FIXTURES / "interrupted.jsonl").read_bytes()
    manifest = capture(data)
    assert manifest == capture(data)
    assert manifest["captured_prefix"]["raw_sha256"] == hashlib.sha256(data).hexdigest()
    operation, = manifest["tool_operations"]
    assert operation["operation_id"] == "inc-1/tool-1"
    assert operation["observation"] == "started_without_confirmed_result"
    assert operation["fingerprint"].startswith("sha256:")
    result = report(manifest)
    assert result["status"] == "held"
    assert result["hold_list"] == [operation["operation_id"]]
    assert "coverage_incomplete" in result["scope_holds"]
    assert result["base_bindings"] == BINDINGS
    assert result["retry_authorized"] is False


def test_prefix_excludes_later_operations_but_cannot_clear_empty_hold_list():
    prefix = b'{"type":"stop"}\n'
    data = prefix + (FIXTURES / "interrupted.jsonl").read_bytes()
    manifest = capture(data, prefix_length=len(prefix), transcript_status="appended")
    assert manifest["tool_operations"] == []
    assert manifest["captured_prefix"]["raw_sha256"] == hashlib.sha256(prefix).hexdigest()
    assert report(manifest)["status"] == "held"


@pytest.mark.parametrize("tail", [b'{"type":', b'{"type":"stop"}', b'\xff\n', b'[]\n'])
def test_malformed_or_unterminated_records_are_quarantined(tail):
    prefix = b'{"type":"stop"}\n'
    parsed = parse_prefix(prefix + tail, len(prefix + tail))
    assert parsed.parsed_byte_length == len(prefix)
    assert parsed.quarantined_tail_bytes == len(tail)
    assert len(parsed.records) == 1
    assert parsed.errors


@pytest.mark.parametrize("length", [-1, 999, True])
def test_invalid_prefix_lengths_reject(length):
    with pytest.raises(ValueError):
        parse_prefix(b"{}\n", length)


def test_duplicate_keys_and_nonfinite_json_are_quarantined():
    for data in [b'{"type":"stop","type":"user"}\n', b'{"value":NaN}\n',
                 b'{"value":1e999}\n']:
        assert parse_prefix(data, len(data)).parsed_byte_length == 0


def test_reported_failure_and_success_are_not_effect_verification():
    for name, expected in [("reported-failure.jsonl", "reported_failure"),
                           ("complete.jsonl", "reported_success")]:
        manifest = capture((FIXTURES / name).read_bytes())
        assert manifest["tool_operations"][0]["observation"] == expected
        assert report(manifest)["hold_list"] == ["inc-1/tool-1"]
        evidence = [{"operation_id": "inc-1/tool-1", "evidence_ref": "fixture-effect-1"}]
        verified = report(manifest, evidence)
        assert verified["operations"][0]["observation"] == "verified_effect"
        assert verified["status"] == "held"  # Effect evidence cannot fix coverage.
        assert verified["retry_authorized"] is False


def test_evidence_without_reference_or_from_other_base_cannot_verify():
    manifest = capture()
    with pytest.raises(ValueError, match="evidence_ref"):
        report(manifest, [{"operation_id": "inc-1/tool-1"}])
    result = reconcile(manifest, {"base_bindings": {}, "verified_operations": []},
                       current_bindings=BINDINGS)
    assert result["status"] == "stale"


@pytest.mark.parametrize("status", ["appended", "truncated", "rotated", "unknown"])
def test_changed_transcript_cannot_have_complete_coverage(status):
    manifest = capture(b'{"type":"stop"}\n', transcript_status=status,
                       writer_state="stopped", lifecycle_complete=True,
                       workspace_available=True, operation_coverage="fixture_complete",
                       boundary="stop")
    assert manifest["coverage"]["status"] == "incomplete"
    assert report(manifest)["status"] == "held"


def test_complete_fixture_is_observation_only_and_live_coverage_stays_unknown():
    args = dict(boundary="stop", writer_state="stopped", lifecycle_complete=True,
                workspace_available=True)
    manifest = capture(b'{"type":"stop"}\n', **args)
    assert manifest["coverage"]["status"] == "incomplete"
    complete = capture(b'{"type":"stop"}\n', operation_coverage="fixture_complete", **args)
    result = report(complete)
    assert result["status"] == "observations_complete"
    assert result["retry_authorized"] is False
    assert result["quiescence"] == "unknown"


def test_changed_binding_is_stale_and_does_not_mutate_capture():
    manifest = capture()
    before = deepcopy(manifest)
    result = report(manifest, current={**BINDINGS, "lineage_revision_id": "revision-2"})
    assert result["status"] == "stale"
    assert manifest == before


def test_identity_is_session_scoped_fingerprint_is_payload_only():
    first = capture()["tool_operations"][0]
    second = capture(session_incarnation="inc-2")["tool_operations"][0]
    assert first["operation_id"] != second["operation_id"]
    assert first["fingerprint"] == second["fingerprint"]


def test_duplicate_id_and_orphan_result_fail_closed():
    data = (FIXTURES / "interrupted.jsonl").read_bytes()
    duplicate = capture(data + data)
    assert duplicate["tool_operations"][0]["observation"] == "not_observable"
    assert "duplicate_tool_id" in duplicate["collector_errors"]
    orphan = capture(b'{"type":"user","message":{"content":'
                     b'[{"type":"tool_result","tool_use_id":"lost"}]}}\n')
    assert "orphan_tool_result" in orphan["collector_errors"]
    assert report(orphan)["status"] == "held"


def test_redacted_manifest_does_not_copy_arguments_outputs_or_unknown_text():
    secret = "SYNTHETIC_SECRET_DO_NOT_STORE"
    records = [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool-1",
         "name": "Write", "input": {"file_path": secret, "content": secret}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result",
         "tool_use_id": "tool-1", "content": secret}]}},
    ]
    data = ("\n".join(json.dumps(r) for r in records) + "\n").encode()
    manifest = capture(data)
    assert secret not in json.dumps(manifest)
    assert manifest["redacted_view"]["sha256"] != manifest["captured_prefix"]["raw_sha256"]
    assert manifest["redacted_view"]["sha256"] == payload_sha256({
        "tool_operations": manifest["tool_operations"],
        "collector_errors": manifest["collector_errors"],
    })


def test_tampered_manifest_rejected():
    manifest = capture()
    manifest["coverage"]["status"] = "complete"
    with pytest.raises(ValueError, match="digest"):
        report(manifest)


def test_unknown_event_is_coverage_gap_not_silent_success():
    manifest = capture(b'{"type":"future_tool_event"}\n')
    assert "unsupported_event" in manifest["collector_errors"]
    assert report(manifest)["status"] == "held"


@pytest.mark.parametrize("data", [b'{"type":[]}\n',
                                    b'{"type":"assistant","message":null}\n',
                                    b'{"type":"user","message":{"content":[null]}}\n'])
def test_malformed_event_shapes_stay_held(data):
    assert report(capture(data))["status"] == "held"


def test_current_file_state_and_absent_sink_receipt_cannot_release_retry():
    # Both A->B->A and a request delayed before sink acceptance can look like
    # nothing happened. The report cannot attribute history from these facts.
    manifest = capture()
    result = reconcile(manifest, {
        "base_bindings": BINDINGS, "verified_operations": [],
        "file_pre_digest": "A", "file_current_digest": "A", "sink_receipts": [],
    }, current_bindings=BINDINGS)
    assert result["status"] == "held"
    assert result["hold_list"] == ["inc-1/tool-1"]
    assert result["retry_authorized"] is False


def test_identical_payloads_with_distinct_ids_remain_distinct_observations():
    data = (FIXTURES / "interrupted.jsonl").read_bytes()
    manifest = capture(data + data.replace(b'tool-1', b'tool-2'))
    first, second = manifest["tool_operations"]
    assert first["fingerprint"] == second["fingerprint"]
    assert first["operation_id"] != second["operation_id"]
    assert report(manifest)["hold_list"] == ["inc-1/tool-1", "inc-1/tool-2"]

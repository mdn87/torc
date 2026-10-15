"""Accounting trusts the execution owner's capture, not rewritable consumer files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments/cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_consumer_smoke as smoke  # noqa: E402


def run_attempt(tmp_path, *, native=None, approval=None):
    owner = smoke.OwnerLedger()
    jobs, payloads = smoke.load_pair()
    approval = approval or smoke.load_approval()
    wrapped = owner.wrap("attempt", native or smoke.recorded_native_transport)

    def transport(prompt):
        raw, usage = wrapped(prompt)
        return raw, smoke.project_usage(usage)

    result = smoke.consume_pair(
        jobs, payloads, output_dir=tmp_path / "attempt", approval=approval,
        effective_controls=approval["controls"], batching_requested=True,
        authority_check=lambda: True, transport=transport,
    )
    return owner, jobs, approval, result


def test_link_requires_external_owner_capture(tmp_path):
    jobs, payloads = smoke.load_pair()
    approval = smoke.load_approval()
    smoke.consume_pair(jobs, payloads, output_dir=tmp_path / "attempt", approval=approval,
                       effective_controls=approval["controls"], batching_requested=True,
                       authority_check=lambda: True, transport=smoke.recorded_transport)
    with pytest.raises(smoke.adapter.CriticBatchAdapterError, match="owner usage"):
        smoke.link_smoke_to_lineage(tmp_path / "attempt", tmp_path / "state", jobs, approval)
    assert not (tmp_path / "state").exists()


def test_original_usage_and_authority_are_preserved(tmp_path):
    owner, jobs, approval, result = run_attempt(tmp_path)
    assert result["status"] == "validated"
    usage = smoke.project_usage(owner.get("attempt")["usage"])
    assert usage == {"input_tokens": 14618, "output_tokens": 639,
                     "cached_input_tokens": 10240, "cache_write_input_tokens": 0,
                     "reasoning_output_tokens": 146}
    linked = smoke.link_smoke_to_lineage(
        tmp_path / "attempt", tmp_path / "state", jobs, approval, owner=owner,
    )
    assert linked["authority_transitions_added"] == 0
    assert linked["verification"]["valid"]
    # Reads cannot mutate the owner's retained native record.
    copy = owner.get("attempt")
    copy["usage"]["input_tokens"] = 1
    assert owner.get("attempt")["usage"]["input_tokens"] == 14618


@pytest.mark.parametrize("field", ["input_tokens", "cache_write_input_tokens"])
def test_recomputed_consumer_receipt_cannot_change_owner_usage(tmp_path, field):
    owner, jobs, approval, _ = run_attempt(tmp_path)
    root = tmp_path / "attempt"
    usage = json.loads((root / "usage.json").read_text())
    usage[field] += 1
    (root / "usage.json").write_text(json.dumps(usage))
    receipt = json.loads((root / "receipt.json").read_text())
    receipt["aggregate_usage"] = usage
    (root / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(smoke.adapter.CriticBatchAdapterError, match="owner usage binding"):
        smoke.link_smoke_to_lineage(root, tmp_path / "state", jobs, approval, owner=owner)
    assert not (tmp_path / "state").exists()


def test_owner_reserves_before_transport_and_accounts_failed_calls(tmp_path):
    calls = []
    def fail(prompt):
        calls.append(prompt)
        raise RuntimeError("failed transport")
    owner, _, _, result = run_attempt(tmp_path, native=fail)
    assert result["status"] == "rejected"
    with pytest.raises(smoke.adapter.CriticBatchAdapterError, match="duplicate owner"):
        owner.wrap("attempt", fail)("retry")
    assert len(calls) == 1
    row = smoke.account_attempts(owner, tmp_path)[0]
    assert row["usage"] is None
    assert "no owner usage" in row["issues"]


def test_rejected_attempt_accounting_uses_owner_and_survives_unreadable_files(tmp_path):
    approval = {**smoke.load_approval(), "maximum_output_bytes": 1}
    owner, _, _, result = run_attempt(tmp_path, approval=approval)
    assert result["status"] == "rejected"
    (tmp_path / "attempt/usage.json").write_text("{")
    row = smoke.account_attempts(owner, tmp_path)[0]
    assert row["usage"]["input_tokens"] == 14618
    assert "attempt record unreadable" in row["issues"]


def test_unreported_usage_is_not_zero_filled(tmp_path):
    def native(prompt):
        raw, usage = smoke.recorded_native_transport(prompt)
        usage["cache_write_input_tokens"] = None
        return raw, usage
    owner, jobs, approval, result = run_attempt(tmp_path, native=native)
    assert result["status"] == "validated"
    assert "cache_write_input_tokens" not in smoke.project_usage(owner.get("attempt")["usage"])
    smoke.link_smoke_to_lineage(
        tmp_path / "attempt", tmp_path / "state", jobs, approval, owner=owner,
    )


def test_rehashed_raw_output_is_rejected_by_owner_binding(tmp_path):
    owner, jobs, approval, _ = run_attempt(tmp_path)
    root = tmp_path / "attempt"
    raw = (root / "output.json").read_text() + " "
    (root / "output.json").write_text(raw)
    disposition = json.loads((root / "disposition.json").read_text())
    disposition["raw_output_sha256"] = smoke._sha(raw)
    (root / "disposition.json").write_text(json.dumps(disposition))
    with pytest.raises(smoke.adapter.CriticBatchAdapterError, match="owner usage binding"):
        smoke.link_smoke_to_lineage(root, tmp_path / "state", jobs, approval, owner=owner)


def test_relabelled_attempt_cannot_borrow_owner_capture(tmp_path):
    owner, jobs, approval, _ = run_attempt(tmp_path)
    root = (tmp_path / "attempt").rename(tmp_path / "replacement")
    request = json.loads((root / "request.json").read_text())
    request["attempt_id"] = "replacement"
    (root / "request.json").write_text(json.dumps(request))
    disposition = json.loads((root / "disposition.json").read_text())
    disposition.update(attempt_id="replacement",
                       request_sha256=smoke._sha(smoke.canonical_json(request)))
    (root / "disposition.json").write_text(json.dumps(disposition))
    with pytest.raises(smoke.adapter.CriticBatchAdapterError, match="owner usage capture"):
        smoke.link_smoke_to_lineage(root, tmp_path / "state", jobs, approval, owner=owner)
    row = smoke.account_attempts(owner, tmp_path)[0]
    assert row["usage"]["input_tokens"] == 14618
    assert row["issues"] == ["attempt directory missing"]


def test_missing_required_owner_counter_remains_unknown(tmp_path):
    def native(prompt):
        raw, usage = smoke.recorded_native_transport(prompt)
        usage["input_tokens"] = None
        return raw, usage
    owner, _, _, result = run_attempt(tmp_path, native=native)
    assert result["status"] == "rejected"
    row = smoke.account_attempts(owner, tmp_path)[0]
    assert "input_tokens" not in row["usage"]
    assert row["issues"] == ["owner usage incomplete"]

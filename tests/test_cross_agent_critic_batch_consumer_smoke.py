from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_adapter as adapter  # noqa: E402
import critic_batch_consumer_smoke as smoke  # noqa: E402


def _run(tmp_path: Path, **changes: object) -> tuple[dict, Mock]:
    approval = smoke.load_approval()
    jobs, payloads = smoke.load_pair()
    transport = Mock(side_effect=smoke.recorded_transport)
    options = {
        "output_dir": tmp_path / "attempt", "approval": approval,
        "effective_controls": approval["controls"], "batching_requested": True,
        "authority_check": lambda: True, "transport": transport,
    }
    options.update(changes)
    return smoke.consume_pair(jobs, payloads, **options), transport


@pytest.mark.parametrize("order", ["header-first", "cutover-first"])
def test_both_orders_bind_transport_and_persist_full_evidence(tmp_path: Path, order: str) -> None:
    approval = smoke.load_approval()
    jobs, payloads = smoke.load_pair(order)
    transport = Mock(side_effect=smoke.recorded_transport)
    output_dir = tmp_path / order
    result = smoke.consume_pair(
        jobs, payloads, output_dir=output_dir, approval=approval,
        effective_controls=approval["controls"], batching_requested=True,
        authority_check=lambda: True, transport=transport,
    )
    assert result["status"] == "validated"
    transport.assert_called_once()
    prompt = transport.call_args.args[0]
    request = json.loads((output_dir / "request.json").read_text())
    response = json.loads((output_dir / "output.json").read_text())
    receipt = json.loads((output_dir / "receipt.json").read_text())
    assert (output_dir / "prompt.txt").read_text() == prompt
    assert request["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert receipt["batch_id"] == response["batch_id"] == request["envelope"]["batch_id"]
    assert [item["candidate_id"] for item in response["critiques"]] == [
        job.candidate_id for job in jobs
    ]
    assert {
        item["candidate_id"]: item["payload"] for item in request["envelope"]["candidates"]
    } == payloads
    assert receipt["aggregate_usage"]["input_tokens"] == 14618
    assert result["usage_source"] == "recorded-provider-usage"
    assert receipt["authority_changed"] is False
    statuses = {
        item["candidate_id"]: item["claim_statuses"] for item in receipt["candidate_receipts"]
    }
    # Both capsules use x1, but it is unmet only for the header candidate.
    assert statuses["header-merge-baseline-v1"]["x1"] == "unmet"
    assert statuses["cutover-plan-baseline-v1"]["x1"] == "met"
    assert all(item["result"]["findings"] for item in response["critiques"])


def test_opt_in_disabled_delegates_without_execution(tmp_path: Path) -> None:
    result, transport = _run(tmp_path, batching_requested=False)
    assert result["status"] == "direct"
    assert "batching_not_requested" in result["reason_codes"]
    transport.assert_not_called()
    assert not (tmp_path / "attempt").exists()


def test_unevaluated_harness_delegates_without_execution(tmp_path: Path) -> None:
    controls = {**smoke.load_approval()["controls"], "harness_version": "changed"}
    result, transport = _run(tmp_path, effective_controls=controls)
    assert result["reason_codes"] == ["effective_controls_outside_approval"]
    transport.assert_not_called()


def test_unapproved_policy_domain_does_not_batch(tmp_path: Path) -> None:
    jobs, payloads = smoke.load_pair()
    jobs = tuple(replace(job, policy_boundary="unevaluated") for job in jobs)
    approval = smoke.load_approval()
    transport = Mock()
    result = smoke.consume_pair(
        jobs, payloads, output_dir=tmp_path / "attempt", approval=approval,
        effective_controls=approval["controls"], batching_requested=True,
        authority_check=lambda: True, transport=transport,
    )
    assert result["reason_codes"] == ["policy_boundary_outside_approval"]
    transport.assert_not_called()


def test_payload_drift_fails_before_dispatch(tmp_path: Path) -> None:
    jobs, payloads = smoke.load_pair()
    payloads[jobs[0].candidate_id] += "changed"
    approval = smoke.load_approval()
    transport = Mock()
    with pytest.raises(adapter.CriticBatchAdapterError, match="payload hash drifted"):
        smoke.consume_pair(
            jobs, payloads, output_dir=tmp_path / "attempt", approval=approval,
            effective_controls=approval["controls"], batching_requested=True,
            authority_check=lambda: True, transport=transport,
        )
    transport.assert_not_called()
    assert not (tmp_path / "attempt").exists()


def test_changed_claim_set_is_outside_approval_before_dispatch(tmp_path: Path) -> None:
    jobs, payloads = smoke.load_pair()
    jobs = tuple(replace(job, claim_ids=(job.claim_ids[0],)) for job in jobs)
    approval = smoke.load_approval()
    transport = Mock()
    result = smoke.consume_pair(
        jobs, payloads, output_dir=tmp_path / "attempt", approval=approval,
        effective_controls=approval["controls"], batching_requested=True,
        authority_check=lambda: True, transport=transport,
    )
    assert result["reason_codes"] == ["claims_outside_approval"]
    transport.assert_not_called()


def test_revocation_immediately_before_dispatch_preserves_disposition(tmp_path: Path) -> None:
    authority = Mock(side_effect=[True, False])
    result, transport = _run(tmp_path, authority_check=authority)
    assert result["status"] == "rejected"
    assert "revoked" in result["error"]
    assert result["transport_calls"] == 0
    transport.assert_not_called()
    assert not (tmp_path / "attempt" / "receipt.json").exists()


@pytest.mark.parametrize("failure", [
    "order", "missing_claim", "cross_claim", "partial_link", "malformed",
    "batch_id", "blocking_approval", "output_budget", "duplicate_json",
])
def test_bad_responses_reject_whole_pair_and_keep_usage_without_retry(
    tmp_path: Path, failure: str,
) -> None:
    def altered(prompt: str) -> tuple[str, dict]:
        raw, usage = smoke.recorded_transport(prompt)
        value = json.loads(raw)
        item = value["critiques"][0]
        if failure == "order":
            value["critiques"].reverse()
        elif failure == "missing_claim":
            item["claim_links"].pop("c1")
        elif failure == "cross_claim":
            item["claim_links"]["c1"] = item["claim_links"]["x3"]
        elif failure == "partial_link":
            item["result"]["findings"][0]["claim_ids"].append("c1")
        elif failure == "batch_id":
            value["batch_id"] = "other-batch"
        elif failure == "blocking_approval":
            item["result"]["verdict"] = "approve"
        elif failure == "output_budget":
            return raw + " " * 32768, usage
        elif failure == "duplicate_json":
            return raw.replace('"schema_version":1', '"schema_version":2,"schema_version":1'), usage
        return ("not JSON" if failure == "malformed" else json.dumps(value)), usage

    transport = Mock(side_effect=altered)
    result, _ = _run(tmp_path, transport=transport)
    assert result["status"] == "rejected"
    assert result["transport_calls"] == 1
    transport.assert_called_once()
    output_dir = tmp_path / "attempt"
    assert (output_dir / "output.json").exists()
    assert json.loads((output_dir / "usage.json").read_text())["input_tokens"] == 14618
    assert not (output_dir / "receipt.json").exists()


def test_context_budget_delegates_before_spending_usage(tmp_path: Path) -> None:
    approval = {**smoke.load_approval(), "maximum_prompt_bytes": 1}
    result, transport = _run(tmp_path, approval=approval)
    assert result["reason_codes"] == ["prompt_budget"]
    transport.assert_not_called()


def test_transport_failure_is_recorded_without_retry(tmp_path: Path) -> None:
    transport = Mock(side_effect=RuntimeError("simulated local transport failure"))
    result, _ = _run(tmp_path, transport=transport)
    assert result["status"] == "rejected"
    assert "simulated local transport failure" in result["error"]
    transport.assert_called_once()
    assert not (tmp_path / "attempt" / "receipt.json").exists()


def test_attempt_evidence_cannot_be_overwritten(tmp_path: Path) -> None:
    first, _ = _run(tmp_path)
    assert first["status"] == "validated"
    saved = (tmp_path / "attempt" / "receipt.json").read_bytes()
    with pytest.raises(FileExistsError):
        _run(tmp_path)
    assert (tmp_path / "attempt" / "receipt.json").read_bytes() == saved


def test_approval_evidence_hash_drift_fails_closed(tmp_path: Path, monkeypatch) -> None:
    approval = smoke.load_approval()
    approval["evidence_inputs"][0]["sha256"] = "0" * 64
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(approval))
    monkeypatch.setattr(smoke, "APPROVAL_PATH", path)
    with pytest.raises(adapter.CriticBatchAdapterError, match="evidence drifted"):
        smoke.load_approval()


def test_cli_completes_consumer_and_authorized_checkpoint(tmp_path: Path, capsys) -> None:
    exit_code = smoke.main([
        "--output-dir", str(tmp_path / "attempt"), "--state-dir", str(tmp_path / "state"),
    ])
    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "validated"
    assert result["live_provider_calls"] == 0
    assert result["lineage"]["lease_holder_before"] == result["lineage"]["lease_holder_after"]
    assert result["lineage"]["authority_transitions_added"] == 0
    assert result["lineage"]["verification"]["valid"] is True
    assert len(result["lineage"]["evidence_artifact_ids"]) == 2


@pytest.mark.parametrize("artifact", ["prompt.txt", "output.json", "request.json"])
def test_tampered_attempt_is_rejected_before_lineage_creation(
    tmp_path: Path, artifact: str,
) -> None:
    result, _ = _run(tmp_path)
    assert result["status"] == "validated"
    path = tmp_path / "attempt" / artifact
    if artifact == "request.json":
        request = json.loads(path.read_text())
        request["approval_sha256"] = "0" * 64
        path.write_text(json.dumps(request))
    else:
        path.write_bytes(path.read_bytes() + b" ")
    jobs, _ = smoke.load_pair()
    with pytest.raises(adapter.CriticBatchAdapterError, match="binding drifted"):
        smoke.link_smoke_to_lineage(
            tmp_path / "attempt", tmp_path / "state", jobs, smoke.load_approval(),
        )
    assert not (tmp_path / "state").exists()

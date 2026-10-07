from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_adapter as adapter  # noqa: E402


def _job(candidate_id: str, payload: str) -> adapter.CriticJob:
    return adapter.CriticJob(
        candidate_id=candidate_id,
        payload_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        claim_ids=("c1", "x1"),
        provider="codex",
        model="gpt-6-sol",
        effort="low",
        policy_boundary="local-review",
        data_boundary="fixture-public",
    )


def _eligible() -> tuple[tuple[adapter.CriticJob, ...], dict[str, str]]:
    payloads = {"candidate-a": "payload a", "candidate-b": "payload b"}
    return tuple(_job(key, value) for key, value in payloads.items()), payloads


def _bound() -> adapter.BatchOperatingBound:
    return adapter.BatchOperatingBound(
        evaluation_id="critic-claim-link-replication-008",
        provider="codex",
        model="gpt-6-sol",
        effort="low",
    )


def _response(decision: adapter.BatchDecision) -> dict[str, object]:
    return {
        "schema_version": 1,
        "batch_id": decision.batch_id,
        "critiques": [
            {
                "candidate_id": candidate_id,
                "claim_links": {"c1": [], "x1": ["f1"]},
                "result": {
                    "schema_version": 1,
                    "verdict": "changes_requested",
                    "findings": [
                        {
                            "finding_id": "f1",
                            "severity": "blocking",
                            "summary": "Constraint is unmet.",
                            "evidence": "candidate.py:1 testable observation",
                            "claim_ids": ["x1"],
                        }
                    ],
                },
            }
            for candidate_id in decision.ordered_candidate_ids
        ],
    }


def test_eligible_pair_builds_deterministic_hash_bound_envelope() -> None:
    jobs, payloads = _eligible()

    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    repeated = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    envelope = adapter.build_envelope(decision, jobs, payloads)

    assert decision.mode == "batch"
    assert decision == repeated
    assert decision.batch_id.startswith("critic-batch-")
    assert envelope["batch_id"] == decision.batch_id
    assert [item["candidate_id"] for item in envelope["candidates"]] == [
        "candidate-a",
        "candidate-b",
    ]


def test_policy_is_opt_in_and_rejects_mixed_or_unsafe_work() -> None:
    jobs, _ = _eligible()

    assert adapter.decide_batch(
        jobs, batching_requested=False, operating_bound=_bound()
    ).reason_codes == ("batching_not_requested",)
    unsafe = (
        jobs[0],
        replace(
            jobs[1],
            provider="claude-code",
            access_mode="read_write",
            tool_mode="shell",
            dependency_ids=("candidate-a",),
        ),
    )
    decision = adapter.decide_batch(unsafe, batching_requested=True, operating_bound=_bound())

    assert decision.mode == "direct"
    assert decision.batch_id is None
    assert decision.reason_codes == (
        "mutable_work",
        "tools_enabled",
        "dependencies_present",
        "mixed_provider",
        "provider_outside_operating_bound",
    )


def test_untested_model_falls_back_even_when_jobs_match_each_other() -> None:
    jobs, _ = _eligible()
    untested = tuple(replace(job, model="future-model") for job in jobs)

    decision = adapter.decide_batch(
        untested,
        batching_requested=True,
        operating_bound=_bound(),
    )

    assert decision.mode == "direct"
    assert decision.reason_codes == ("model_outside_operating_bound",)


def test_payload_hash_drift_fails_closed() -> None:
    jobs, payloads = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    payloads["candidate-a"] = "changed"

    with pytest.raises(adapter.CriticBatchAdapterError, match="payload hash drifted"):
        adapter.build_envelope(decision, jobs, payloads)


def test_validated_receipt_keeps_usage_at_batch_level() -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())

    receipt = adapter.validate_response(
        decision,
        jobs,
        _response(decision),
        aggregate_usage={"input_tokens": 14000, "output_tokens": 600},
    )

    assert receipt["status"] == "validated"
    assert receipt["aggregate_usage"] == {"input_tokens": 14000, "output_tokens": 600}
    assert "per_candidate_usage" not in receipt
    assert receipt["authority_changed"] is False
    assert all(
        item["claim_statuses"] == {"c1": "met", "x1": "unmet"}
        for item in receipt["candidate_receipts"]
    )


def test_response_with_unlinked_finding_fails_closed() -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    response["critiques"][0]["result"]["findings"].append(
        {
            "finding_id": "f2",
            "severity": "blocking",
            "summary": "Unlinked.",
            "evidence": "candidate.py:2 observation",
            "claim_ids": ["x1"],
        }
    )

    with pytest.raises(adapter.CriticBatchAdapterError, match="unlinked finding"):
        adapter.validate_response(
            decision,
            jobs,
            response,
            aggregate_usage={"input_tokens": 1, "output_tokens": 1},
        )


def test_per_candidate_usage_is_rejected() -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())

    with pytest.raises(adapter.CriticBatchAdapterError, match="must not be manufactured"):
        adapter.validate_response(
            decision,
            jobs,
            _response(decision),
            aggregate_usage={
                "input_tokens": 1,
                "output_tokens": 1,
                "per_candidate_tokens": 1,
            },
        )

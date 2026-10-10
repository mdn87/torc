from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

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


@pytest.mark.parametrize(
    "changes",
    [
        {"payload_sha256": "0" * 64},
        {"claim_ids": ("c1",)},
        {"policy_boundary": "different-policy"},
        {"access_mode": "read_write"},
        {"dependency_ids": ("candidate-b",)},
        {"data_boundary": "different-data"},
        {"model": "unevaluated-model"},
    ],
)
def test_decision_cannot_be_reused_with_changed_jobs(changes: dict[str, object]) -> None:
    jobs, payloads = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    changed = (replace(jobs[0], **changes), jobs[1])

    with pytest.raises(adapter.CriticBatchAdapterError, match="bound batch decision"):
        adapter.build_envelope(decision, changed, payloads)
    with pytest.raises(adapter.CriticBatchAdapterError, match="bound batch decision"):
        adapter.validate_response(
            decision, changed, _response(decision),
            aggregate_usage={"input_tokens": 1, "output_tokens": 1},
        )


def test_finding_must_link_to_every_claim_it_names() -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    response["critiques"][0]["result"]["findings"][0]["claim_ids"] = ["c1", "x1"]

    with pytest.raises(adapter.CriticBatchAdapterError, match="every named claim"):
        adapter.validate_response(
            decision, jobs, response,
            aggregate_usage={"input_tokens": 1, "output_tokens": 1},
        )


@pytest.mark.parametrize("usage", [
    {"input_tokens": True, "output_tokens": 1},
    {"input_tokens": 1, "output_tokens": 1, 3: 1},
])
def test_malformed_usage_fails_with_adapter_error(usage: dict[object, object]) -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    with pytest.raises(adapter.CriticBatchAdapterError, match="provider usage"):
        adapter.validate_response(decision, jobs, _response(decision), aggregate_usage=usage)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim_ids", ["c1", "x1"]),
        ("claim_ids", "c1"),
        ("claim_ids", ()),
        ("claim_ids", ("c1", "c1")),
        ("claim_ids", (["c1"],)),
        ("claim_ids", (" c1",)),
        ("dependency_ids", ["candidate-b"]),
        ("dependency_ids", (None,)),
        ("dependency_ids", ("",)),
        ("dependency_ids", ("candidate-b ",)),
        ("dependency_ids", ("candidate-b", "candidate-b")),
        ("candidate_id", 1),
        ("provider", []),
        ("model", None),
        ("effort", True),
        ("policy_boundary", {}),
        ("data_boundary", " fixture-public"),
        ("output_contract", ""),
        ("access_mode", 1.0),
        ("tool_mode", ("none",)),
        ("payload_sha256", ["0"] * 64),
        ("payload_sha256", None),
        ("payload_sha256", "F" * 64),
    ],
)
def test_job_rejects_mutable_or_malformed_descriptors(field: str, value: Any) -> None:
    jobs, _ = _eligible()

    with pytest.raises(adapter.CriticBatchAdapterError):
        replace(jobs[0], **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evaluation_id", []),
        ("provider", True),
        ("model", None),
        ("effort", "low "),
        ("output_contract", ""),
        ("maximum_batch_size", 2.0),
        ("maximum_batch_size", True),
        ("maximum_batch_size", "2"),
        ("maximum_batch_size", []),
    ],
)
def test_operating_bound_rejects_malformed_types(field: str, value: Any) -> None:
    with pytest.raises(adapter.CriticBatchAdapterError):
        replace(_bound(), **{field: value})


def test_policy_rejects_mutable_jobs_and_non_boolean_opt_in() -> None:
    jobs, _ = _eligible()

    with pytest.raises(adapter.CriticBatchAdapterError, match="immutable tuple"):
        adapter.decide_batch(list(jobs), batching_requested=True, operating_bound=_bound())
    with pytest.raises(adapter.CriticBatchAdapterError, match="boolean"):
        adapter.decide_batch(jobs, batching_requested="true", operating_bound=_bound())


def test_decision_cannot_be_reused_with_reversed_jobs_or_changed_bound() -> None:
    jobs, payloads = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    changed_bound = replace(
        decision, operating_bound=replace(_bound(), evaluation_id="unrelated-evaluation")
    )

    with pytest.raises(adapter.CriticBatchAdapterError, match="bound batch decision"):
        adapter.build_envelope(decision, tuple(reversed(jobs)), payloads)
    with pytest.raises(adapter.CriticBatchAdapterError, match="bound batch decision"):
        adapter.build_envelope(changed_bound, jobs, payloads)


@pytest.mark.parametrize("payload", [None, [], {}, 1, "\ud800"])
def test_malformed_payload_fails_with_adapter_error(payload: Any) -> None:
    jobs, payloads = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    payloads["candidate-a"] = payload

    with pytest.raises(adapter.CriticBatchAdapterError, match="payload"):
        adapter.build_envelope(decision, jobs, payloads)


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("version", [True, 1.0, "1", None, [], {}])
def test_response_schema_versions_require_integers(nested: bool, version: Any) -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    header = response["critiques"][0]["result"] if nested else response
    header["schema_version"] = version

    with pytest.raises(adapter.CriticBatchAdapterError):
        adapter.validate_response(
            decision, jobs, response, aggregate_usage={"input_tokens": 1, "output_tokens": 1}
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("critiques",), {}),
        (("critiques", 0), []),
        (("critiques", 0, "claim_links"), []),
        (("critiques", 0, "claim_links", "x1"), {}),
        (("critiques", 0, "claim_links", "x1"), [[]]),
        (("critiques", 0, "result"), []),
        (("critiques", 0, "result", "verdict"), []),
        (("critiques", 0, "result", "verdict"), {}),
        (("critiques", 0, "result", "findings"), {}),
        (("critiques", 0, "result", "findings", 0), []),
        (("critiques", 0, "result", "findings", 0, "finding_id"), []),
        (("critiques", 0, "result", "findings", 0, "severity"), []),
        (("critiques", 0, "result", "findings", 0, "severity"), {}),
        (("critiques", 0, "result", "findings", 0, "summary"), {}),
        (("critiques", 0, "result", "findings", 0, "evidence"), "\ud800"),
        (("critiques", 0, "result", "findings", 0, "claim_ids"), [[]]),
    ],
)
def test_malformed_nested_response_fails_with_adapter_error(
    path: tuple[str | int, ...], value: Any
) -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    container = response
    for component in path[:-1]:
        container = container[component]
    container[path[-1]] = value

    with pytest.raises(adapter.CriticBatchAdapterError):
        adapter.validate_response(
            decision, jobs, response, aggregate_usage={"input_tokens": 1, "output_tokens": 1}
        )


def test_approval_cannot_contradict_a_blocking_finding() -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    response["critiques"][0]["result"]["verdict"] = "approve"

    with pytest.raises(adapter.CriticBatchAdapterError, match="blocking finding"):
        adapter.validate_response(
            decision, jobs, response, aggregate_usage={"input_tokens": 1, "output_tokens": 1}
        )


def test_changes_requested_requires_a_finding() -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    response["critiques"][0]["result"]["findings"] = []
    response["critiques"][0]["claim_links"]["x1"] = []

    with pytest.raises(adapter.CriticBatchAdapterError, match="at least one finding"):
        adapter.validate_response(
            decision, jobs, response, aggregate_usage={"input_tokens": 1, "output_tokens": 1}
        )


@pytest.mark.parametrize("keep_non_blocking", [False, True])
def test_approval_preserves_supported_non_blocking_semantics(keep_non_blocking: bool) -> None:
    jobs, _ = _eligible()
    decision = adapter.decide_batch(jobs, batching_requested=True, operating_bound=_bound())
    response = _response(decision)
    result = response["critiques"][0]["result"]
    result["verdict"] = "approve"
    if keep_non_blocking:
        result["findings"][0]["severity"] = "non_blocking"
    else:
        result["findings"] = []
        response["critiques"][0]["claim_links"]["x1"] = []

    receipt = adapter.validate_response(
        decision, jobs, response, aggregate_usage={"input_tokens": 1, "output_tokens": 1}
    )

    assert receipt["candidate_receipts"][0]["verdict"] == "approve"
    assert receipt["candidate_receipts"][0]["finding_count"] == int(keep_non_blocking)
    assert receipt["candidate_receipts"][0]["claim_statuses"]["x1"] == (
        "unmet" if keep_non_blocking else "met"
    )

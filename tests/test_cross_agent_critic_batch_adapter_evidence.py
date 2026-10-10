from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
RUNS = EXPERIMENT / "runs" / "critic-claim-link-replication-008"
SOURCE_PLAN = EXPERIMENT / "critic-claim-link-generalization-006-plan.json"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_adapter as adapter  # noqa: E402


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize("run_id", ["01-header-first", "02-cutover-first"])
def test_reference_adapter_validates_recorded_replication_evidence(run_id: str) -> None:
    run_root = RUNS / run_id
    probe = _object(run_root / "probe-plan.json")
    output = _object(run_root / "output.json")
    worker = _object(run_root / "phase" / "worker-run.json")
    source_plan = _object(SOURCE_PLAN)
    expected_by_candidate = {
        item["candidate_id"]: item["expected_claim_statuses"] for item in source_plan["candidates"]
    }
    candidate_by_id = {item["candidate_id"]: item for item in probe["candidates"]}
    jobs = tuple(
        adapter.CriticJob(
            candidate_id=candidate_id,
            payload_sha256=candidate_by_id[candidate_id]["payload_sha256"],
            claim_ids=tuple(probe["reviewable_claim_ids"][candidate_id]),
            provider="codex",
            model="gpt-6-sol",
            effort="low",
            policy_boundary="local-tool-free-review",
            data_boundary="synthetic-fixtures",
        )
        for candidate_id in probe["candidate_order"]
    )
    bound = adapter.BatchOperatingBound(
        evaluation_id="critic-claim-link-replication-008",
        provider="codex",
        model="gpt-6-sol",
        effort="low",
    )
    decision = adapter.decide_batch(
        jobs,
        batching_requested=True,
        operating_bound=bound,
    )
    response = {
        "schema_version": 1,
        "batch_id": decision.batch_id,
        "critiques": output["critiques"],
    }
    usage = {
        key: value
        for key, value in worker["usage"].items()
        if key
        in {
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "reasoning_output_tokens",
            "output_tokens",
        }
        and isinstance(value, int)
    }

    receipt = adapter.validate_response(
        decision,
        jobs,
        response,
        aggregate_usage=usage,
    )

    assert receipt["status"] == "validated"
    assert receipt["ordered_candidate_ids"] == probe["candidate_order"]
    assert receipt["aggregate_usage"]["input_tokens"] == 14618
    assert receipt["authority_changed"] is False
    assert {
        item["candidate_id"]: item["claim_statuses"] for item in receipt["candidate_receipts"]
    } == {
        candidate_id: expected_by_candidate[candidate_id]
        for candidate_id in probe["candidate_order"]
    }

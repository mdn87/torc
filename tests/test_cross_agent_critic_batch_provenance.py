from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from torc.canonical import record_hash_is_valid
from torc.errors import IntegrityError, InvalidInputError, LeaseConflictError
from torc.store import Store
from torc.verify import verify_store

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_adapter as adapter  # noqa: E402
import critic_batch_provenance as provenance  # noqa: E402
from critic_batch_provenance import link_batch_evidence  # noqa: E402


def _lineage(store: Store) -> dict[str, Any]:
    store.register_substrate(
        {
            "schema_version": 1,
            "substrate_id": "synthetic-review",
            "label": "Local model-free provenance smoke",
            "adapter": "synthetic",
            "capabilities": ["repository_read"],
            "policy_labels": ["local-synthetic"],
            "context_budget": {"unit": "words", "limit": 300},
            "task_affinities": ["review"],
        }
    )
    root = store.create_lineage(
        "batch-lineage",
        {
            "identity": {"label": "Batch provenance smoke"},
            "self_model": {"role": "Preserve review evidence"},
            "goals": ["Keep attributable evidence"],
            "commitments": ["Preserve authority"],
            "constraints": ["Local deterministic execution only"],
            "open_work": ["Evaluate the external review"],
            "uncertainties": ["Findings require independent confirmation"],
            "artifact_refs": ["prior-artifact"],
            "memory_refs": [],
        },
        revision_id="batch-root",
        created_at="2026-10-07T12:00:00Z",
    )
    for activation_id in ("activation-owner", "activation-observer"):
        store.create_activation(
            "batch-lineage",
            root["revision_id"],
            "synthetic-review",
            activation_id=activation_id,
            started_at="2026-10-07T12:01:00Z",
        )
    store.acquire_lease(
        "batch-lineage",
        "activation-owner",
        lease_id="lease-owner",
        issued_at="2026-10-07T12:02:00Z",
    )
    return root


def _evidence() -> dict[str, Any]:
    jobs = tuple(
        adapter.CriticJob(
            candidate_id=candidate_id,
            payload_sha256=hashlib.sha256(candidate_id.encode()).hexdigest(),
            claim_ids=("c1", "x1"),
            provider="synthetic",
            model="synthetic-review",
            effort="deterministic",
            policy_boundary="local-only",
            data_boundary="synthetic-public",
        )
        for candidate_id in ("candidate-a", "candidate-b")
    )
    decision = adapter.decide_batch(
        jobs,
        batching_requested=True,
        operating_bound=adapter.BatchOperatingBound(
            evaluation_id="model-free-smoke",
            provider="synthetic",
            model="synthetic-review",
            effort="deterministic",
        ),
    )
    response = {
        "schema_version": 1,
        "batch_id": decision.batch_id,
        "critiques": [
            {
                "candidate_id": job.candidate_id,
                "claim_links": {"c1": [], "x1": ["f1"]},
                "result": {
                    "schema_version": 1,
                    "verdict": "changes_requested",
                    "findings": [
                        {
                            "finding_id": "f1",
                            "severity": "blocking",
                            "summary": f"Synthetic constraint failure for {job.candidate_id}",
                            "evidence": f"{job.candidate_id}.py:1 synthetic observation",
                            "claim_ids": ["x1"],
                        }
                    ],
                },
            }
            for job in jobs
        ],
    }
    receipt = adapter.validate_response(
        decision, jobs, response, aggregate_usage={"input_tokens": 40, "output_tokens": 20}
    )
    return {"decision": decision, "jobs": jobs, "receipt": receipt, "response": response}


def _link(store: Store, **changes: Any) -> dict[str, Any]:
    arguments = {
        "lineage_id": "batch-lineage",
        "activation_id": "activation-owner",
        "revision_id": "batch-checkpoint",
        "created_at": "2026-10-07T12:03:00Z",
    } | _evidence() | changes
    return link_batch_evidence(store, **arguments)


def _transitions(store: Store) -> list[dict[str, Any]]:
    return [dict(row) for row in store.connection.execute("SELECT * FROM authority_transitions")]


def test_batch_evidence_checkpoint_retains_authority_and_canonical_parent(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        root = _lineage(store)
        root_before = deepcopy(root)
        before = store.current_authority("batch-lineage")
        transitions = _transitions(store)

        result = _link(store)

        checkpoint = result["checkpoint"]
        after = store.current_authority("batch-lineage")
        assert checkpoint["event_type"] == "checkpoint"
        assert checkpoint["parent_revision_ids"] == [root["revision_id"]]
        assert checkpoint["integrity"]["previous_revision_sha256"] == root["integrity"][
            "canonical_payload_sha256"
        ]
        assert store.get_revision(root["revision_id"]) == root_before
        assert record_hash_is_valid(checkpoint)
        assert after == before | {"lineage_head_revision_id": checkpoint["revision_id"]}
        assert _transitions(store) == transitions
        assert store.get_activation("activation-observer")["state"] == "pending"
        assert store.connection.execute("SELECT COUNT(*) FROM leases").fetchone()[0] == 1
        assert store.connection.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM handoff_results").fetchone()[0] == 0
        assert verify_store(store, "batch-lineage")["valid"] is True

        artifact_ids = [item["artifact_id"] for item in result["artifacts"]]
        assert checkpoint["evidence_refs"] == artifact_ids
        assert checkpoint["canonical_state"] == root_before["canonical_state"] | {
            "artifact_refs": ["prior-artifact", *artifact_ids]
        }


def test_full_response_and_aggregate_receipt_survive_store_reopen(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _lineage(store)
        result = _link(store)

    with Store(tmp_path, read_only=True) as reopened:
        artifacts = result["artifacts"]
        documents = [
            json.loads((reopened.state_dir / item["relative_path"]).read_text(encoding="utf-8"))
            for item in artifacts
        ]
        assert all(record_hash_is_valid(document) for document in documents)
        assert all(document["source_revision_id"] == "batch-root" for document in documents)
        assert all(document["activation_id"] == "activation-owner" for document in documents)
        expected = _evidence()
        assert documents[0]["evidence"] == expected["receipt"]
        assert documents[1]["evidence"] == expected["response"]
        assert documents[0]["evidence"]["aggregate_usage"] == {
            "input_tokens": 40,
            "output_tokens": 20,
        }
        assert "per_candidate_usage" not in documents[0]["evidence"]
        assert "findings" in documents[1]["evidence"]["critiques"][0]["result"]
        assert verify_store(reopened, "batch-lineage")["artifacts_checked"] == 2
        assert verify_store(reopened, "batch-lineage")["valid"] is True


def test_unauthorized_activation_cannot_link_batch_evidence(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        root = _lineage(store)
        authority = store.current_authority("batch-lineage")
        with pytest.raises(LeaseConflictError, match="authoritative lease"):
            _link(store, activation_id="activation-observer")
        assert store.current_authority("batch-lineage") == authority
        assert store.lineage_revisions("batch-lineage") == [root]
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0
        assert not (tmp_path / "artifacts").exists()


def test_execution_context_is_sealed_separately_from_receipt_and_canonical_state(
    tmp_path: Path,
) -> None:
    context = {
        "execution_mode": "model-free-recorded-replay",
        "usage_source": "recorded-provider-usage",
        "attempt_id": "replay-attempt-1",
        "request_sha256": "a" * 64,
        "prompt_sha256": "b" * 64,
        "raw_output_sha256": "c" * 64,
    }
    original_context = deepcopy(context)
    with Store(tmp_path) as store:
        _lineage(store)
        result = _link(store, evidence_context=context)
        context["usage_source"] = "changed-after-export"

    with Store(tmp_path, read_only=True) as reopened:
        for artifact in result["artifacts"]:
            document = json.loads(
                (tmp_path / artifact["relative_path"]).read_text(encoding="utf-8")
            )
            assert document["evidence_context"] == original_context
            assert "evidence_context" not in document["evidence"]
            assert record_hash_is_valid(document)
            if artifact["record_kind"] == "critic-batch-receipt":
                assert document["evidence"] == _evidence()["receipt"]
        state = reopened.get_revision("batch-checkpoint")["canonical_state"]
        assert "evidence_context" not in state
        assert "execution_mode" not in state
        assert verify_store(reopened, "batch-lineage")["valid"] is True


@pytest.mark.parametrize("artifact_index", [0, 1], ids=["receipt", "full-response"])
def test_tampered_exported_batch_evidence_fails_verification(
    tmp_path: Path, artifact_index: int
) -> None:
    with Store(tmp_path) as store:
        _lineage(store)
        result = _link(store)
        authority = store.current_authority("batch-lineage")
        checkpoint = store.get_revision("batch-checkpoint")
        artifact = result["artifacts"][artifact_index]
        path = tmp_path / artifact["relative_path"]
        path.write_text('{"tampered":true}\n', encoding="utf-8")

        verification = verify_store(store, "batch-lineage")

        assert verification["valid"] is False
        assert any(
            error["code"] == "artifact_hash_mismatch"
            and error["record_id"] == artifact["artifact_id"]
            for error in verification["errors"]
        )
        with pytest.raises(IntegrityError, match="artifact_hash_mismatch"):
            _link(store, revision_id="second-checkpoint")
        assert store.current_authority("batch-lineage") == authority
        assert store.get_revision("batch-checkpoint") == checkpoint
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 2


def test_receipt_cannot_claim_authority_or_different_findings(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        root = _lineage(store)
        evidence = _evidence()
        receipt = evidence["receipt"] | {"authority_changed": True}
        with pytest.raises(InvalidInputError, match="does not match"):
            _link(store, receipt=receipt)
        changed_response = deepcopy(evidence["response"])
        changed_response["critiques"][0]["result"]["findings"][0]["evidence"] = "changed"
        with pytest.raises(InvalidInputError, match="does not match"):
            _link(store, response=changed_response)
        assert store.lineage_revisions("batch-lineage") == [root]
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_changed_head_cannot_be_overwritten_with_stale_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Store(tmp_path) as store:
        root = _lineage(store)
        register = provenance.artifact_metadata

        def advance_between_export_and_append(*args: Any, **kwargs: Any) -> dict[str, Any]:
            metadata = register(*args, **kwargs)
            if metadata["record_kind"] == "critic-batch-response":
                store.append_revision(
                    "batch-lineage",
                    root["canonical_state"] | {"open_work": ["New canonical task"]},
                    event_type="checkpoint",
                    activation_id="activation-owner",
                    revision_id="concurrent-checkpoint",
                    created_at="2026-10-07T12:03:00Z",
                )
            return metadata

        monkeypatch.setattr(provenance, "artifact_metadata", advance_between_export_and_append)
        with pytest.raises(LeaseConflictError, match="head or authority changed"):
            _link(store)
        assert store.current_authority("batch-lineage")["lineage_head_revision_id"] == (
            "concurrent-checkpoint"
        )
        assert store.get_revision("concurrent-checkpoint")["canonical_state"]["open_work"] == [
            "New canonical task"
        ]
        assert len(store.lineage_revisions("batch-lineage")) == 2
        assert verify_store(store, "batch-lineage")["valid"] is True

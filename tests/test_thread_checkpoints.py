from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from torc.errors import CheckpointConflictError, ThreadCheckpointError
from torc.store import _MIGRATION_1, Store
from torc.thread_checkpoints import (
    accepted_thread_checkpoint,
    get_thread_binding,
    link_thread_to_lineage,
    record_checkpoint_decision,
)
from torc.verify import verify_store

THREAD_ID = "plir:thread:01JTESTTHREAD00000000000000"
LINEAGE_ID = "lineage-lode"
ACTIVATION_ID = "activation-lode"
CHECKPOINT_ONE = "ogmi:checkpoint:lode-one"
CHECKPOINT_TWO = "ogmi:checkpoint:lode-two"


def _canonical_state() -> dict:
    return {
        "identity": {"label": "Lode thread authority"},
        "self_model": {"role": "govern checkpoint acceptance"},
        "goals": ["preserve authority"],
        "commitments": ["accept checkpoints explicitly"],
        "constraints": ["LIR cannot accept its own checkpoint"],
        "open_work": [],
        "uncertainties": [],
        "artifact_refs": [],
        "memory_refs": [],
    }


def _bootstrap(state_dir: Path) -> None:
    with Store(state_dir) as store:
        store.register_substrate(
            {
                "schema_version": 1,
                "substrate_id": "substrate-lode",
                "label": "Lode authority",
                "adapter": "local",
                "capabilities": ["repository_read", "repository_write"],
                "policy_labels": ["local-workspace"],
                "context_budget": {"unit": "words", "limit": 1000},
                "task_affinities": ["implementation"],
            }
        )
        revision = store.create_lineage(
            LINEAGE_ID,
            _canonical_state(),
            revision_id="revision-lode-one",
            created_at="2026-09-02T12:00:00Z",
        )
        store.create_activation(
            LINEAGE_ID,
            revision["revision_id"],
            "substrate-lode",
            activation_id=ACTIVATION_ID,
            started_at="2026-09-02T12:01:00Z",
        )
        store.acquire_lease(
            LINEAGE_ID,
            ACTIVATION_ID,
            lease_id="lease-lode",
            issued_at="2026-09-02T12:02:00Z",
        )
        link_thread_to_lineage(
            store,
            thread_id=THREAD_ID,
            lineage_id=LINEAGE_ID,
            activation_id=ACTIVATION_ID,
            expected_lineage_head_revision_id=revision["revision_id"],
            evidence_refs=["ogmi:manifest:lode"],
            link_id="thread-link-lode",
            linked_at="2026-09-02T12:03:00Z",
        )


def _accept(
    store: Store,
    checkpoint_ref: str,
    *,
    expected: str | None,
    decision_id: str,
    decided_at: str,
) -> dict:
    return record_checkpoint_decision(
        store,
        thread_id=THREAD_ID,
        checkpoint_ref=checkpoint_ref,
        checkpoint_sha256=("a" if checkpoint_ref == CHECKPOINT_ONE else "b") * 64,
        disposition="accepted",
        activation_id=ACTIVATION_ID,
        expected_accepted_checkpoint_ref=expected,
        policy_version="lir-protocol-v0",
        reason_codes=["tests_passed", "authority_current"],
        evidence_refs=["evidence:test-suite"],
        decision_id=decision_id,
        decided_at=decided_at,
    )


def test_link_and_accepted_decisions_advance_one_torc_owned_head(tmp_path: Path) -> None:
    _bootstrap(tmp_path)

    with Store(tmp_path) as store:
        first = _accept(
            store,
            CHECKPOINT_ONE,
            expected=None,
            decision_id="checkpoint-decision-one",
            decided_at="2026-09-02T12:04:00Z",
        )
        second = _accept(
            store,
            CHECKPOINT_TWO,
            expected=CHECKPOINT_ONE,
            decision_id="checkpoint-decision-two",
            decided_at="2026-09-02T12:05:00Z",
        )

        binding = get_thread_binding(store, THREAD_ID)
        accepted = accepted_thread_checkpoint(store, THREAD_ID)

        assert binding["relationship"] == "thread_carried_by_lineage"
        assert binding["lineage_id"] == LINEAGE_ID
        assert first["authority"]["lease_id"] == "lease-lode"
        assert accepted == second
        assert accepted["checkpoint_ref"] == CHECKPOINT_TWO
        assert verify_store(store, LINEAGE_ID)["valid"] is True


def test_stale_expected_head_fails_without_appending_a_decision(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    with Store(tmp_path) as store:
        _accept(
            store,
            CHECKPOINT_ONE,
            expected=None,
            decision_id="checkpoint-decision-one",
            decided_at="2026-09-02T12:04:00Z",
        )

        with pytest.raises(CheckpointConflictError, match="accepted checkpoint head"):
            _accept(
                store,
                CHECKPOINT_TWO,
                expected=None,
                decision_id="checkpoint-decision-stale",
                decided_at="2026-09-02T12:05:00Z",
            )

        count = store.connection.execute(
            "SELECT COUNT(*) FROM thread_checkpoint_decisions"
        ).fetchone()[0]
        assert count == 1
        assert accepted_thread_checkpoint(store, THREAD_ID)["checkpoint_ref"] == CHECKPOINT_ONE


def test_non_authoritative_activation_cannot_accept_checkpoint(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    with Store(tmp_path) as store:
        store.create_activation(
            LINEAGE_ID,
            "revision-lode-one",
            "substrate-lode",
            activation_id="activation-observer",
        )

        with pytest.raises(ThreadCheckpointError, match="active lineage authority"):
            record_checkpoint_decision(
                store,
                thread_id=THREAD_ID,
                checkpoint_ref=CHECKPOINT_ONE,
                checkpoint_sha256="a" * 64,
                disposition="accepted",
                activation_id="activation-observer",
                expected_accepted_checkpoint_ref=None,
                policy_version="lir-protocol-v0",
                reason_codes=["looks_good"],
                evidence_refs=["evidence:review"],
            )

        assert accepted_thread_checkpoint(store, THREAD_ID) is None


def test_rejected_decision_is_immutable_and_does_not_advance_head(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    with Store(tmp_path) as store:
        rejected = record_checkpoint_decision(
            store,
            thread_id=THREAD_ID,
            checkpoint_ref=CHECKPOINT_ONE,
            checkpoint_sha256="a" * 64,
            disposition="rejected",
            activation_id=ACTIVATION_ID,
            expected_accepted_checkpoint_ref=None,
            policy_version="lir-protocol-v0",
            reason_codes=["verification_failed"],
            evidence_refs=["evidence:test-failure"],
            decision_id="checkpoint-decision-rejected",
            decided_at="2026-09-02T12:04:00Z",
        )

        assert rejected["disposition"] == "rejected"
        assert accepted_thread_checkpoint(store, THREAD_ID) is None
        with pytest.raises(sqlite3.IntegrityError, match="immutable checkpoint decisions"):
            store.connection.execute(
                "UPDATE thread_checkpoint_decisions SET disposition = 'accepted'"
            )


def test_decision_id_replay_is_idempotent_but_cannot_change_content(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    with Store(tmp_path) as store:
        original = _accept(
            store,
            CHECKPOINT_ONE,
            expected=None,
            decision_id="checkpoint-decision-one",
            decided_at="2026-09-02T12:04:00Z",
        )
        replay = _accept(
            store,
            CHECKPOINT_ONE,
            expected=None,
            decision_id="checkpoint-decision-one",
            decided_at="2026-09-02T12:04:00Z",
        )
        assert replay == original

        with pytest.raises(ThreadCheckpointError, match="different content"):
            _accept(
                store,
                CHECKPOINT_TWO,
                expected=CHECKPOINT_ONE,
                decision_id="checkpoint-decision-one",
                decided_at="2026-09-02T12:05:00Z",
            )


def test_two_checkpoint_acceptances_from_same_head_have_one_winner(tmp_path: Path) -> None:
    _bootstrap(tmp_path)

    def attempt(index: int) -> str:
        try:
            with Store(tmp_path) as store:
                _accept(
                    store,
                    CHECKPOINT_ONE if index == 1 else CHECKPOINT_TWO,
                    expected=None,
                    decision_id=f"checkpoint-decision-concurrent-{index}",
                    decided_at=f"2026-09-02T12:04:0{index}Z",
                )
            return "accepted"
        except CheckpointConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (1, 2)))

    assert sorted(results) == ["accepted", "conflict"]
    with Store(tmp_path) as store:
        assert store.connection.execute(
            "SELECT COUNT(*) FROM thread_checkpoint_decisions"
        ).fetchone()[0] == 1


def test_thread_binding_cannot_be_silently_reassigned(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    with Store(tmp_path) as store:
        store.register_substrate(
            {
                "schema_version": 1,
                "substrate_id": "substrate-other",
                "label": "Other",
                "adapter": "local",
                "capabilities": [],
                "policy_labels": [],
                "context_budget": {"unit": "words", "limit": 100},
                "task_affinities": [],
            }
        )
        revision = store.create_lineage("lineage-other", _canonical_state())
        store.create_activation(
            "lineage-other",
            revision["revision_id"],
            "substrate-other",
            activation_id="activation-other",
        )
        store.acquire_lease("lineage-other", "activation-other")

        with pytest.raises(ThreadCheckpointError, match="already has a primary lineage"):
            link_thread_to_lineage(
                store,
                thread_id=THREAD_ID,
                lineage_id="lineage-other",
                activation_id="activation-other",
                expected_lineage_head_revision_id=revision["revision_id"],
                evidence_refs=["evidence:other"],
            )


def test_verifier_detects_checkpoint_decision_tampering(tmp_path: Path) -> None:
    _bootstrap(tmp_path)
    with Store(tmp_path) as store:
        decision = _accept(
            store,
            CHECKPOINT_ONE,
            expected=None,
            decision_id="checkpoint-decision-one",
            decided_at="2026-09-02T12:04:00Z",
        )
        tampered = dict(decision)
        tampered["reason_codes"] = ["forged"]
        store.connection.execute("DROP TRIGGER thread_checkpoint_decisions_no_update")
        store.connection.execute(
            "UPDATE thread_checkpoint_decisions SET payload_json = ? WHERE decision_id = ?",
            (json.dumps(tampered), decision["decision_id"]),
        )
        store.connection.commit()

        result = verify_store(store, LINEAGE_ID)

        assert result["valid"] is False
        assert any(
            error["code"] == "thread_checkpoint_decision_hash_mismatch"
            for error in result["errors"]
        )


def test_schema_one_database_upgrades_to_thread_authority_schema(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(tmp_path / "torc.sqlite3")
    connection.executescript(_MIGRATION_1)
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    with Store(tmp_path) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        tables = {
            row["name"]
            for row in store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "thread_lineage_bindings",
        "thread_checkpoint_decisions",
        "thread_accepted_heads",
    }.issubset(tables)

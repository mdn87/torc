from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from torc.canonical import canonical_json, seal_record
from torc.cli import main
from torc.errors import IntegrityError, LeaseConflictError, RollbackError
from torc.operator import (
    checkpoint_operator_lineage,
    create_operator_lineage,
    prepare_operator_handoff,
    resolve_operator_handoff,
    rollback_operator_lineage,
)
from torc.rollbacks import apply_rollback
from torc.store import Store
from torc.verify import verify_store

ROOT = Path(__file__).resolve().parents[1]


def _state(label: str) -> dict[str, Any]:
    return {
        "identity": {"label": "Rollback test lineage"},
        "self_model": {
            "role": label,
            "settled_decisions": [f"settled-{label}"],
            "methods": ["append-only restoration"],
        },
        "goals": [f"goal-{label}"],
        "commitments": ["preserve history"],
        "constraints": ["do not move the head backward"],
        "open_work": [f"work-{label}"],
        "uncertainties": [],
        "artifact_refs": [],
        "memory_refs": [],
    }


def _substrate() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": "rollback-substrate",
        "label": "Rollback operator substrate",
        "adapter": "manual",
        "capabilities": ["repository_read", "repository_write"],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": ["implementation"],
    }


def _handoff_plan() -> dict[str, Any]:
    target = _substrate()
    target.update(
        {
            "substrate_id": "rollback-target-substrate",
            "label": "Rollback stale handoff target",
            "task_affinities": ["review"],
        }
    )
    return {
        "target_substrate": target,
        "target_activation_id": "activation-stale-target",
        "task_phase": "independent-review",
        "requirements": {
            "capabilities": ["repository_read", "repository_write"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 500,
        },
        "budget_limit": 1000,
        "target_responsibility": "Review the pre-rollback canonical state",
        "reason_code": "task_phase_transition",
        "rationale": "Prepare a handoff before rollback.",
    }


def _bootstrap(store: Store) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    created = create_operator_lineage(
        store,
        lineage_id="rollback-lineage",
        canonical_state=_state("one"),
        substrate=_substrate(),
        activation_id="activation-rollback",
    )
    second = checkpoint_operator_lineage(
        store,
        lineage_id="rollback-lineage",
        activation_id=created["activation_id"],
        canonical_state=_state("two"),
        evidence_refs=["checkpoint-two"],
    )
    third = checkpoint_operator_lineage(
        store,
        lineage_id="rollback-lineage",
        activation_id=created["activation_id"],
        canonical_state=_state("three"),
        evidence_refs=["checkpoint-three"],
    )
    return created, second, third


def _rollback(
    store: Store,
    created: dict[str, Any],
    third: dict[str, Any],
) -> dict[str, Any]:
    return rollback_operator_lineage(
        store,
        lineage_id="rollback-lineage",
        activation_id=created["activation_id"],
        expected_head_revision_id=third["revision_id"],
        target_revision_id=created["revision_id"],
        operator_ref="operator-rollback-decision",
        rationale="The latest canonical direction was invalid.",
        evidence_refs=["review-finding-rollback"],
    )


def _cli_json(capsys, *args: str) -> dict[str, Any]:
    assert main(list(args)) == 0
    return json.loads(capsys.readouterr().out)


def test_rollback_appends_exact_state_and_preserves_authority(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        original_rows = {
            row["revision_id"]: row["payload_json"]
            for row in store.connection.execute(
                "SELECT revision_id, payload_json FROM revisions ORDER BY rowid"
            )
        }
        authority_before = store.current_authority("rollback-lineage")
        transitions_before = store.connection.execute(
            "SELECT COUNT(*) FROM authority_transitions WHERE lineage_id = ?",
            ("rollback-lineage",),
        ).fetchone()[0]

        result = _rollback(store, created, third)
        rollback = store.get_revision(result["revision_id"])
        authority_after = store.current_authority("rollback-lineage")

        assert rollback["event_type"] == "rollback_applied"
        assert rollback["parent_revision_ids"] == [third["revision_id"]]
        assert rollback["canonical_state"] == store.get_revision(created["revision_id"])[
            "canonical_state"
        ]
        assert rollback["rollback_context"]["target_revision_id"] == created[
            "revision_id"
        ]
        assert authority_after["activation_id"] == authority_before["activation_id"]
        assert authority_after["lease_id"] == authority_before["lease_id"]
        assert authority_after["lineage_head_revision_id"] == rollback["revision_id"]
        assert result["authority_transferred"] is False
        assert result["authority_transition_added"] is False
        assert store.connection.execute(
            "SELECT COUNT(*) FROM authority_transitions WHERE lineage_id = ?",
            ("rollback-lineage",),
        ).fetchone()[0] == transitions_before
        for revision_id, payload in original_rows.items():
            assert store.connection.execute(
                "SELECT payload_json FROM revisions WHERE revision_id = ?", (revision_id,)
            ).fetchone()["payload_json"] == payload
        schema = json.loads(
            (ROOT / "schemas" / "lineage-revision.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(rollback)
        assert result["verification"]["valid"] is True


def test_checkpoint_can_continue_after_rollback(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        rolled_back = _rollback(store, created, third)

        checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="rollback-lineage",
            activation_id=created["activation_id"],
            canonical_state=_state("after-rollback"),
        )

        assert store.get_revision(checkpoint["revision_id"])["parent_revision_ids"] == [
            rolled_back["revision_id"]
        ]
        assert verify_store(store, "rollback-lineage")["valid"] is True


def test_rollback_makes_prepared_handoff_stale(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="rollback-lineage",
            source_activation_id=created["activation_id"],
            plan=_handoff_plan(),
        )
        reconstruction = json.loads(
            (store.state_dir / prepared["reconstruction_template_path"]).read_text(
                encoding="utf-8"
            )
        )
        _rollback(store, created, third)

        with pytest.raises(LeaseConflictError, match="changed after handoff preparation"):
            resolve_operator_handoff(
                store,
                handoff_id=prepared["handoff_id"],
                target_activation_id=prepared["target_activation_id"],
                reconstruction=reconstruction,
            )

        assert store.list_hashed_records("handoff_results", "rollback-lineage") == []
        assert verify_store(store, "rollback-lineage")["valid"] is True


def test_stale_expected_head_fails_without_appending(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, second, third = _bootstrap(store)
        before = len(store.lineage_revisions("rollback-lineage"))

        with pytest.raises(LeaseConflictError, match="expected head"):
            rollback_operator_lineage(
                store,
                lineage_id="rollback-lineage",
                activation_id=created["activation_id"],
                expected_head_revision_id=second["revision_id"],
                target_revision_id=created["revision_id"],
                operator_ref="operator-rollback-decision",
                rationale="Stale operator view.",
                evidence_refs=["review-finding-rollback"],
            )

        assert len(store.lineage_revisions("rollback-lineage")) == before
        assert store.current_authority("rollback-lineage")["lineage_head_revision_id"] == third[
            "revision_id"
        ]


def test_rollback_holds_write_lock_during_authority_recheck(
    tmp_path: Path, monkeypatch
) -> None:
    with Store(tmp_path) as store, Store(tmp_path) as competitor:
        created, _second, third = _bootstrap(store)
        competitor.connection.execute("PRAGMA busy_timeout = 1")
        original_current_authority = store.current_authority
        authority_reads = 0

        def current_authority_with_competing_write(lineage_id: str) -> dict[str, Any]:
            nonlocal authority_reads
            authority_reads += 1
            authority = original_current_authority(lineage_id)
            if authority_reads == 2:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    competitor.connection.execute(
                        "UPDATE lineages SET status = status WHERE lineage_id = ?",
                        (lineage_id,),
                    )
                competitor.connection.rollback()
            return authority

        monkeypatch.setattr(store, "current_authority", current_authority_with_competing_write)

        rollback = apply_rollback(
            store,
            lineage_id="rollback-lineage",
            activation_id=created["activation_id"],
            expected_head_revision_id=third["revision_id"],
            target_revision_id=created["revision_id"],
            operator_ref="operator-rollback-decision",
            rationale="Exercise the concurrent writer fence.",
            evidence_refs=["concurrency-check-rollback"],
        )

        assert authority_reads == 2
        assert store.current_authority("rollback-lineage")["lineage_head_revision_id"] == (
            rollback["revision_id"]
        )
        assert verify_store(store, "rollback-lineage")["valid"] is True


def test_non_authoritative_activation_cannot_rollback(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        observer = store.create_activation(
            "rollback-lineage",
            third["revision_id"],
            created["substrate_id"],
            activation_id="activation-observer",
        )
        before = len(store.lineage_revisions("rollback-lineage"))

        with pytest.raises(LeaseConflictError, match="does not hold lineage authority"):
            rollback_operator_lineage(
                store,
                lineage_id="rollback-lineage",
                activation_id=observer["activation_id"],
                expected_head_revision_id=third["revision_id"],
                target_revision_id=created["revision_id"],
                operator_ref="operator-rollback-decision",
                rationale="Unauthorized rollback.",
                evidence_refs=["review-finding-rollback"],
            )

        assert len(store.lineage_revisions("rollback-lineage")) == before


@pytest.mark.parametrize(
    ("operator_ref", "rationale", "evidence_refs", "message"),
    [
        ("bad operator ref", "reason", ["evidence-rollback"], "ID contract"),
        ("operator-ref", "", ["evidence-rollback"], "rationale"),
        ("operator-ref", "reason", [], "unique evidence"),
        ("operator-ref", "reason", ["bad evidence"], "unique evidence"),
    ],
)
def test_invalid_rollback_context_fails_without_appending(
    tmp_path: Path,
    operator_ref: str,
    rationale: str,
    evidence_refs: list[str],
    message: str,
) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        before = len(store.lineage_revisions("rollback-lineage"))

        with pytest.raises(RollbackError, match=message):
            rollback_operator_lineage(
                store,
                lineage_id="rollback-lineage",
                activation_id=created["activation_id"],
                expected_head_revision_id=third["revision_id"],
                target_revision_id=created["revision_id"],
                operator_ref=operator_ref,
                rationale=rationale,
                evidence_refs=evidence_refs,
            )

        assert len(store.lineage_revisions("rollback-lineage")) == before


def test_current_head_and_cross_lineage_targets_are_rejected(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        other = create_operator_lineage(
            store,
            lineage_id="other-lineage",
            canonical_state=_state("other"),
            substrate=_substrate(),
            activation_id="activation-other",
        )
        before = len(store.lineage_revisions("rollback-lineage"))

        with pytest.raises(RollbackError, match="strict ancestor"):
            rollback_operator_lineage(
                store,
                lineage_id="rollback-lineage",
                activation_id=created["activation_id"],
                expected_head_revision_id=third["revision_id"],
                target_revision_id=third["revision_id"],
                operator_ref="operator-ref",
                rationale="No-op target.",
                evidence_refs=["evidence-rollback"],
            )
        with pytest.raises(RollbackError, match="not a revision in this lineage"):
            rollback_operator_lineage(
                store,
                lineage_id="rollback-lineage",
                activation_id=created["activation_id"],
                expected_head_revision_id=third["revision_id"],
                target_revision_id=other["revision_id"],
                operator_ref="operator-ref",
                rationale="Cross-lineage target.",
                evidence_refs=["evidence-rollback"],
            )

        assert len(store.lineage_revisions("rollback-lineage")) == before


def test_integrity_failure_blocks_rollback_before_append(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        payload = store.connection.execute(
            "SELECT payload_json FROM revisions WHERE revision_id = ?",
            (created["revision_id"],),
        ).fetchone()["payload_json"]
        tampered = json.loads(payload)
        tampered["canonical_state"]["goals"] = ["tampered"]
        with store.connection:
            store.connection.execute("DROP TRIGGER revisions_no_update")
            store.connection.execute(
                "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
                (json.dumps(tampered), created["revision_id"]),
            )
        before = len(store.lineage_revisions("rollback-lineage"))

        with pytest.raises(IntegrityError, match="revision_hash_mismatch"):
            _rollback(store, created, third)

        assert len(store.lineage_revisions("rollback-lineage")) == before


def test_verify_detects_semantically_invalid_sealed_rollback(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        result = _rollback(store, created, third)
        rollback = store.get_revision(result["revision_id"])
        rollback["canonical_state"] = _state("not-the-target")
        invalid = seal_record(
            rollback,
            previous_revision_sha256=rollback["integrity"][
                "previous_revision_sha256"
            ],
        )
        with store.connection:
            store.connection.execute("DROP TRIGGER revisions_no_update")
            store.connection.execute(
                "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
                (canonical_json(invalid), result["revision_id"]),
            )

        verification = verify_store(store, "rollback-lineage")

        assert verification["valid"] is False
        assert "rollback_state_mismatch" in {
            error["code"] for error in verification["errors"]
        }


def test_verify_rejects_rollback_transition_and_inactive_source_lease(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created, _second, third = _bootstrap(store)
        result = _rollback(store, created, third)
        rollback = store.get_revision(result["revision_id"])
        with store.connection:
            store.connection.execute(
                """INSERT INTO authority_transitions
                   VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)""",
                (
                    "transition-invalid-rollback",
                    "rollback-lineage",
                    created["activation_id"],
                    created["activation_id"],
                    created["lease_id"],
                    created["lease_id"],
                    result["revision_id"],
                    rollback["created_at"],
                ),
            )
            store.connection.execute(
                "UPDATE leases SET issued_at = ? WHERE lease_id = ?",
                ("9999-01-01T00:00:00Z", created["lease_id"]),
            )

        verification = verify_store(store, "rollback-lineage")
        codes = {error["code"] for error in verification["errors"]}

        assert verification["valid"] is False
        assert "rollback_has_authority_transition" in codes
        assert "rollback_lease_mismatch" in codes


def test_cli_applies_and_verifies_rollback(tmp_path: Path, capsys) -> None:
    state_one = tmp_path / "state-one.json"
    state_two = tmp_path / "state-two.json"
    substrate_file = tmp_path / "substrate.json"
    state_one.write_text(json.dumps(_state("one")), encoding="utf-8")
    state_two.write_text(json.dumps(_state("two")), encoding="utf-8")
    substrate_file.write_text(json.dumps(_substrate()), encoding="utf-8")
    state_dir = tmp_path / "store"
    common = ("--state-dir", str(state_dir), "--lineage", "rollback-lineage")

    created = _cli_json(
        capsys, "lineage", "create", *common, "--state-file", str(state_one),
        "--substrate-file", str(substrate_file),
        "--activation-id", "activation-rollback", "--json",
    )
    checkpoint = _cli_json(
        capsys, "lineage", "checkpoint", *common, "--activation",
        "activation-rollback", "--state-file", str(state_two), "--json",
    )
    rolled_back = _cli_json(
        capsys, "lineage", "rollback", *common, "--activation", "activation-rollback",
        "--expected-head", checkpoint["revision_id"],
        "--target-revision", created["revision_id"],
        "--operator-ref", "operator-rollback-decision", "--rationale",
        "Restore the accepted initial state.",
        "--evidence-ref", "review-finding-rollback", "--json",
    )

    assert rolled_back["authority_transferred"] is False
    assert rolled_back["authority_transition_added"] is False
    assert rolled_back["verification"]["valid"] is True
    with Store(state_dir) as store:
        revision = store.get_revision(rolled_back["revision_id"])
        assert revision["canonical_state"] == _state("one")
        assert verify_store(store, "rollback-lineage")["valid"] is True

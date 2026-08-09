from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from torc.branches import create_lineage_branch
from torc.canonical import canonical_json, seal_record
from torc.cli import main
from torc.errors import BranchError, IntegrityError, LeaseConflictError
from torc.operator import (
    branch_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
)
from torc.store import Store
from torc.verify import verify_store

ROOT = Path(__file__).resolve().parents[1]


def _state(label: str) -> dict[str, Any]:
    return {
        "identity": {"label": f"Branch state {label}"},
        "self_model": {
            "role": label,
            "settled_decisions": [f"decision-{label}"],
            "methods": ["independent append-only lineages"],
        },
        "goals": [f"goal-{label}"],
        "commitments": ["preserve branch origin"],
        "constraints": ["do not share authority"],
        "open_work": [f"work-{label}"],
        "uncertainties": [],
        "artifact_refs": [],
        "memory_refs": [],
    }


def _substrate(substrate_id: str = "branch-source-substrate") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": substrate_id,
        "label": substrate_id,
        "adapter": "manual",
        "capabilities": ["repository_read", "repository_write"],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": ["implementation"],
    }


def _bootstrap(store: Store) -> dict[str, Any]:
    return create_operator_lineage(
        store,
        lineage_id="source-lineage",
        canonical_state=_state("source"),
        substrate=_substrate(),
        activation_id="activation-source",
    )


def _branch(store: Store, source: dict[str, Any]) -> dict[str, Any]:
    return branch_operator_lineage(
        store,
        source_lineage_id="source-lineage",
        source_activation_id=source["activation_id"],
        expected_source_revision_id=source["revision_id"],
        child_lineage_id="child-lineage",
        child_activation_id="activation-child",
        child_substrate=_substrate("branch-child-substrate"),
        operator_ref="operator-branch-decision",
        target_assignment_ref="assignment-child-lineage",
        rationale="Create an independent implementation direction.",
        evidence_refs=["design-finding-branch"],
    )


def _cli_json(capsys, *args: str) -> dict[str, Any]:
    assert main(list(args)) == 0
    return json.loads(capsys.readouterr().out)


def test_branch_creates_independent_lineage_and_preserves_source(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        source_before = store.current_authority("source-lineage")

        result = _branch(store, source)
        child = store.get_revision(result["child_revision_id"])
        child_authority = store.current_authority("child-lineage")
        active_leases = store.connection.execute(
            "SELECT lineage_id FROM leases WHERE status = 'active' ORDER BY lineage_id"
        ).fetchall()

        assert result["source_authority_unchanged"] is True
        assert store.current_authority("source-lineage") == source_before
        assert child["event_type"] == "branch_created"
        assert child["parent_revision_ids"] == []
        assert child["integrity"]["previous_revision_sha256"] is None
        assert child["canonical_state"] == store.get_revision(source["revision_id"])[
            "canonical_state"
        ]
        assert child["branch_origin"]["source_revision_id"] == source["revision_id"]
        assert child_authority["activation_id"] == "activation-child"
        assert child_authority["lineage_head_revision_id"] == child["revision_id"]
        assert [row["lineage_id"] for row in active_leases] == [
            "child-lineage",
            "source-lineage",
        ]
        schema = json.loads(
            (ROOT / "schemas" / "lineage-revision.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(child)
        assert result["source_verification"]["valid"] is True
        assert result["child_verification"]["valid"] is True


def test_source_and_child_advance_independently(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        branch = _branch(store, source)

        source_checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="source-lineage",
            activation_id=source["activation_id"],
            canonical_state=_state("source-next"),
        )
        child_checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="child-lineage",
            activation_id=branch["child_activation_id"],
            canonical_state=_state("child-next"),
        )

        assert store.current_authority("source-lineage")["lineage_head_revision_id"] == (
            source_checkpoint["revision_id"]
        )
        assert store.current_authority("child-lineage")["lineage_head_revision_id"] == (
            child_checkpoint["revision_id"]
        )
        assert verify_store(store, "source-lineage")["valid"] is True
        assert verify_store(store, "child-lineage")["valid"] is True


def test_stale_and_non_authoritative_source_fail_without_child(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        observer = store.create_activation(
            "source-lineage",
            source["revision_id"],
            source["substrate_id"],
            activation_id="activation-observer",
        )
        checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="source-lineage",
            activation_id=source["activation_id"],
            canonical_state=_state("source-next"),
        )

        with pytest.raises(LeaseConflictError, match="expected head"):
            _branch(store, source)
        with pytest.raises(LeaseConflictError, match="does not hold lineage authority"):
            branch_operator_lineage(
                store,
                source_lineage_id="source-lineage",
                source_activation_id=observer["activation_id"],
                expected_source_revision_id=checkpoint["revision_id"],
                child_lineage_id="child-lineage",
                child_activation_id="activation-child",
                child_substrate=_substrate("branch-child-substrate"),
                operator_ref="operator-branch-decision",
                target_assignment_ref="assignment-child-lineage",
                rationale="Unauthorized branch.",
                evidence_refs=["design-finding-branch"],
            )

        assert store.connection.execute(
            "SELECT 1 FROM lineages WHERE lineage_id = 'child-lineage'"
        ).fetchone() is None


@pytest.mark.parametrize(
    ("operator_ref", "assignment_ref", "rationale", "evidence", "message"),
    [
        ("bad operator", "assignment-child", "reason", ["evidence"], "ID contract"),
        ("operator", "bad assignment", "reason", ["evidence"], "ID contract"),
        ("operator", "assignment-child", "", ["evidence"], "rationale"),
        ("operator", "assignment-child", "reason", [], "unique evidence"),
        ("operator", "assignment-child", "reason", ["bad evidence"], "unique evidence"),
        ("operator", "assignment-child", "reason", ["operator"], "distinct"),
    ],
)
def test_invalid_branch_context_creates_no_child(
    tmp_path: Path,
    operator_ref: str,
    assignment_ref: str,
    rationale: str,
    evidence: list[str],
    message: str,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)

        with pytest.raises(BranchError, match=message):
            branch_operator_lineage(
                store,
                source_lineage_id="source-lineage",
                source_activation_id=source["activation_id"],
                expected_source_revision_id=source["revision_id"],
                child_lineage_id="child-lineage",
                child_activation_id="activation-child",
                child_substrate=_substrate("branch-child-substrate"),
                operator_ref=operator_ref,
                target_assignment_ref=assignment_ref,
                rationale=rationale,
                evidence_refs=evidence,
            )

        assert store.connection.execute(
            "SELECT 1 FROM lineages WHERE lineage_id = 'child-lineage'"
        ).fetchone() is None


def test_duplicate_identity_and_substrate_conflict_leave_no_partial_child(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        store.register_substrate(_substrate("branch-child-substrate"))
        conflicting = _substrate("branch-child-substrate")
        conflicting["label"] = "conflicting descriptor"

        with pytest.raises(BranchError, match="different content"):
            branch_operator_lineage(
                store,
                source_lineage_id="source-lineage",
                source_activation_id=source["activation_id"],
                expected_source_revision_id=source["revision_id"],
                child_lineage_id="child-lineage",
                child_activation_id="activation-child",
                child_substrate=conflicting,
                operator_ref="operator-branch-decision",
                target_assignment_ref="assignment-child-lineage",
                rationale="Conflicting substrate.",
                evidence_refs=["design-finding-branch"],
            )

        assert store.connection.execute(
            "SELECT 1 FROM lineages WHERE lineage_id = 'child-lineage'"
        ).fetchone() is None
        assert store.connection.execute(
            "SELECT 1 FROM activations WHERE activation_id = 'activation-child'"
        ).fetchone() is None


def test_duplicate_child_lineage_leaves_existing_branch_unchanged(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        first = _branch(store, source)
        counts_before = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("lineages", "revisions", "activations", "leases")
        }

        with pytest.raises(BranchError, match="child lineage already exists"):
            _branch(store, source)

        counts_after = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in counts_before
        }
        assert counts_after == counts_before
        assert store.current_authority("child-lineage")["lineage_head_revision_id"] == (
            first["child_revision_id"]
        )


def test_duplicate_child_activation_is_rejected_before_substrate_registration(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        store.create_activation(
            "source-lineage",
            source["revision_id"],
            source["substrate_id"],
            activation_id="activation-child",
        )

        with pytest.raises(BranchError, match="child activation already exists"):
            _branch(store, source)

        assert store.connection.execute(
            "SELECT 1 FROM lineages WHERE lineage_id = 'child-lineage'"
        ).fetchone() is None
        assert store.connection.execute(
            "SELECT 1 FROM substrates WHERE substrate_id = 'branch-child-substrate'"
        ).fetchone() is None


def test_branch_holds_write_lock_during_source_authority_check(
    tmp_path: Path, monkeypatch
) -> None:
    with Store(tmp_path) as store, Store(tmp_path) as competitor:
        source = _bootstrap(store)
        competitor.connection.execute("PRAGMA busy_timeout = 1")
        original = store.current_authority

        def authority_with_competing_write(lineage_id: str) -> dict[str, Any]:
            authority = original(lineage_id)
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                competitor.connection.execute(
                    "UPDATE lineages SET status = status WHERE lineage_id = ?",
                    (lineage_id,),
                )
            competitor.connection.rollback()
            return authority

        monkeypatch.setattr(store, "current_authority", authority_with_competing_write)
        child = create_lineage_branch(
            store,
            source_lineage_id="source-lineage",
            source_activation_id=source["activation_id"],
            expected_source_revision_id=source["revision_id"],
            child_lineage_id="child-lineage",
            child_activation_id="activation-child",
            child_substrate=_substrate("branch-child-substrate"),
            operator_ref="operator-branch-decision",
            target_assignment_ref="assignment-child-lineage",
            rationale="Exercise the concurrent writer fence.",
            evidence_refs=["concurrency-check-branch"],
        )

        assert child["lineage_id"] == "child-lineage"
        assert verify_store(store, "child-lineage")["valid"] is True


def test_branch_cannot_predate_its_source_revision(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)

        with pytest.raises(BranchError, match="cannot predate"):
            create_lineage_branch(
                store,
                source_lineage_id="source-lineage",
                source_activation_id=source["activation_id"],
                expected_source_revision_id=source["revision_id"],
                child_lineage_id="child-lineage",
                child_activation_id="activation-child",
                child_substrate=_substrate("branch-child-substrate"),
                operator_ref="operator-branch-decision",
                target_assignment_ref="assignment-child-lineage",
                rationale="Impossible chronology.",
                evidence_refs=["chronology-check-branch"],
                created_at="2000-01-01T00:00:00Z",
            )

        assert store.connection.execute(
            "SELECT 1 FROM lineages WHERE lineage_id = 'child-lineage'"
        ).fetchone() is None


def test_integrity_failure_blocks_branch_before_any_child_write(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        payload = store.connection.execute(
            "SELECT payload_json FROM revisions WHERE revision_id = ?",
            (source["revision_id"],),
        ).fetchone()["payload_json"]
        tampered = json.loads(payload)
        tampered["canonical_state"]["goals"] = ["tampered"]
        with store.connection:
            store.connection.execute("DROP TRIGGER revisions_no_update")
            store.connection.execute(
                "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
                (json.dumps(tampered), source["revision_id"]),
            )

        with pytest.raises(IntegrityError, match="revision_hash_mismatch"):
            _branch(store, source)

        assert store.connection.execute(
            "SELECT 1 FROM lineages WHERE lineage_id = 'child-lineage'"
        ).fetchone() is None


def test_verify_detects_semantically_invalid_sealed_branch(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        result = _branch(store, source)
        child = store.get_revision(result["child_revision_id"])
        child["canonical_state"] = _state("not-source")
        invalid = seal_record(child, previous_revision_sha256=None)
        with store.connection:
            store.connection.execute("DROP TRIGGER revisions_no_update")
            store.connection.execute(
                "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
                (canonical_json(invalid), child["revision_id"]),
            )

        verification = verify_store(store, "child-lineage")

        assert verification["valid"] is False
        assert "branch_state_mismatch" in {
            error["code"] for error in verification["errors"]
        }


def test_verify_rejects_branch_pinned_to_non_head_source_revision(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="source-lineage",
            activation_id=source["activation_id"],
            canonical_state=_state("source-current"),
        )
        result = _branch(store, checkpoint)
        child = store.get_revision(result["child_revision_id"])
        old_source = store.get_revision(source["revision_id"])
        child["canonical_state"] = old_source["canonical_state"]
        child["branch_origin"]["source_revision_id"] = source["revision_id"]
        child["branch_origin"]["source_revision_sha256"] = old_source["integrity"][
            "canonical_payload_sha256"
        ]
        child["evidence_refs"][0] = source["revision_id"]
        invalid = seal_record(child, previous_revision_sha256=None)
        with store.connection:
            store.connection.execute("DROP TRIGGER revisions_no_update")
            store.connection.execute(
                "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
                (canonical_json(invalid), child["revision_id"]),
            )

        verification = verify_store(store, "child-lineage")

        assert verification["valid"] is False
        assert "branch_source_not_head_at_creation" in {
            error["code"] for error in verification["errors"]
        }


def test_verify_requires_exact_initial_branch_transition(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        result = _branch(store, source)
        with store.connection:
            store.connection.execute(
                """UPDATE authority_transitions SET occurred_at = ?
                   WHERE resulting_revision_id = ?""",
                ("9999-01-01T00:00:00Z", result["child_revision_id"]),
            )

        verification = verify_store(store, "child-lineage")

        assert verification["valid"] is False
        assert "branch_initial_transition_missing" in {
            error["code"] for error in verification["errors"]
        }


def test_cli_creates_and_verifies_branch(tmp_path: Path, capsys) -> None:
    state_file = tmp_path / "state.json"
    source_substrate_file = tmp_path / "source-substrate.json"
    child_substrate_file = tmp_path / "child-substrate.json"
    state_file.write_text(json.dumps(_state("source")), encoding="utf-8")
    source_substrate_file.write_text(json.dumps(_substrate()), encoding="utf-8")
    child_substrate_file.write_text(
        json.dumps(_substrate("branch-child-substrate")), encoding="utf-8"
    )
    state_dir = tmp_path / "store"
    source = _cli_json(
        capsys, "lineage", "create", "--state-dir", str(state_dir),
        "--lineage", "source-lineage", "--state-file", str(state_file),
        "--substrate-file", str(source_substrate_file),
        "--activation-id", "activation-source", "--json",
    )
    branch = _cli_json(
        capsys, "lineage", "branch", "--state-dir", str(state_dir),
        "--source-lineage", "source-lineage",
        "--source-activation", "activation-source",
        "--expected-head", source["revision_id"],
        "--child-lineage", "child-lineage",
        "--child-activation", "activation-child",
        "--substrate-file", str(child_substrate_file),
        "--operator-ref", "operator-branch-decision",
        "--target-assignment-ref", "assignment-child-lineage",
        "--rationale", "Create an independent implementation direction.",
        "--evidence-ref", "design-finding-branch", "--json",
    )

    assert branch["source_authority_unchanged"] is True
    assert branch["source_verification"]["valid"] is True
    assert branch["child_verification"]["valid"] is True
    with Store(state_dir) as store:
        assert store.current_authority("source-lineage")["activation_id"] == (
            "activation-source"
        )
        assert store.current_authority("child-lineage")["activation_id"] == (
            "activation-child"
        )

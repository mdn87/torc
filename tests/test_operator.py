from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from torc.canonical import canonical_json, seal_record
from torc.cli import main
from torc.errors import HandoffError, IntegrityError, LeaseConflictError
from torc.handoffs import resolve_handoff
from torc.operator import (
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
    prepare_operator_handoff,
    prepare_operator_recovery,
    resolve_operator_handoff,
    resolve_operator_recovery,
)
from torc.store import Store
from torc.verify import verify_store


def _state(*, open_work: list[str] | None = None) -> dict[str, Any]:
    return {
        "identity": {"label": "TORC development lineage"},
        "self_model": {
            "role": "Implement the bounded P2 pilot",
            "settled_decisions": ["Dogfood a real handoff instead of rerunning P1b"],
            "methods": ["Keep the operator surface thin"],
        },
        "goals": ["Exercise acceptance-gated succession during real work"],
        "commitments": ["Keep canonical history append-only"],
        "constraints": ["Do not edit the parent repository"],
        "open_work": open_work or ["Implement and review the operator handoff lane"],
        "uncertainties": ["Whether the operator overhead is worthwhile"],
        "artifact_refs": ["artifact-p2-scope"],
        "memory_refs": [],
    }


def _source_substrate() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": "codex-windows",
        "label": "Codex implementation session on Windows",
        "adapter": "manual",
        "capabilities": ["repository_read", "repository_write", "verification_execute"],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": ["implementation"],
    }


def _target_substrate() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": "claude-wsl",
        "label": "Claude review session in WSL2",
        "adapter": "manual",
        "capabilities": ["repository_read", "verification_execute"],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": ["review"],
    }


def _plan() -> dict[str, Any]:
    return {
        "target_substrate": _target_substrate(),
        "target_activation_id": "activation-review",
        "task_phase": "independent-review",
        "requirements": {
            "capabilities": ["repository_read", "verification_execute"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 500,
        },
        "budget_limit": 1000,
        "target_responsibility": "Review the P2 operator handoff implementation",
        "reason_code": "task_phase_transition",
        "rationale": "The implementation batch is ready for independent review.",
    }


def _recovery_plan() -> dict[str, Any]:
    plan = _plan()
    plan.update(
        {
            "target_activation_id": "activation-recovery",
            "task_phase": "failure-recovery",
            "target_responsibility": "Recover the last verified TORC lineage head",
            "reason_code": "failure_recovery",
            "rationale": "The authoritative activation is unavailable.",
            "operator_ref": "operator-recovery-decision",
            "target_assignment_ref": "assignment-recovery-review",
        }
    )
    plan["target_substrate"]["task_affinities"].append("recovery")
    return plan


def _bootstrap(store: Store) -> dict[str, Any]:
    return create_operator_lineage(
        store,
        lineage_id="torc-dev",
        canonical_state=_state(),
        substrate=_source_substrate(),
        activation_id="activation-implementation",
    )


def _load_template(store: Store, prepared: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (store.state_dir / prepared["reconstruction_template_path"]).read_text(
            encoding="utf-8"
        )
    )


def test_authoritative_checkpoint_updates_status(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="torc-dev",
            activation_id=created["activation_id"],
            canonical_state=_state(open_work=["Prepare independent review"]),
            evidence_refs=["commit-p2-implementation"],
        )
        status = operator_lineage_status(store, "torc-dev")

        assert checkpoint["revision_id"] == status["head_revision_id"]
        assert status["open_work"] == ["Prepare independent review"]
        assert status["revision_count"] == 2
        assert status["current_authority"]["activation_id"] == created["activation_id"]
        assert verify_store(store, "torc-dev")["valid"] is True


def test_non_authoritative_activation_cannot_checkpoint(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        observer = store.create_activation(
            "torc-dev",
            created["revision_id"],
            created["substrate_id"],
            activation_id="activation-observer",
        )

        with pytest.raises(LeaseConflictError):
            checkpoint_operator_lineage(
                store,
                lineage_id="torc-dev",
                activation_id=observer["activation_id"],
                canonical_state=_state(),
            )


def test_prepare_exports_derived_artifacts_without_transferring_authority(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="torc-dev",
            source_activation_id=created["activation_id"],
            plan=_plan(),
        )

        brief = (store.state_dir / prepared["brief_path"]).read_text(encoding="utf-8")
        template = _load_template(store, prepared)
        snapshot = store.get_hashed_record("handoffs", "handoff_id", prepared["handoff_id"])

        assert "Derived execution artifact" in brief
        assert template["source_revision_id"] == created["revision_id"]
        assert snapshot["target_activation_id"] == prepared["target_activation_id"]
        assert store.current_authority("torc-dev")["activation_id"] == created["activation_id"]
        assert operator_lineage_status(store, "torc-dev")["pending_handoff_ids"] == [
            prepared["handoff_id"]
        ]
        assert verify_store(store, "torc-dev")["valid"] is True


def test_only_bound_target_activation_can_resolve(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="torc-dev",
            source_activation_id=created["activation_id"],
            plan=_plan(),
        )
        other = store.create_activation(
            "torc-dev",
            created["revision_id"],
            _target_substrate()["substrate_id"],
            activation_id="activation-other-reviewer",
        )

        with pytest.raises(HandoffError, match="intended handoff recipient"):
            resolve_operator_handoff(
                store,
                handoff_id=prepared["handoff_id"],
                target_activation_id=other["activation_id"],
                reconstruction=_load_template(store, prepared),
            )

        assert store.current_authority("torc-dev")["activation_id"] == created["activation_id"]


def test_rejection_is_preserved_and_source_authority_remains(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="torc-dev",
            source_activation_id=created["activation_id"],
            plan=_plan(),
        )
        reconstruction = _load_template(store, prepared)
        reconstruction["hard_constraints"] = []

        resolved = resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=reconstruction,
        )

        assert resolved["disposition"] == "rejected"
        assert resolved["ok"] is False
        assert resolved["failed_requirements"] == ["hard_constraints"]
        assert resolved["current_authority"]["activation_id"] == created["activation_id"]
        assert len(store.list_hashed_records("handoff_results", "torc-dev")) == 1
        assert resolved["verification"]["valid"] is True


def test_acceptance_transfers_authority_to_bound_target(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="torc-dev",
            source_activation_id=created["activation_id"],
            plan=_plan(),
        )
        reconstruction = _load_template(store, prepared)
        reconstruction["new_inferences"] = ["Review must still inspect the complete diff"]

        resolved = resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=reconstruction,
        )

        assert resolved["disposition"] == "accepted"
        assert resolved["failed_requirements"] == []
        assert resolved["current_authority"]["activation_id"] == "activation-review"
        assert store.get_activation(created["activation_id"])["state"] == "suspended"
        assert operator_lineage_status(store, "torc-dev")["pending_handoff_ids"] == []
        assert resolved["verification"]["valid"] is True


def test_recovery_prepare_freezes_evidence_without_transferring_authority(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="torc-dev",
            failed_activation_id=created["activation_id"],
            plan=_recovery_plan(),
            evidence_refs=["process-probe-001", "operator-observation-001"],
        )
        snapshot = store.get_hashed_record(
            "handoffs", "handoff_id", prepared["handoff_id"]
        )
        brief = (store.state_dir / prepared["brief_path"]).read_text(encoding="utf-8")

        assert snapshot["reason_code"] == "failure_recovery"
        assert snapshot["recovery_context"] == prepared["recovery_context"]
        assert snapshot["recovery_context"]["evidence_refs"] == [
            "process-probe-001",
            "operator-observation-001",
        ]
        assert snapshot["source_authority"]["lease_id"] == created["lease_id"]
        schema = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "schemas"
                / "handoff-snapshot.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(snapshot)
        assert "Recovery declaration" in brief
        assert store.current_authority("torc-dev")["activation_id"] == created[
            "activation_id"
        ]
        assert store.get_activation(created["activation_id"])["state"] == "active"
        assert store.get_activation(prepared["target_activation_id"])["state"] == "pending"
        assert verify_store(store, "torc-dev")["valid"] is True


@pytest.mark.parametrize(
    ("plan_update", "evidence_refs", "message"),
    [
        ({"reason_code": "task_phase_transition"}, ["probe-001"], "recovery plans"),
        ({}, [], "unique failure evidence"),
        ({}, ["probe result 1"], "unique failure evidence"),
        ({"operator_ref": ""}, ["probe-001"], "operator_ref"),
        ({"target_assignment_ref": ""}, ["probe-001"], "target_assignment_ref"),
        (
            {"target_activation_id": "activation-implementation"},
            ["probe-001"],
            "must differ from the source",
        ),
    ],
)
def test_invalid_recovery_declaration_creates_no_records(
    tmp_path: Path,
    plan_update: dict[str, Any],
    evidence_refs: list[str],
    message: str,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        plan = _recovery_plan()
        plan.update(plan_update)
        before = {
            table: store.connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()[
                "count"
            ]
            for table in ("substrates", "fit_decisions", "projections", "activations", "handoffs")
        }

        with pytest.raises(HandoffError, match=message):
            prepare_operator_recovery(
                store,
                lineage_id="torc-dev",
                failed_activation_id=created["activation_id"],
                plan=plan,
                evidence_refs=evidence_refs,
            )

        after = {
            table: store.connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()[
                "count"
            ]
            for table in before
        }
        assert after == before


def test_recovery_requires_current_authoritative_activation(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)

        with pytest.raises(HandoffError, match="does not hold lineage authority"):
            prepare_operator_recovery(
                store,
                lineage_id="torc-dev",
                failed_activation_id="activation-not-authoritative",
                plan=_recovery_plan(),
                evidence_refs=["probe-001"],
            )

        assert store.current_authority("torc-dev")["activation_id"] == created[
            "activation_id"
        ]
        assert store.list_hashed_records("handoffs", "torc-dev") == []


def test_recovery_rejects_preexisting_target_before_creating_records(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        store.create_activation(
            "torc-dev",
            created["revision_id"],
            created["substrate_id"],
            activation_id="activation-recovery",
        )
        before = {
            table: store.connection.execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            ).fetchone()["count"]
            for table in ("substrates", "fit_decisions", "projections", "activations", "handoffs")
        }

        with pytest.raises(HandoffError, match="target activation already exists"):
            prepare_operator_recovery(
                store,
                lineage_id="torc-dev",
                failed_activation_id=created["activation_id"],
                plan=_recovery_plan(),
                evidence_refs=["probe-001"],
            )

        after = {
            table: store.connection.execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            ).fetchone()["count"]
            for table in before
        }
        assert after == before


def test_rejected_recovery_preserves_failed_source_as_authority(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="torc-dev",
            failed_activation_id=created["activation_id"],
            plan=_recovery_plan(),
            evidence_refs=["probe-001"],
        )
        reconstruction = _load_template(store, prepared)
        reconstruction["active_commitments"] = []

        resolved = resolve_operator_recovery(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=reconstruction,
        )

        assert resolved["disposition"] == "rejected"
        assert resolved["current_authority"]["activation_id"] == created["activation_id"]
        assert store.get_activation(created["activation_id"])["state"] == "active"
        assert store.get_activation(prepared["target_activation_id"])["state"] == "pending"
        assert resolved["verification"]["valid"] is True


def test_accepted_recovery_marks_source_failed_and_transfers_one_lease(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="torc-dev",
            failed_activation_id=created["activation_id"],
            plan=_recovery_plan(),
            evidence_refs=["probe-001"],
        )

        resolved = resolve_operator_recovery(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=_load_template(store, prepared),
        )
        active_leases = store.connection.execute(
            "SELECT lease_id FROM leases WHERE lineage_id = ? AND status = 'active'",
            ("torc-dev",),
        ).fetchall()

        assert resolved["disposition"] == "accepted"
        assert store.get_activation(created["activation_id"])["state"] == "failed"
        assert store.get_activation(created["activation_id"])["ended_at"] is not None
        assert store.get_activation(prepared["target_activation_id"])["state"] == "active"
        assert len(active_leases) == 1
        assert resolved["current_authority"]["activation_id"] == "activation-recovery"
        assert resolved["verification"]["valid"] is True


def test_recovery_resolution_revalidates_frozen_context(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="torc-dev",
            failed_activation_id=created["activation_id"],
            plan=_recovery_plan(),
            evidence_refs=["probe-001"],
        )
        snapshot = store.get_hashed_record(
            "handoffs", "handoff_id", prepared["handoff_id"]
        )
        legacy_handoff_id = "handoff-legacy-recovery"
        snapshot["handoff_id"] = legacy_handoff_id
        snapshot.pop("recovery_context")
        legacy_snapshot = seal_record(snapshot)
        with store.connection:
            store.connection.execute(
                "INSERT INTO handoffs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    legacy_handoff_id,
                    legacy_snapshot["lineage_id"],
                    legacy_snapshot["source_revision_id"],
                    legacy_snapshot["source_activation_id"],
                    legacy_snapshot["source_lease_id"],
                    legacy_snapshot["target_substrate_id"],
                    legacy_snapshot["fit_decision_id"],
                    legacy_snapshot["projection_id"],
                    canonical_json(legacy_snapshot),
                ),
            )

        with pytest.raises(HandoffError, match="structured recovery context"):
            resolve_handoff(
                store,
                handoff_id=legacy_handoff_id,
                target_activation_id=prepared["target_activation_id"],
                reconstruction=_load_template(store, prepared),
            )

        assert store.current_authority("torc-dev")["activation_id"] == created[
            "activation_id"
        ]
        assert store.list_hashed_records("handoff_results", "torc-dev") == []
        assert verify_store(store, "torc-dev")["errors"][0]["code"] == (
            "recovery_context_invalid"
        )


def test_verify_detects_inconsistent_accepted_recovery_source_state(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="torc-dev",
            failed_activation_id=created["activation_id"],
            plan=_recovery_plan(),
            evidence_refs=["probe-001"],
        )
        resolve_operator_recovery(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=_load_template(store, prepared),
        )
        with store.connection:
            store.connection.execute(
                "UPDATE activations SET state = 'suspended' WHERE activation_id = ?",
                (created["activation_id"],),
            )

        verification = verify_store(store, "torc-dev")

        assert verification["valid"] is False
        assert "recovery_source_activation_not_failed" in {
            error["code"] for error in verification["errors"]
        }


def test_stale_recovery_fails_closed_after_source_advances(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="torc-dev",
            failed_activation_id=created["activation_id"],
            plan=_recovery_plan(),
            evidence_refs=["probe-001"],
        )
        checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="torc-dev",
            activation_id=created["activation_id"],
            canonical_state=_state(open_work=["Source returned before recovery"]),
        )

        with pytest.raises(LeaseConflictError, match="changed after handoff preparation"):
            resolve_operator_recovery(
                store,
                handoff_id=prepared["handoff_id"],
                target_activation_id=prepared["target_activation_id"],
                reconstruction=_load_template(store, prepared),
            )

        assert store.current_authority("torc-dev")["lineage_head_revision_id"] == checkpoint[
            "revision_id"
        ]
        assert store.current_authority("torc-dev")["activation_id"] == created[
            "activation_id"
        ]
        assert store.list_hashed_records("handoff_results", "torc-dev") == []
        assert verify_store(store, "torc-dev")["valid"] is True


def test_artifact_tampering_blocks_resolution_before_authority_transfer(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="torc-dev",
            source_activation_id=created["activation_id"],
            plan=_plan(),
        )
        brief_path = store.state_dir / prepared["brief_path"]
        brief_path.write_text("tampered\n", encoding="utf-8")

        with pytest.raises(IntegrityError, match="artifact_hash_mismatch"):
            resolve_operator_handoff(
                store,
                handoff_id=prepared["handoff_id"],
                target_activation_id=prepared["target_activation_id"],
                reconstruction=_load_template(store, prepared),
            )

        assert store.current_authority("torc-dev")["activation_id"] == created["activation_id"]
        assert store.list_hashed_records("handoff_results", "torc-dev") == []


def test_cli_drives_lineage_and_accepted_handoff(tmp_path: Path, capsys) -> None:
    state_file = tmp_path / "state.json"
    substrate_file = tmp_path / "substrate.json"
    plan_file = tmp_path / "plan.json"
    state_file.write_text(json.dumps(_state()), encoding="utf-8")
    substrate_file.write_text(json.dumps(_source_substrate()), encoding="utf-8")
    plan_file.write_text(json.dumps(_plan()), encoding="utf-8")
    store_dir = tmp_path / "store"

    assert (
        main(
            [
                "lineage",
                "create",
                "--state-dir",
                str(store_dir),
                "--lineage",
                "torc-dev",
                "--state-file",
                str(state_file),
                "--substrate-file",
                str(substrate_file),
                "--activation-id",
                "activation-implementation",
                "--json",
            ]
        )
        == 0
    )
    created = json.loads(capsys.readouterr().out)

    assert (
        main(
            [
                "lineage",
                "status",
                "--state-dir",
                str(store_dir),
                "--lineage",
                "torc-dev",
                "--json",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)

    assert created["activation_id"] == "activation-implementation"
    assert status["current_authority"]["activation_id"] == "activation-implementation"

    assert (
        main(
            [
                "handoff",
                "prepare",
                "--state-dir",
                str(store_dir),
                "--lineage",
                "torc-dev",
                "--source-activation",
                "activation-implementation",
                "--plan-file",
                str(plan_file),
                "--json",
            ]
        )
        == 0
    )
    prepared = json.loads(capsys.readouterr().out)
    reconstruction_file = store_dir / prepared["reconstruction_template_path"]

    assert (
        main(
            [
                "handoff",
                "resolve",
                "--state-dir",
                str(store_dir),
                "--handoff",
                prepared["handoff_id"],
                "--target-activation",
                prepared["target_activation_id"],
                "--reconstruction-file",
                str(reconstruction_file),
                "--json",
            ]
        )
        == 0
    )
    resolved = json.loads(capsys.readouterr().out)

    assert resolved["disposition"] == "accepted"
    assert resolved["current_authority"]["activation_id"] == "activation-review"


def test_cli_drives_accepted_failure_recovery(tmp_path: Path, capsys) -> None:
    state_file = tmp_path / "state.json"
    substrate_file = tmp_path / "substrate.json"
    plan_file = tmp_path / "recovery-plan.json"
    state_file.write_text(json.dumps(_state()), encoding="utf-8")
    substrate_file.write_text(json.dumps(_source_substrate()), encoding="utf-8")
    plan_file.write_text(json.dumps(_recovery_plan()), encoding="utf-8")
    store_dir = tmp_path / "store"

    assert main(
        [
            "lineage",
            "create",
            "--state-dir",
            str(store_dir),
            "--lineage",
            "torc-dev",
            "--state-file",
            str(state_file),
            "--substrate-file",
            str(substrate_file),
            "--activation-id",
            "activation-implementation",
            "--json",
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "recovery",
            "prepare",
            "--state-dir",
            str(store_dir),
            "--lineage",
            "torc-dev",
            "--failed-activation",
            "activation-implementation",
            "--plan-file",
            str(plan_file),
            "--evidence-ref",
            "process-probe-001",
            "--json",
        ]
    ) == 0
    prepared = json.loads(capsys.readouterr().out)

    assert main(
        [
            "recovery",
            "resolve",
            "--state-dir",
            str(store_dir),
            "--handoff",
            prepared["handoff_id"],
            "--target-activation",
            prepared["target_activation_id"],
            "--reconstruction-file",
            str(store_dir / prepared["reconstruction_template_path"]),
            "--json",
        ]
    ) == 0
    resolved = json.loads(capsys.readouterr().out)

    assert resolved["disposition"] == "accepted"
    assert resolved["current_authority"]["activation_id"] == "activation-recovery"
    with Store(store_dir) as store:
        assert store.get_activation("activation-implementation")["state"] == "failed"
        assert verify_store(store, "torc-dev")["valid"] is True

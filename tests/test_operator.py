from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from torc.cli import main
from torc.errors import HandoffError, IntegrityError, LeaseConflictError
from torc.operator import (
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
    prepare_operator_handoff,
    resolve_operator_handoff,
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
        assert operator_lineage_status(store, "torc-dev")["pending_handoff_ids"] == []
        assert resolved["verification"]["valid"] is True


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

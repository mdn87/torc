from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from torc.demo import inspect_lineage, run_demo
from torc.errors import (
    HandoffError,
    LeaseConflictError,
    NotFoundError,
    ProjectionBudgetError,
)
from torc.fit import evaluate_fit
from torc.handoffs import expected_reconstruction, prepare_handoff, resolve_handoff
from torc.projections import compile_projection
from torc.store import Store
from torc.verify import verify_store


def _state() -> dict[str, Any]:
    return {
        "identity": {"label": "Test lineage"},
        "self_model": {
            "role": "Implement P0",
            "settled_decisions": ["Authority is acceptance-gated"],
            "methods": ["Prefer deterministic evidence"],
        },
        "goals": ["Prove continuity", "Verify provenance"],
        "commitments": ["Preserve authority", "Keep canonical state immutable"],
        "constraints": ["No network", "No daemon"],
        "open_work": ["Run independent review"],
        "uncertainties": ["Baseline comparison remains unproven"],
        "artifact_refs": ["artifact-one", "artifact-two"],
        "memory_refs": [],
    }


def _substrate(
    substrate_id: str, *, review: bool, context_limit: int = 300
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": substrate_id,
        "label": substrate_id,
        "adapter": "synthetic",
        "capabilities": (
            ["repository_read", "independent_review"]
            if review
            else ["repository_read", "repository_write"]
        ),
        "policy_labels": ["local-synthetic"],
        "context_budget": {"unit": "words", "limit": context_limit},
        "task_affinities": ["review" if review else "implementation"],
    }


def _prepared(store: Store) -> dict[str, Any]:
    store.register_substrate(_substrate("substrate-a", review=False, context_limit=800))
    store.register_substrate(_substrate("substrate-b", review=True))
    revision = store.create_lineage(
        "lineage-test",
        _state(),
        revision_id="revision-test-1",
        created_at="2026-08-06T00:00:00Z",
    )
    source = store.create_activation(
        "lineage-test",
        revision["revision_id"],
        "substrate-a",
        activation_id="activation-source",
        started_at="2026-08-06T00:01:00Z",
    )
    store.acquire_lease(
        "lineage-test",
        source["activation_id"],
        lease_id="lease-source",
        issued_at="2026-08-06T00:02:00Z",
    )
    fit = evaluate_fit(
        store,
        lineage_id="lineage-test",
        source_revision_id=revision["revision_id"],
        source_substrate_id="substrate-a",
        task_phase="independent-review",
        requirements={
            "capabilities": ["repository_read", "independent_review"],
            "policy_labels": ["local-synthetic"],
            "minimum_context_units": 50,
        },
        fit_decision_id="fit-test",
        decided_at="2026-08-06T00:03:00Z",
    )
    projection = compile_projection(
        store,
        lineage_id="lineage-test",
        source_revision_id=revision["revision_id"],
        target_substrate_id="substrate-b",
        budget_limit=70,
        handoff_reason="task_phase_transition",
        target_responsibility="Independently review P0",
        projection_id="projection-test",
        compiled_at="2026-08-06T00:04:00Z",
    )
    snapshot = prepare_handoff(
        store,
        lineage_id="lineage-test",
        source_activation_id=source["activation_id"],
        fit_decision_id=fit["fit_decision_id"],
        projection_id=projection["projection_id"],
        reason_code="task_phase_transition",
        rationale="Implementation is ready for independent review.",
        handoff_id="handoff-test",
        prepared_at="2026-08-06T00:05:00Z",
    )
    target = store.create_activation(
        "lineage-test",
        revision["revision_id"],
        "substrate-b",
        activation_id="activation-target",
        started_at="2026-08-06T00:06:00Z",
    )
    return {
        "revision": revision,
        "source": source,
        "fit": fit,
        "projection": projection,
        "snapshot": snapshot,
        "target": target,
    }


def _accept(store: Store, prepared: dict[str, Any]) -> dict[str, Any]:
    reconstruction = expected_reconstruction(store, prepared["snapshot"])
    reconstruction["new_inferences"] = ["Review evidence is still required"]
    return resolve_handoff(
        store,
        handoff_id=prepared["snapshot"]["handoff_id"],
        target_activation_id=prepared["target"]["activation_id"],
        reconstruction=reconstruction,
        handoff_result_id="result-test",
        target_lease_id="lease-target",
        resulting_revision_id="revision-test-2",
        resolved_at="2026-08-06T00:07:00Z",
    )


def test_accepted_handoff_transfers_authority_and_verifies(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        assert store.current_authority("lineage-test")["activation_id"] == "activation-source"

        result = _accept(store, prepared)

        assert result["disposition"] == "accepted"
        assert store.current_authority("lineage-test") == {
            "lineage_head_revision_id": "revision-test-2",
            "activation_id": "activation-target",
            "substrate_id": "substrate-b",
            "lease_id": "lease-target",
        }
        assert verify_store(store, "lineage-test")["valid"] is True


def test_duplicate_active_lease_is_rejected_transactionally(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        duplicate = store.create_activation(
            "lineage-test",
            prepared["revision"]["revision_id"],
            "substrate-b",
            activation_id="activation-duplicate",
        )

        with pytest.raises(LeaseConflictError):
            store.acquire_lease(
                "lineage-test", duplicate["activation_id"], lease_id="lease-duplicate"
            )

        active = store.connection.execute(
            "SELECT lease_id FROM leases WHERE status = 'active'"
        ).fetchall()
        assert [row["lease_id"] for row in active] == ["lease-source"]
        assert store.get_activation("activation-duplicate")["state"] == "pending"


def test_preparation_alone_does_not_transfer_authority(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        authority = store.current_authority("lineage-test")

        assert prepared["snapshot"]["source_authority"]["activation_id"] == "activation-source"
        assert authority["activation_id"] == "activation-source"
        assert authority["lease_id"] == "lease-source"


def test_rejected_acceptance_preserves_source_authority(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        reconstruction = expected_reconstruction(store, prepared["snapshot"])
        reconstruction["hard_constraints"] = []

        result = resolve_handoff(
            store,
            handoff_id="handoff-test",
            target_activation_id="activation-target",
            reconstruction=reconstruction,
            handoff_result_id="result-rejected",
        )

        assert result["disposition"] == "rejected"
        assert result["resulting_authority"] is None
        assert store.current_authority("lineage-test")["activation_id"] == "activation-source"
        assert verify_store(store, "lineage-test")["valid"] is True


def test_projection_budgets_differ_without_mutating_revision(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        source_hash = prepared["revision"]["integrity"]["canonical_payload_sha256"]
        source_bytes = store.connection.execute(
            "SELECT payload_json FROM revisions WHERE revision_id = 'revision-test-1'"
        ).fetchone()["payload_json"]
        constrained = compile_projection(
            store,
            lineage_id="lineage-test",
            source_revision_id="revision-test-1",
            target_substrate_id="substrate-b",
            budget_limit=35,
            handoff_reason="task_phase_transition",
            target_responsibility="Independently review P0",
            projection_id="projection-constrained",
        )

        assert (
            constrained["included_sections"]
            != prepared["projection"]["included_sections"]
        )
        assert (
            store.get_revision("revision-test-1")["integrity"]["canonical_payload_sha256"]
            == source_hash
        )
        assert (
            store.connection.execute(
                "SELECT payload_json FROM revisions WHERE revision_id = 'revision-test-1'"
            ).fetchone()["payload_json"]
            == source_bytes
        )


def test_required_continuity_cannot_be_omitted_for_budget(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)

        with pytest.raises(ProjectionBudgetError, match="required continuity"):
            compile_projection(
                store,
                lineage_id="lineage-test",
                source_revision_id=prepared["revision"]["revision_id"],
                target_substrate_id="substrate-b",
                budget_limit=1,
                handoff_reason="task_phase_transition",
                target_responsibility="Review P0",
            )


@pytest.mark.parametrize(
    ("table", "trigger", "id_column", "record_id", "expected_code"),
    (
        (
            "revisions",
            "revisions_no_update",
            "revision_id",
            "revision-test-1",
            "revision_hash_mismatch",
        ),
        (
            "projections",
            "projections_no_update",
            "projection_id",
            "projection-test",
            "projection_hash_mismatch",
        ),
        (
            "handoffs",
            "handoffs_no_update",
            "handoff_id",
            "handoff-test",
            "handoff_hash_mismatch",
        ),
        (
            "handoff_results",
            "handoff_results_no_update",
            "handoff_result_id",
            "result-test",
            "handoff_result_hash_mismatch",
        ),
    ),
)
def test_tampering_with_immutable_records_is_detected(
    tmp_path: Path,
    table: str,
    trigger: str,
    id_column: str,
    record_id: str,
    expected_code: str,
) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        _accept(store, prepared)
        row = store.connection.execute(
            f"SELECT payload_json FROM {table} WHERE {id_column} = ?", (record_id,)
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload["schema_version"] = 999
        with store.connection:
            store.connection.execute(f"DROP TRIGGER {trigger}")
            store.connection.execute(
                f"UPDATE {table} SET payload_json = ? WHERE {id_column} = ?",
                (json.dumps(payload), record_id),
            )

        verification = verify_store(store, "lineage-test")

        assert verification["valid"] is False
        assert expected_code in {error["code"] for error in verification["errors"]}


def test_result_requires_existing_matching_snapshot_and_target(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        prepared = _prepared(store)
        reconstruction = expected_reconstruction(store, prepared["snapshot"])

        with pytest.raises(NotFoundError, match="handoffs record"):
            resolve_handoff(
                store,
                handoff_id="handoff-missing",
                target_activation_id="activation-target",
                reconstruction=reconstruction,
            )

        unrelated = store.create_activation(
            "lineage-test",
            "revision-test-1",
            "substrate-a",
            activation_id="activation-unrelated",
        )
        with pytest.raises(HandoffError, match="does not match"):
            resolve_handoff(
                store,
                handoff_id="handoff-test",
                target_activation_id=unrelated["activation_id"],
                reconstruction=reconstruction,
            )
        assert store.current_authority("lineage-test")["activation_id"] == "activation-source"


def test_demo_exports_inspectable_artifacts_and_verifies(tmp_path: Path) -> None:
    payload = run_demo(tmp_path)

    assert payload["lease_holder_before"] == "activation-source"
    assert payload["lease_holder_after_prepare"] == "activation-source"
    assert payload["lease_holder_after"] == "activation-target"
    assert payload["verification"]["valid"] is True
    assert payload["artifact_paths"]
    assert all((tmp_path / path).is_file() for path in payload["artifact_paths"])
    with Store(tmp_path) as store:
        inspection = inspect_lineage(store, "demo-lineage")
        assert inspection["integrity"]["valid"] is True
        assert inspection["lineage_head"]["revision_id"] == "revision-demo-0004"


def test_exported_artifact_tampering_is_detected(tmp_path: Path) -> None:
    payload = run_demo(tmp_path)
    artifact = tmp_path / payload["artifact_paths"][0]
    artifact.write_text("{}\n", encoding="utf-8")

    with Store(tmp_path) as store:
        verification = verify_store(store, "demo-lineage")

    assert verification["valid"] is False
    assert "artifact_hash_mismatch" in {
        error["code"] for error in verification["errors"]
    }


def test_empty_database_migration_is_repeatable_and_idempotent(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as first:
        assert first.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        table_count = first.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()[0]

    with Store(tmp_path) as second:
        assert second.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert (
            second.connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
            == table_count
        )

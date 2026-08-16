from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from torc.cli import main
from torc.context import (
    ContextError,
    attach_context,
    checkpoint_context,
    detach_context,
    hydrate_context,
)
from torc.operator import (
    branch_operator_lineage,
    create_operator_lineage,
    prepare_operator_handoff,
    resolve_operator_handoff,
)
from torc.store import Store


def _state(label: str = "current") -> dict[str, Any]:
    return {
        "identity": {"label": f"context-{label}"},
        "self_model": {
            "role": "Continue the root session",
            "settled_decisions": ["OGMI owns shared continuity records"],
            "methods": ["Hydrate through a verified Torc projection"],
        },
        "goals": ["Preserve useful root-session continuity"],
        "commitments": ["Keep canonical history append-only"],
        "constraints": ["Do not transfer authority during compaction"],
        "open_work": ["Finish the root vertical slice"],
        "uncertainties": [],
        "artifact_refs": ["artifact-context-plan"],
        "memory_refs": [],
    }


def _substrate() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": "codex-root",
        "label": "Codex root session",
        "adapter": "codex",
        "capabilities": ["repository_read", "repository_write"],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": ["implementation"],
    }


def _successor_substrate() -> dict[str, Any]:
    substrate = _substrate()
    substrate.update(
        {
            "substrate_id": "codex-successor",
            "label": "Codex successor session",
        }
    )
    return substrate


def _handoff_plan() -> dict[str, Any]:
    return {
        "target_substrate": _successor_substrate(),
        "target_activation_id": "activation-successor",
        "task_phase": "implementation-continuation",
        "requirements": {
            "capabilities": ["repository_read", "repository_write"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 100,
        },
        "budget_limit": 1000,
        "target_responsibility": "Continue the accepted implementation handoff",
        "reason_code": "model_succession",
        "rationale": "The operator selected a successor activation.",
    }


class StubOgmi:
    def __init__(self, *, digest: str = "a" * 64) -> None:
        self.digest = digest

    def resolve(self, **kwargs: object) -> dict[str, Any]:
        return {
            "checkpoint_id": "checkpoint-driver-01",
            "checkpoint_path": str(kwargs["checkpoint_path"]),
            "checkpoint_sha256": self.digest,
            "checkpoint": {
                "record_type": "checkpoint",
                "schema_version": "0.1",
                "id": "checkpoint-driver-01",
                "run_id": kwargs["expected_run_id"],
                "assignment_id": kwargs["expected_assignment_id"],
                "reason": "context_threshold",
                "objective": "Continue the bounded implementation.",
                "next_action": "Resume the next verified step.",
            },
            "orientation": {
                "node": {"id": kwargs["orientation_spine_id"]},
                "validation": {"errors": 0},
            },
        }


def _bootstrap(store: Store) -> dict[str, Any]:
    return create_operator_lineage(
        store,
        lineage_id="lineage-root",
        canonical_state=_state(),
        substrate=_substrate(),
        activation_id="activation-root",
    )


def _attach_ogmi(store: Store, tmp_path: Path, ogmi: StubOgmi) -> dict[str, Any]:
    project = tmp_path / "ogmi-project"
    project.mkdir(exist_ok=True)
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("{}", encoding="utf-8")
    return attach_context(
        store,
        harness="codex",
        repository_identity="lugos",
        runtime_session_ref="session-root",
        lineage_id="lineage-root",
        activation_id="activation-root",
        continuity_mode="ogmi_workgraph",
        ogmi_project_path=project,
        ogmi_run_id="run-01",
        ogmi_assignment_id="assignment-driver-01",
        ogmi_orientation_spine_id="project.active",
        ogmi_checkpoint_path=checkpoint,
        ogmi=ogmi,
    )


def test_store_migrates_and_exact_binding_rejects_duplicates(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        binding = attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        authority = store.current_authority("lineage-root")

        assert binding["continuity_mode"] == "torc_standalone"
        assert store.get_context_binding("codex", "session-root", "lugos")[
            "binding_id"
        ] == binding["binding_id"]
        assert int(store.connection.execute("PRAGMA user_version").fetchone()[0]) == 2
        with pytest.raises(ContextError, match="already bound"):
            attach_context(
                store,
                harness="codex",
                repository_identity="lugos",
                runtime_session_ref="session-root",
                lineage_id="lineage-root",
                activation_id="activation-root",
                continuity_mode="torc_standalone",
            )
        assert store.current_authority("lineage-root") == authority


def test_existing_version_one_store_is_preserved_by_additive_migration(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
    connection = sqlite3.connect(tmp_path / "torc.sqlite3")
    connection.execute("DROP TABLE context_bindings")
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    with Store(tmp_path) as migrated:
        assert migrated.get_lineage("lineage-root")["head_revision_id"] == created[
            "revision_id"
        ]
        assert int(migrated.connection.execute("PRAGMA user_version").fetchone()[0]) == 2
        assert migrated.context_bindings_for_session("codex", "session-root") == []


def test_standalone_checkpoint_and_hydrate_preserve_authority(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        authority_before = store.current_authority("lineage-root")
        result = checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("checkpoint"),
            budget_limit=1000,
        )
        authority_after = store.current_authority("lineage-root")

    with Store(tmp_path, read_only=True) as store:
        hydrated = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
        )

    assert result["revision_id"] != created["revision_id"]
    assert authority_before["activation_id"] == authority_after["activation_id"]
    assert authority_before["lease_id"] == authority_after["lease_id"]
    assert hydrated["status"] == "ready"
    assert hydrated["continuity"] == {
        "mode": "torc_standalone",
        "limitation": "No shared OGMI workgraph checkpoint is attached.",
    }
    assert '"ogmi_checkpoint"' not in hydrated["additional_context"]


def test_ogmi_checkpoint_references_hash_and_hydrates_bounded_view(tmp_path: Path) -> None:
    ogmi = StubOgmi()
    with Store(tmp_path) as store:
        _bootstrap(store)
        _attach_ogmi(store, tmp_path, ogmi)
        authority_before = store.current_authority("lineage-root")
        result = checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("checkpoint"),
            budget_limit=1000,
            ogmi=ogmi,
        )
        revision = store.get_revision(result["revision_id"])
        authority_after = store.current_authority("lineage-root")

    with Store(tmp_path, read_only=True) as store:
        hydrated = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            ogmi=ogmi,
        )

    assert revision["evidence_refs"] == ["ogmi-checkpoint:sha256:" + "a" * 64]
    assert authority_after["activation_id"] == authority_before["activation_id"]
    assert authority_after["lease_id"] == authority_before["lease_id"]
    assert hydrated["status"] == "ready"
    assert hydrated["continuity"] == {
        "mode": "ogmi_workgraph",
        "checkpoint_id": "checkpoint-driver-01",
        "checkpoint_sha256": "a" * 64,
        "orientation_spine_id": "project.active",
        "run_id": "run-01",
        "assignment_id": "assignment-driver-01",
    }
    assert len(hydrated["additional_context"].encode()) <= 65_536


def test_checkpoint_delegates_once_to_existing_operator_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import torc.context as context_module

    with Store(tmp_path) as store:
        _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        original = context_module.checkpoint_operator_lineage
        calls = 0

        def counted(*args: object, **kwargs: object) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(context_module, "checkpoint_operator_lineage", counted)
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("checkpoint"),
            budget_limit=1000,
        )

        assert calls == 1
        assert len(store.lineage_revisions("lineage-root")) == 2


def test_hydrate_fails_closed_for_wrong_repository_stale_authority_and_tampering(
    tmp_path: Path,
) -> None:
    ogmi = StubOgmi()
    with Store(tmp_path) as store:
        _bootstrap(store)
        _attach_ogmi(store, tmp_path, ogmi)
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("checkpoint"),
            budget_limit=1000,
            ogmi=ogmi,
        )

    with Store(tmp_path, read_only=True) as store:
        wrong_repository = hydrate_context(
            store,
            harness="codex",
            repository_identity="other",
            runtime_session_ref="session-root",
            ogmi=ogmi,
        )
        tampered_ogmi = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            ogmi=StubOgmi(digest="b" * 64),
        )

    assert wrong_repository["status"] == "stale"
    assert tampered_ogmi["status"] == "invalid"

    with Store(tmp_path) as store:
        store.connection.execute(
            "UPDATE activations SET state = 'suspended' WHERE activation_id = ?",
            ("activation-root",),
        )
        store.connection.commit()
    with Store(tmp_path, read_only=True) as store:
        stale = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            ogmi=ogmi,
        )
    assert stale["status"] == "stale"


def test_insufficient_budget_is_atomic(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        head_before = store.get_lineage("lineage-root")["head_revision_id"]
        with pytest.raises(Exception, match="budget"):
            checkpoint_context(
                store,
                harness="codex",
                repository_identity="lugos",
                runtime_session_ref="session-root",
                canonical_state=_state("checkpoint"),
                budget_limit=1,
            )
        assert store.get_lineage("lineage-root")["head_revision_id"] == head_before
        assert len(store.lineage_revisions("lineage-root")) == 1


def test_hydrate_rejects_a_tampered_projection(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        result = checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("checkpoint"),
            budget_limit=1000,
        )
        row = store.connection.execute(
            "SELECT payload_json FROM projections WHERE projection_id = ?",
            (result["projection_id"],),
        ).fetchone()
        projection = json.loads(row["payload_json"])
        projection["budget"]["limit"] += 1
        store.connection.execute("DROP TRIGGER projections_no_update")
        store.connection.execute(
            "UPDATE projections SET payload_json = ? WHERE projection_id = ?",
            (json.dumps(projection), result["projection_id"]),
        )
        store.connection.commit()

    with Store(tmp_path, read_only=True) as store:
        hydrated = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
        )

    assert hydrated["status"] == "invalid"


def test_detach_removes_only_the_exact_adapter_binding(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        binding = attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        store.connection.execute(
            "UPDATE activations SET state = 'suspended' WHERE activation_id = ?",
            ("activation-root",),
        )
        store.connection.commit()
        counts_before = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("lineages", "revisions", "activations", "leases")
        }

        result = detach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
        )
        counts_after = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("lineages", "revisions", "activations", "leases")
        }

        assert result == {
            "schema_version": 1,
            "status": "detached",
            "binding_id": binding["binding_id"],
            "harness": "codex",
            "repository_identity": "lugos",
            "runtime_session_ref": "session-root",
            "lineage_id": "lineage-root",
            "activation_id": "activation-root",
            "continuity_mode": "torc_standalone",
        }
        assert counts_after == counts_before
        assert store.context_bindings_for_session("codex", "session-root") == []


def test_detach_fails_closed_on_unbound_or_repository_mismatch(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )

        with pytest.raises(ContextError, match="exact runtime context binding"):
            detach_context(
                store,
                harness="codex",
                repository_identity="other",
                runtime_session_ref="session-root",
            )
        with pytest.raises(ContextError, match="exact runtime context binding"):
            detach_context(
                store,
                harness="codex",
                repository_identity="lugos",
                runtime_session_ref="session-other",
            )
        assert len(store.context_bindings_for_session("codex", "session-root")) == 1


def test_observer_hydrate_is_non_authoritative_and_omits_ogmi_assignment_body(
    tmp_path: Path,
) -> None:
    ogmi = StubOgmi()
    tables = (
        "lineages",
        "revisions",
        "activations",
        "leases",
        "handoffs",
        "handoff_results",
        "authority_transitions",
        "context_bindings",
    )
    with Store(tmp_path) as store:
        _bootstrap(store)
        _attach_ogmi(store, tmp_path, ogmi)
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("observer-parent"),
            budget_limit=1000,
            ogmi=ogmi,
        )
        counts_before = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }

    with Store(tmp_path, read_only=True) as store:
        observed = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            request_mode="observer",
            ogmi=ogmi,
        )
        assert store.connection.total_changes == 0

    with Store(tmp_path) as store:
        counts_after = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }

    assert observed["status"] == "ready"
    assert observed["request_mode"] == "observer"
    assert observed["authority"] == {
        "kind": "observer",
        "lineage_authority": False,
        "checkpoint_allowed": False,
    }
    assert observed["continuity"] == {
        "mode": "ogmi_workgraph",
        "parent_checkpoint_id": "checkpoint-driver-01",
        "parent_checkpoint_sha256": "a" * 64,
    }
    assert '"torc_projection"' in observed["additional_context"]
    serialized = json.dumps(observed, sort_keys=True)
    for forbidden in (
        "assignment-driver-01",
        '"ogmi_checkpoint"',
        '"ogmi_orientation"',
        '"lease_id"',
    ):
        assert forbidden not in serialized
    assert counts_after == counts_before


def test_successor_hydrate_requires_an_accepted_handoff_to_current_activation(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("ordinary-root"),
            budget_limit=1000,
        )
    with Store(tmp_path, read_only=True) as store:
        not_a_successor = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            request_mode="successor",
        )
    assert not_a_successor["status"] == "invalid"

    accepted_dir = tmp_path / "accepted"
    with Store(accepted_dir) as store:
        source = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="lineage-root",
            source_activation_id=source["activation_id"],
            plan=_handoff_plan(),
        )
        reconstruction = json.loads(
            (store.state_dir / prepared["reconstruction_template_path"]).read_text(
                encoding="utf-8"
            )
        )
        resolved = resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=reconstruction,
        )
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-successor",
            lineage_id="lineage-root",
            activation_id="activation-successor",
            continuity_mode="torc_standalone",
        )
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-successor",
            canonical_state=_state("accepted-successor"),
            budget_limit=1000,
        )

    with Store(accepted_dir, read_only=True) as store:
        successor = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-successor",
            request_mode="successor",
        )

    assert successor["status"] == "ready"
    assert successor["request_mode"] == "successor"
    assert successor["authority"] == {
        "kind": "successor",
        "lineage_authority": True,
        "checkpoint_allowed": True,
    }
    assert successor["authority_proof"] == {
        "handoff_id": prepared["handoff_id"],
        "handoff_result_id": resolved["handoff_result_id"],
    }
    assert created["activation_id"] == "activation-root"


def test_branch_hydrate_requires_an_explicit_authoritative_branch(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        branch = branch_operator_lineage(
            store,
            source_lineage_id="lineage-root",
            source_activation_id=source["activation_id"],
            expected_source_revision_id=source["revision_id"],
            child_lineage_id="lineage-branch",
            child_activation_id="activation-branch",
            child_substrate=_successor_substrate(),
            operator_ref="operator-branch",
            target_assignment_ref="assignment-branch",
            rationale="Create an explicit durable branch.",
            evidence_refs=["evidence-branch"],
        )
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-branch",
            lineage_id="lineage-branch",
            activation_id="activation-branch",
            continuity_mode="torc_standalone",
        )
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-branch",
            canonical_state=_state("branch"),
            budget_limit=1000,
        )

    with Store(tmp_path, read_only=True) as store:
        branch_context = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-branch",
            request_mode="branch",
        )

    assert branch_context["status"] == "ready"
    assert branch_context["request_mode"] == "branch"
    assert branch_context["authority"] == {
        "kind": "branch",
        "lineage_authority": True,
        "checkpoint_allowed": True,
    }
    assert branch_context["authority_proof"] == {
        "source_lineage_id": "lineage-root",
        "source_revision_id": source["revision_id"],
        "branch_revision_id": branch["child_revision_id"],
    }


def test_root_request_mode_preserves_default_payload_and_unknown_mode_fails_closed(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("root"),
            budget_limit=1000,
        )

    with Store(tmp_path, read_only=True) as store:
        default = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
        )
        explicit = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            request_mode="root",
        )
        invalid = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            request_mode="invented",
        )

    assert explicit == default
    assert invalid["status"] == "invalid"


def test_hydrate_uses_one_snapshot_when_another_connection_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Store(tmp_path) as store:
        store.connection.execute("PRAGMA journal_mode = WAL")
        _bootstrap(store)
        attach_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            lineage_id="lineage-root",
            activation_id="activation-root",
            continuity_mode="torc_standalone",
        )
        original_checkpoint = checkpoint_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
            canonical_state=_state("before-concurrent-write"),
            budget_limit=1000,
        )

    with Store(tmp_path) as writer, Store(tmp_path, read_only=True) as reader:
        get_binding = reader.get_context_binding

        def get_binding_then_checkpoint(
            harness: str, runtime_session_ref: str, repository_identity: str
        ) -> dict[str, Any]:
            binding = get_binding(harness, runtime_session_ref, repository_identity)
            checkpoint_context(
                writer,
                harness="codex",
                repository_identity="lugos",
                runtime_session_ref="session-root",
                canonical_state=_state("after-concurrent-write"),
                budget_limit=1000,
            )
            return binding

        monkeypatch.setattr(reader, "get_context_binding", get_binding_then_checkpoint)
        hydrated = hydrate_context(
            reader,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-root",
        )
        latest_binding = writer.get_context_binding("codex", "session-root", "lugos")

        assert reader.connection.in_transaction is False

    assert hydrated["status"] == "ready"
    assert hydrated["source_revision_id"] == original_checkpoint["revision_id"]
    assert hydrated["projection_id"] == original_checkpoint["projection_id"]
    assert latest_binding["source_revision_id"] != hydrated["source_revision_id"]


@pytest.mark.parametrize("request_mode", ["root", "observer", "successor", "branch"])
def test_all_request_modes_remain_non_ready_without_an_exact_binding(
    tmp_path: Path, request_mode: str
) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
    with Store(tmp_path, read_only=True) as store:
        result = hydrate_context(
            store,
            harness="codex",
            repository_identity="lugos",
            runtime_session_ref="session-unbound",
            request_mode=request_mode,
        )

    assert result["status"] == "unbound"


def test_context_cli_round_trip_uses_exact_lookup_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(_state("cli")), encoding="utf-8")

    assert (
        main(
            [
                "context",
                "attach",
                "--state-dir",
                str(tmp_path),
                "--harness",
                "codex",
                "--repository-id",
                "lugos",
                "--runtime-session",
                "session-root",
                "--lineage",
                "lineage-root",
                "--activation",
                "activation-root",
                "--mode",
                "torc_standalone",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "context",
                "checkpoint",
                "--state-dir",
                str(tmp_path),
                "--harness",
                "codex",
                "--repository-id",
                "lugos",
                "--runtime-session",
                "session-root",
                "--state-file",
                str(state_file),
                "--budget-limit",
                "1000",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "context",
                "hydrate",
                "--state-dir",
                str(tmp_path),
                "--harness",
                "codex",
                "--repository-id",
                "lugos",
                "--runtime-session",
                "session-root",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ready"
    assert payload["activation_id"] == "activation-root"

    assert (
        main(
            [
                "context",
                "hydrate",
                "--state-dir",
                str(tmp_path),
                "--harness",
                "codex",
                "--repository-id",
                "lugos",
                "--runtime-session",
                "session-root",
                "--request-mode",
                "observer",
                "--json",
            ]
        )
        == 0
    )
    observer = json.loads(capsys.readouterr().out)
    assert observer["request_mode"] == "observer"
    assert observer["authority"]["lineage_authority"] is False

    assert (
        main(
            [
                "context",
                "detach",
                "--state-dir",
                str(tmp_path),
                "--harness",
                "codex",
                "--repository-id",
                "lugos",
                "--runtime-session",
                "session-root",
                "--json",
            ]
        )
        == 0
    )
    detached = json.loads(capsys.readouterr().out)
    assert detached["schema_version"] == 1
    assert detached["status"] == "detached"

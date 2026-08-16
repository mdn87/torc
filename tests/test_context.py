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
from torc.operator import create_operator_lineage
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

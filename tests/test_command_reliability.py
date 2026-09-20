from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from torc.cli import main
from torc.errors import LeaseConflictError, NotFoundError, TorcError
from torc.operator import (
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
)
from torc.store import Store
from torc.verify import verify_store


def _state() -> dict[str, Any]:
    return {
        "identity": {"label": "Reliability lineage"},
        "self_model": {"role": "Exercise routine operator commands"},
        "goals": ["Keep routine operations dependable"],
        "commitments": ["Keep canonical history append-only"],
        "constraints": ["Do not edit the parent repository"],
        "open_work": ["Harden lineage creation"],
        "uncertainties": [],
        "artifact_refs": [],
        "memory_refs": [],
    }


def _substrate() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": "local-session",
        "label": "Local operator session",
        "adapter": "manual",
        "capabilities": ["repository_read"],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 1000},
        "task_affinities": ["implementation"],
    }


def _create(store: Store, lineage_id: str, **overrides: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "lineage_id": lineage_id,
        "canonical_state": _state(),
        "substrate": _substrate(),
    }
    arguments.update(overrides)
    return create_operator_lineage(store, **arguments)


def _table_counts(store: Store) -> dict[str, int]:
    return {
        table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("lineages", "revisions", "substrates", "activations", "leases")
    }


def _write(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "canonical_state",
    [
        {},
        {**_state(), "goals": "not-a-list"},
        {**_state(), "open_work": [1]},
        {**_state(), "artifact_refs": ["not a valid id"]},
        {**_state(), "identity": []},
        {**_state(), "unexpected": True},
    ],
)
def test_create_rejects_invalid_state_before_any_write(
    tmp_path: Path, canonical_state: dict[str, Any]
) -> None:
    with Store(tmp_path) as store:
        with pytest.raises(TorcError):
            _create(store, "lineage-invalid", canonical_state=canonical_state)

        assert set(_table_counts(store).values()) == {0}


@pytest.mark.parametrize(
    "substrate",
    [
        {},
        {**_substrate(), "substrate_id": "not a valid id"},
        {**_substrate(), "capabilities": "repository_read"},
        {**_substrate(), "context_budget": {"unit": "words"}},
        {**_substrate(), "context_budget": {"unit": "words", "limit": 0}},
    ],
)
def test_create_rejects_invalid_substrate_before_any_write(
    tmp_path: Path, substrate: dict[str, Any]
) -> None:
    with Store(tmp_path) as store:
        with pytest.raises(TorcError):
            _create(store, "lineage-invalid", substrate=substrate)

        assert set(_table_counts(store).values()) == {0}


@pytest.mark.parametrize("field", ["lineage_id", "activation_id"])
def test_create_rejects_invalid_identifiers(tmp_path: Path, field: str) -> None:
    with Store(tmp_path) as store:
        arguments = {"lineage_id": "lineage-ok", "activation_id": "activation-ok"}
        arguments[field] = "not a valid id"
        lineage_id = arguments.pop("lineage_id")
        with pytest.raises(TorcError):
            _create(store, lineage_id, **arguments)

        assert set(_table_counts(store).values()) == {0}


def test_checkpoint_rejects_invalid_state_and_keeps_head(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _create(store, "lineage-a", activation_id="activation-a")

        with pytest.raises(TorcError):
            checkpoint_operator_lineage(
                store,
                lineage_id="lineage-a",
                activation_id="activation-a",
                canonical_state={},
            )

        status = operator_lineage_status(store, "lineage-a")
        assert status["head_revision_id"] == created["revision_id"]
        assert status["revision_count"] == 1


def test_duplicate_activation_leaves_no_partial_lineage_and_retry_succeeds(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        _create(store, "lineage-a", activation_id="activation-shared")
        before = _table_counts(store)

        with pytest.raises(LeaseConflictError, match="activation already exists"):
            _create(store, "lineage-b", activation_id="activation-shared")

        assert _table_counts(store) == before
        with pytest.raises(NotFoundError):
            store.get_lineage("lineage-b")

        retried = _create(store, "lineage-b", activation_id="activation-b")

        assert retried["ok"] is True
        authority = store.current_authority("lineage-b")
        assert authority["activation_id"] == "activation-b"
        assert verify_store(store)["valid"] is True


def test_duplicate_lineage_is_a_clear_error(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _create(store, "lineage-a", activation_id="activation-a")
        before = _table_counts(store)

        with pytest.raises(TorcError, match="lineage already exists"):
            _create(store, "lineage-a", activation_id="activation-other")

        assert _table_counts(store) == before


def test_failed_create_does_not_register_a_new_substrate(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _create(store, "lineage-a", activation_id="activation-shared")
        other = {**_substrate(), "substrate_id": "other-session"}

        with pytest.raises(LeaseConflictError):
            _create(
                store,
                "lineage-b",
                substrate=other,
                activation_id="activation-shared",
            )

        assert [item["substrate_id"] for item in store.list_substrates()] == [
            "local-session"
        ]


def test_cli_create_reports_invalid_input_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_dir = tmp_path / "state"
    arguments = [
        "lineage",
        "create",
        "--state-dir",
        str(state_dir),
        "--lineage",
        "lineage-bad",
        "--state-file",
        str(_write(tmp_path / "empty.json", {})),
        "--substrate-file",
        str(_write(tmp_path / "substrate.json", _substrate())),
        "--json",
    ]

    assert main(arguments) == 1
    failure = json.loads(capsys.readouterr().out)

    assert failure["ok"] is False
    assert "canonical state" in failure["detail"]


def test_cli_create_reports_duplicate_activation_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_dir = tmp_path / "state"
    shared = [
        "--state-dir",
        str(state_dir),
        "--state-file",
        str(_write(tmp_path / "state.json", _state())),
        "--substrate-file",
        str(_write(tmp_path / "substrate.json", _substrate())),
        "--activation-id",
        "activation-shared",
        "--json",
    ]

    assert main(["lineage", "create", "--lineage", "lineage-a", *shared]) == 0
    capsys.readouterr()
    assert main(["lineage", "create", "--lineage", "lineage-b", *shared]) == 1
    failure = json.loads(capsys.readouterr().out)

    assert failure == {
        "ok": False,
        "error": "LeaseConflictError",
        "detail": "activation already exists: activation-shared",
    }


@pytest.mark.parametrize(
    "command",
    [
        ["verify"],
        ["inspect", "--lineage", "lineage-a"],
        ["lineage", "status", "--lineage", "lineage-a"],
        ["lineage", "explain", "--lineage", "lineage-a"],
    ],
)
def test_inspection_commands_do_not_create_missing_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    missing = tmp_path / "does-not-exist"

    assert main([*command, "--state-dir", str(missing), "--json"]) == 1
    failure = json.loads(capsys.readouterr().out)

    assert failure["ok"] is False
    assert failure["error"] == "NotFoundError"
    assert not missing.exists()


def test_inspection_commands_refuse_to_migrate_an_older_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with Store(tmp_path) as store:
        _create(store, "lineage-a", activation_id="activation-a")
    connection = sqlite3.connect(tmp_path / "torc.sqlite3")
    connection.execute("PRAGMA user_version = 3")
    connection.commit()
    connection.close()

    assert main(["verify", "--state-dir", str(tmp_path), "--json"]) == 1
    failure = json.loads(capsys.readouterr().out)

    assert failure["ok"] is False
    assert failure["error"] == "SchemaVersionError"
    assert "read-only commands never migrate" in failure["detail"]
    connection = sqlite3.connect(tmp_path / "torc.sqlite3")
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    connection.close()


def test_inspection_commands_still_verify_existing_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with Store(tmp_path) as store:
        _create(store, "lineage-a", activation_id="activation-a")

    assert main(["verify", "--state-dir", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["lineages_checked"] == ["lineage-a"]
    status = ["lineage", "status", "--state-dir", str(tmp_path), "--lineage", "lineage-a"]
    assert main([*status, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["revision_count"] == 1

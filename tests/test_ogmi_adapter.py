from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from torc.ogmi_adapter import OgmiAdapter, OgmiAdapterError


def _checkpoint(path: Path) -> dict[str, object]:
    record: dict[str, object] = {
        "record_type": "checkpoint",
        "schema_version": "0.1",
        "id": "checkpoint-driver-01",
        "run_id": "run-01",
        "assignment_id": "assignment-driver-01",
        "reason": "context_threshold",
        "objective": "Continue the bounded implementation.",
        "pinned_state": {},
        "workspace": {},
        "ledger": {},
        "completed_gates": [],
        "pending_gates": [],
        "artifacts": [],
        "next_reads": [],
        "next_action": "Resume the next verified step.",
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def _canonical_digest(record: dict[str, object]) -> str:
    content = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def _successful_output(
    argv: list[str], *, digest: str, project_records: int = 4
) -> tuple[int, bytes, bytes, bool]:
    command = argv[3]
    if command == "validate":
        records = 1 if Path(argv[4]).is_file() else project_records
        stdout = json.dumps({"records": records, "errors": 0, "warnings": 0}).encode()
    elif command == "hash":
        stdout = f"sha256:{digest}\n".encode()
    else:
        stdout = json.dumps(
            {
                "node": {"id": "project.active"},
                "validation": {"errors": 0, "warnings": 0, "issues": []},
            }
        ).encode()
    return 0, stdout, b"", False


def test_adapter_validates_project_graph_and_exact_checkpoint_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    checkpoint_path = project_path / "runs" / "checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True)
    record = _checkpoint(checkpoint_path)
    digest = _canonical_digest(record)
    calls: list[list[str]] = []
    adapter = OgmiAdapter()

    def fake_run(argv: list[str]) -> tuple[int, bytes, bytes, bool]:
        calls.append(argv)
        return _successful_output(argv, digest=digest)

    monkeypatch.setattr(adapter, "_bounded_process", fake_run)
    resolved = adapter.resolve(
        checkpoint_path=checkpoint_path,
        project_path=project_path,
        orientation_spine_id="project.active",
        expected_run_id="run-01",
        expected_assignment_id="assignment-driver-01",
    )

    assert [call[2:] for call in calls] == [
        ["ogmi", "validate", str(project_path.resolve()), "--json"],
        ["ogmi", "validate", str(checkpoint_path.resolve()), "--json"],
        ["ogmi", "hash", str(checkpoint_path.resolve())],
        ["ogmi", "orient", str(project_path.resolve()), "project.active"],
    ]
    assert resolved["checkpoint_id"] == "checkpoint-driver-01"
    assert resolved["checkpoint"] == record
    assert resolved["checkpoint_sha256"] == digest
    assert resolved["orientation"]["node"]["id"] == "project.active"


def test_adapter_rejects_checkpoint_outside_selected_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    checkpoint_path = tmp_path / "outside-checkpoint.json"
    record = _checkpoint(checkpoint_path)
    adapter = OgmiAdapter()
    monkeypatch.setattr(
        adapter,
        "_bounded_process",
        lambda argv: _successful_output(argv, digest=_canonical_digest(record)),
    )

    with pytest.raises(OgmiAdapterError, match="selected project"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )


def test_adapter_rejects_invalid_selected_project_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    checkpoint_path = project_path / "checkpoint.json"
    project_path.mkdir()
    record = _checkpoint(checkpoint_path)
    digest = _canonical_digest(record)
    adapter = OgmiAdapter()

    def invalid_project(argv: list[str]) -> tuple[int, bytes, bytes, bool]:
        if argv[3] == "validate" and Path(argv[4]).is_dir():
            return 0, b'{"records": 4, "errors": 1}', b"", False
        return _successful_output(argv, digest=digest)

    monkeypatch.setattr(adapter, "_bounded_process", invalid_project)
    with pytest.raises(OgmiAdapterError, match="selected project graph"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )


def test_adapter_rejects_hash_that_does_not_match_exact_checkpoint_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    checkpoint_path = project_path / "checkpoint.json"
    project_path.mkdir()
    _checkpoint(checkpoint_path)
    adapter = OgmiAdapter()
    monkeypatch.setattr(
        adapter,
        "_bounded_process",
        lambda argv: _successful_output(argv, digest="b" * 64),
    )

    with pytest.raises(OgmiAdapterError, match="exact checkpoint value"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )


def test_adapter_rejects_checkpoint_bytes_changing_during_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    checkpoint_path = project_path / "checkpoint.json"
    project_path.mkdir()
    record = _checkpoint(checkpoint_path)
    digest = _canonical_digest(record)
    adapter = OgmiAdapter()
    mutated = False

    def mutate_after_first_read(
        argv: list[str],
    ) -> tuple[int, bytes, bytes, bool]:
        nonlocal mutated
        output = _successful_output(argv, digest=digest)
        if not mutated:
            changed = dict(record)
            changed["objective"] = "Changed while the adapter was resolving."
            checkpoint_path.write_text(json.dumps(changed), encoding="utf-8")
            mutated = True
        return output

    monkeypatch.setattr(adapter, "_bounded_process", mutate_after_first_read)
    with pytest.raises(OgmiAdapterError, match="changed during resolution"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )


@pytest.mark.parametrize(
    ("expected_run", "expected_assignment", "match"),
    [
        ("run-other", "assignment-driver-01", "run identity"),
        ("run-01", "assignment-other", "assignment identity"),
    ],
)
def test_adapter_rejects_binding_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expected_run: str,
    expected_assignment: str,
    match: str,
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    checkpoint_path = project_path / "checkpoint.json"
    _checkpoint(checkpoint_path)

    adapter = OgmiAdapter()

    def fake_run(argv: list[str]) -> tuple[int, bytes, bytes, bool]:
        if argv[3] == "validate":
            output = b'{"records": 1, "errors": 0}'
        elif argv[3] == "hash":
            output = ("sha256:" + "a" * 64).encode()
        else:
            output = b'{"node": {"id": "project.active"}, "validation": {"errors": 0}}'
        return 0, output, b"", False

    monkeypatch.setattr(adapter, "_bounded_process", fake_run)
    with pytest.raises(OgmiAdapterError, match=match):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id=expected_run,
            expected_assignment_id=expected_assignment,
        )


def test_adapter_fails_closed_on_invalid_timeout_and_oversized_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    checkpoint_path = project_path / "checkpoint.json"
    _checkpoint(checkpoint_path)
    adapter = OgmiAdapter(timeout_seconds=1, max_output_bytes=4096)

    monkeypatch.setattr(
        adapter,
        "_bounded_process",
        lambda argv: (1, b'{"errors": 1}', b"invalid", False),
    )
    with pytest.raises(OgmiAdapterError, match="validate failed"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )

    def timeout(argv: list[str]) -> tuple[int, bytes, bytes, bool]:
        raise subprocess.TimeoutExpired(argv, 1)

    monkeypatch.setattr(adapter, "_bounded_process", timeout)
    with pytest.raises(OgmiAdapterError, match="timed out"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )

    monkeypatch.setattr(adapter, "_bounded_process", lambda argv: (0, b"x", b"", True))
    with pytest.raises(OgmiAdapterError, match="output limit"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )


def test_adapter_rejects_wrong_version_and_orientation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    checkpoint_path = project_path / "checkpoint.json"
    checkpoint = _checkpoint(checkpoint_path)
    checkpoint["schema_version"] = "9.9"
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

    adapter = OgmiAdapter()
    monkeypatch.setattr(
        adapter,
        "_bounded_process",
        lambda argv: (
            0,
            (
                b'{"records": 1, "errors": 0}'
                if argv[3] == "validate"
                else ("sha256:" + "a" * 64).encode()
                if argv[3] == "hash"
                else b'{"node": {"id": "wrong"}, "validation": {"errors": 0}}'
            ),
            b"",
            False,
        ),
    )
    with pytest.raises(OgmiAdapterError, match="schema version"):
        adapter.resolve(
            checkpoint_path=checkpoint_path,
            project_path=project_path,
            orientation_spine_id="project.active",
            expected_run_id="run-01",
            expected_assignment_id="assignment-driver-01",
        )


def test_bounded_process_kills_before_retaining_more_than_ceiling() -> None:
    adapter = OgmiAdapter(timeout_seconds=2, max_output_bytes=1024)

    returncode, stdout, stderr, overflow = adapter._bounded_process(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"]
    )

    assert returncode != 0
    assert overflow is True
    assert len(stdout) + len(stderr) == 1024

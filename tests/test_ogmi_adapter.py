from __future__ import annotations

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


def test_adapter_uses_fixed_ogmi_argv_and_returns_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    _checkpoint(checkpoint_path)
    project_path = tmp_path / "project"
    project_path.mkdir()
    calls: list[list[str]] = []
    adapter = OgmiAdapter(timeout_seconds=1, max_output_bytes=4096)

    def fake_run(argv: list[str]) -> tuple[int, bytes, bytes, bool]:
        calls.append(argv)
        command = argv[3]
        if command == "validate":
            stdout = json.dumps({"records": 1, "errors": 0, "warnings": 0}).encode()
        elif command == "hash":
            stdout = ("sha256:" + "a" * 64 + "\n").encode()
        else:
            stdout = json.dumps(
                {
                    "node": {"id": "project.active"},
                    "validation": {"errors": 0, "warnings": 0, "issues": []},
                }
            ).encode()
        return 0, stdout, b"", False

    monkeypatch.setattr(adapter, "_bounded_process", fake_run)
    resolved = adapter.resolve(
        checkpoint_path=checkpoint_path,
        project_path=project_path,
        orientation_spine_id="project.active",
        expected_run_id="run-01",
        expected_assignment_id="assignment-driver-01",
    )

    assert [call[2:] for call in calls] == [
        ["ogmi", "validate", str(checkpoint_path.resolve()), "--json"],
        ["ogmi", "hash", str(checkpoint_path.resolve())],
        ["ogmi", "orient", str(project_path.resolve()), "project.active"],
    ]
    assert resolved["checkpoint_id"] == "checkpoint-driver-01"
    assert resolved["checkpoint_sha256"] == "a" * 64
    assert resolved["orientation"]["node"]["id"] == "project.active"


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
    checkpoint_path = tmp_path / "checkpoint.json"
    _checkpoint(checkpoint_path)
    project_path = tmp_path / "project"
    project_path.mkdir()

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
    checkpoint_path = tmp_path / "checkpoint.json"
    _checkpoint(checkpoint_path)
    project_path = tmp_path / "project"
    project_path.mkdir()
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
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = _checkpoint(checkpoint_path)
    checkpoint["schema_version"] = "9.9"
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    project_path = tmp_path / "project"
    project_path.mkdir()

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

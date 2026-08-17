from __future__ import annotations

import json
from pathlib import Path

import pytest

from torc.artifacts.acceptance import accept_project_snapshot
from torc.artifacts.storage import ArtifactStore
from torc.artifacts.view import build_current_snapshot_view
from torc.cli import main
from torc.errors import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures" / "project-snapshot"
NOW = "2026-08-16T12:00:00Z"


def _load(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _accepted_store(tmp_path: Path) -> ArtifactStore:
    store = ArtifactStore(tmp_path)
    receipt = accept_project_snapshot(
        _load("snapshot.accepted.manual.json"),
        _load("evidence.accepted.json"),
        store,
        SCHEMAS,
        clock=lambda: NOW,
    )
    assert receipt["status"] == "accepted"
    return store


def test_current_view_revalidates_and_returns_all_three_records(tmp_path: Path) -> None:
    store = _accepted_store(tmp_path)

    view = build_current_snapshot_view(store, SCHEMAS)

    assert view["report_kind"] == "project_snapshot_view"
    assert view["derived"] is True
    assert view["canonical"] is False
    assert view["trusted"] is True
    assert view["artifact"]["artifact_id"] == store.current_id()
    assert view["evidence_bundle"]["bundle_id"] == view["receipt"]["evidence_bundle_id"]
    assert view["receipt"]["status"] == "accepted"


def test_current_view_fails_closed_when_stored_evidence_is_tampered(tmp_path: Path) -> None:
    store = _accepted_store(tmp_path)
    evidence_path = next(store.evidence_dir.glob("*.json"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["warnings"] = ["tampered"]
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(IntegrityError, match="Evidence Bundle"):
        build_current_snapshot_view(store, SCHEMAS)


def test_artifact_view_cli_emits_trusted_read_envelope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _accepted_store(tmp_path)

    assert main(["artifact", "view", "--store", str(store.root), "--json"]) == 0

    view = json.loads(capsys.readouterr().out)
    assert view["trusted"] is True
    assert view["artifact"]["artifact_id"] == store.current_id()

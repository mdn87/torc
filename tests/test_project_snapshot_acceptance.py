from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from torc.artifacts.acceptance import accept_project_snapshot
from torc.artifacts.identity import seal_content_id
from torc.artifacts.render import render_snapshot_html
from torc.artifacts.storage import ArtifactStore
from torc.artifacts.validation import validate_acceptance_receipt
from torc.canonical import canonical_json
from torc.cli import main
from torc.errors import NotFoundError, TorcError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
NOW = "2026-08-16T12:00:00Z"
COMMIT = "2" * 40


def _records() -> tuple[dict[str, object], dict[str, object]]:
    content = "accepted evidence"
    bundle = seal_content_id(
        {
            "schema": "urn:lugos:artifact:evidence-bundle:v1alpha1",
            "bundle_id": "",
            "collected_at": NOW,
            "collector": {"name": "torc", "version": "0.1.0"},
            "scope": {
                "repositories": [{"repository": "local/torc", "commit": COMMIT, "branch": "main"}]
            },
            "sources": [
                {
                    "source_id": "status",
                    "type": "git-file",
                    "repository": "local/torc",
                    "commit": COMMIT,
                    "path": "STATUS.md",
                    "selector": {"type": "whole-file"},
                    "content_sha256": "sha256:" + hashlib.sha256(content.encode()).hexdigest(),
                    "collected_at": NOW,
                    "content": content,
                }
            ],
            "git_state": [
                {
                    "repository": "local/torc",
                    "commit": COMMIT,
                    "branch": "main",
                    "clean": True,
                    "modified_paths": [],
                    "untracked_paths": [],
                    "recent_commits": [],
                }
            ],
            "warnings": [],
        },
        "bundle_id",
    )
    snapshot = seal_content_id(
        {
            "schema": "urn:lugos:artifact:project-snapshot:v1alpha1",
            "artifact_id": "",
            "kind": "project-snapshot",
            "generated_at": NOW,
            "scope": {
                "name": "TORC",
                "repositories": [{"repository": "local/torc", "commit": COMMIT}],
            },
            "generator": {
                "implementation": "manual-fixture",
                "version": "1",
                "provider": "manual",
            },
            "evidence_bundle": {"bundle_id": bundle["bundle_id"]},
            "projects": [
                {
                    "project_id": "torc",
                    "name": "TORC",
                    "status": "active",
                    "repositories": ["local/torc"],
                    "progress": [{"kind": "checks", "label": "validation passed"}],
                }
            ],
            "claims": [
                {
                    "claim_id": "ready",
                    "subject": "torc",
                    "predicate": "status",
                    "value": "reference-consumer-ready",
                    "status": "verified",
                    "evidence": [{"source_id": "status"}],
                    "observed_at": NOW,
                }
            ],
            "blockers": [
                {
                    "blocker_id": "none",
                    "summary": "No open implementation blocker",
                    "status": "resolved",
                    "evidence": [{"source_id": "status"}],
                }
            ],
            "pending_decisions": [],
            "recent_activity": [
                {
                    "activity_id": "validation",
                    "summary": "Validated fixture",
                    "occurred_at": NOW,
                    "evidence": [{"source_id": "status"}],
                }
            ],
            "conflicts": [],
            "unknowns": [],
            "metadata": {},
        },
        "artifact_id",
    )
    return bundle, snapshot


def test_accepted_snapshot_updates_current_and_renders_read_only_html(
    tmp_path: Path,
) -> None:
    bundle, snapshot = _records()
    store = ArtifactStore(tmp_path)

    receipt = accept_project_snapshot(snapshot, bundle, store, SCHEMAS, clock=lambda: NOW)

    assert receipt["status"] == "accepted"
    assert validate_acceptance_receipt(receipt, SCHEMAS).valid is True
    assert receipt["artifact_id"] == snapshot["artifact_id"]
    assert store.current_id() == snapshot["artifact_id"]
    assert store.current_artifact() == snapshot
    assert (
        store.accepted_dir / f"{str(snapshot['artifact_id']).removeprefix('sha256:')}.json"
    ).is_file()
    html = render_snapshot_html(snapshot, receipt)
    assert "TORC" in html
    assert "reference-consumer-ready" in html
    assert "No open implementation blocker" in html
    assert "Validated fixture" in html
    assert "Acceptance: accepted" in html
    assert "local/torc" in html and COMMIT in html
    assert "status" in html
    assert "<form" not in html and "contenteditable" not in html


def test_rejected_snapshot_cannot_update_current(tmp_path: Path) -> None:
    bundle, accepted = _records()
    store = ArtifactStore(tmp_path)
    first_receipt = accept_project_snapshot(accepted, bundle, store, SCHEMAS, clock=lambda: NOW)
    rejected = dict(accepted)
    rejected["claims"] = [dict(accepted["claims"][0])]
    rejected["claims"][0]["evidence"] = []
    rejected = seal_content_id(rejected, "artifact_id")

    receipt = accept_project_snapshot(rejected, bundle, store, SCHEMAS, clock=lambda: NOW)

    assert first_receipt["status"] == "accepted"
    assert receipt["status"] == "rejected"
    assert receipt["errors"]
    assert store.current_id() == accepted["artifact_id"]
    rejected_path = (
        store.accepted_dir / f"{str(rejected['artifact_id']).removeprefix('sha256:')}.json"
    )
    assert not rejected_path.exists()
    with pytest.raises(TorcError, match="rejected receipt cannot publish"):
        store.publish_accepted(rejected, receipt)


def test_digest_mismatch_still_produces_a_rejected_receipt(tmp_path: Path) -> None:
    bundle, snapshot = _records()
    snapshot["metadata"] = {"modified_after_identity": True}
    store = ArtifactStore(tmp_path)

    receipt = accept_project_snapshot(snapshot, bundle, store, SCHEMAS, clock=lambda: NOW)

    assert receipt["status"] == "rejected"
    assert any("artifact digest does not match content" in item for item in receipt["errors"])
    assert list(store.receipts_dir.glob("*.json"))
    assert not list(store.candidates_dir.glob("*.json"))
    with pytest.raises(NotFoundError):
        store.current_id()


def test_artifact_cli_validate_accept_current_and_render(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, snapshot = _records()
    bundle_path = tmp_path / "bundle.json"
    snapshot_path = tmp_path / "snapshot.json"
    bundle_path.write_text(canonical_json(bundle) + "\n", encoding="utf-8")
    snapshot_path.write_text(canonical_json(snapshot) + "\n", encoding="utf-8")
    store = tmp_path / "store"
    output = tmp_path / "dashboard" / "index.html"

    assert (
        main(["artifact", "validate", str(snapshot_path), "--evidence", str(bundle_path), "--json"])
        == 0
    )
    assert __import__("json").loads(capsys.readouterr().out)["valid"] is True
    assert (
        main(
            [
                "artifact",
                "accept",
                str(snapshot_path),
                "--evidence",
                str(bundle_path),
                "--store",
                str(store),
                "--json",
            ]
        )
        == 0
    )
    receipt = __import__("json").loads(capsys.readouterr().out)
    assert receipt["status"] == "accepted"
    assert main(["artifact", "current", "--store", str(store), "--json"]) == 0
    current = __import__("json").loads(capsys.readouterr().out)
    assert current["artifact_id"] == snapshot["artifact_id"]
    assert (
        main(
            [
                "artifact",
                "render",
                "--artifact",
                "current",
                "--store",
                str(store),
                "--format",
                "html",
                "--out",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    rendered = __import__("json").loads(capsys.readouterr().out)
    assert rendered["artifact_id"] == snapshot["artifact_id"]
    assert output.is_file()

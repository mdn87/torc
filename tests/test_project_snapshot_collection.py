from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from torc.artifacts.collection import collect_evidence_bundle
from torc.artifacts.identity import content_id_is_valid
from torc.errors import TorcError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
NOW = "2026-08-16T12:00:00Z"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "STATUS.md").write_text("# Status\n\nInitial.\n", encoding="utf-8")
    (repo / "data.json").write_text('{"gate":"passed"}\n', encoding="utf-8")
    (repo / ".env").write_text("API_KEY=secret-pattern-value\n", encoding="utf-8")
    _git(repo, "add", "STATUS.md", "data.json")
    _git(repo, "commit", "-m", "Initial status")
    return repo


def _manifest(repo: Path, extra: str = "") -> Path:
    path = repo / ".lugos" / "project-snapshot.sources.yaml"
    path.parent.mkdir()
    path.write_text(
        """version: 1
repository: local/project
recent_commits: 2
sources:
  - id: status
    path: STATUS.md
    required: true
  - id: gates
    path: data.json
    required: true
  - id: optional-roadmap
    path: ROADMAP.yaml
    required: false
"""
        + extra,
        encoding="utf-8",
    )
    return path


def test_collection_records_dirty_git_state_and_optional_missing_warning(
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    manifest = _manifest(repo)
    (repo / "STATUS.md").write_text("# Status\n\nChanged.\n", encoding="utf-8")
    (repo / "notes with space.yaml").write_text("state: draft\n", encoding="utf-8")

    first = collect_evidence_bundle(repo, manifest, SCHEMAS, clock=lambda: NOW)
    second = collect_evidence_bundle(repo, manifest, SCHEMAS, clock=lambda: NOW)

    assert first == second
    assert content_id_is_valid(first, "bundle_id") is True
    assert first["scope"]["repositories"][0]["repository"] == "local/project"
    state = first["git_state"][0]
    assert state["clean"] is False
    assert state["modified_paths"] == ["STATUS.md"]
    assert state["untracked_paths"] == [
        ".env",
        ".lugos/project-snapshot.sources.yaml",
        "notes with space.yaml",
    ]
    assert len(state["recent_commits"]) == 1
    assert [source["source_id"] for source in first["sources"]] == ["gates", "status"]
    assert first["sources"][1]["content"] == "# Status\n\nChanged.\n"
    assert first["warnings"] == ["optional source missing: ROADMAP.yaml"]
    assert all(source["path"] != ".env" for source in first["sources"])
    assert "secret-pattern-value" not in str(first)


def test_missing_required_source_fails_collection(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    manifest = _manifest(repo)
    (repo / "STATUS.md").unlink()

    with pytest.raises(TorcError, match="required source missing: STATUS.md"):
        collect_evidence_bundle(repo, manifest, SCHEMAS, clock=lambda: NOW)


@pytest.mark.parametrize(
    "path",
    [".env", "secrets/key.pem", "node_modules/pkg/index.js", ".git/config"],
)
def test_secret_prone_or_dependency_paths_are_rejected(tmp_path: Path, path: str) -> None:
    repo = _repository(tmp_path)
    target = repo / path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("credential material", encoding="utf-8")
    manifest = repo / "sources.yaml"
    manifest.write_text(
        "version: 1\nrepository: local/project\nsources:\n"
        f"  - id: forbidden\n    path: {path}\n    required: true\n",
        encoding="utf-8",
    )

    with pytest.raises(TorcError, match="source path is excluded"):
        collect_evidence_bundle(repo, manifest, SCHEMAS, clock=lambda: NOW)

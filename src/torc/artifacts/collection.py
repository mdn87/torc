"""Deterministic, manifest-bounded local Git evidence collection."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from torc import __version__
from torc.canonical import utc_now
from torc.errors import TorcError

from .identity import seal_content_id
from .validation import validate_evidence_bundle

Clock = Callable[[], str]
_EXCLUDED_PARTS = {
    ".git",
    ".ssh",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "secrets",
    "secret",
    "credentials",
    "credential",
}
_EXCLUDED_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
}
_EXCLUDED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def _git(repo: Path, *args: str, allow_failure: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode and not allow_failure:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise TorcError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.rstrip("\r\n")


def _manifest(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise TorcError(f"could not read evidence manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise TorcError("evidence manifest must be an object with version: 1")
    if not isinstance(value.get("sources", []), list):
        raise TorcError("evidence manifest sources must be a list")
    return value


def _safe_source(repo: Path, raw_path: Any) -> tuple[Path, str]:
    if not isinstance(raw_path, str) or not raw_path:
        raise TorcError("source path must be a non-empty repository-relative string")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise TorcError(f"source path escapes repository: {raw_path}")
    lowered = [part.casefold() for part in relative.parts]
    name = relative.name.casefold()
    if (
        any(part in _EXCLUDED_PARTS for part in lowered)
        or name in _EXCLUDED_NAMES
        or name.startswith(".env.")
        or relative.suffix.casefold() in _EXCLUDED_SUFFIXES
        or lowered[:2] == [".lugos", "artifacts"]
    ):
        raise TorcError(f"source path is excluded: {raw_path}")
    resolved = (repo / relative).resolve()
    if not resolved.is_relative_to(repo):
        raise TorcError(f"source path escapes repository: {raw_path}")
    return resolved, relative.as_posix()


def _git_state(repo: Path) -> tuple[list[str], list[str]]:
    output = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    modified: list[str] = []
    untracked: list[str] = []
    records = output.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        status, path = record[:2], record[3:]
        if status == "??":
            untracked.append(path)
        else:
            modified.append(path)
            if "R" in status or "C" in status:
                index += 1
    return sorted(modified), sorted(untracked)


def _recent_commits(repo: Path, limit: int) -> list[dict[str, str]]:
    if limit < 0 or limit > 100:
        raise TorcError("recent_commits must be between 0 and 100")
    if limit == 0:
        return []
    output = _git(
        repo,
        "log",
        "-n",
        str(limit),
        "--format=%H%x1f%s%x1f%aI%x1e",
    )
    records = []
    for raw in output.split("\x1e"):
        fields = raw.strip().split("\x1f")
        if len(fields) == 3:
            records.append({"commit": fields[0], "subject": fields[1], "authored_at": fields[2]})
    return records


def _selected_content(content: str, selector: dict[str, Any]) -> str:
    if selector["type"] == "whole-file":
        return content
    start = selector.get("start")
    end = selector.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise TorcError("line-range selector requires 1-based start <= end")
    return "".join(content.splitlines(keepends=True)[start - 1 : end])


def collect_evidence_bundle(
    repository: Path | str,
    manifest_path: Path | str,
    schema_dir: Path | str,
    *,
    clock: Clock = utc_now,
) -> dict[str, Any]:
    repo = Path(repository).resolve()
    if _git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise TorcError(f"not a local Git worktree: {repo}")
    manifest = _manifest(Path(manifest_path).resolve())
    repository_id = manifest.get("repository") or f"local/{repo.name}"
    if not isinstance(repository_id, str) or not repository_id:
        raise TorcError("manifest repository must be a non-empty string")
    commit = _git(repo, "rev-parse", "HEAD")
    branch = _git(repo, "symbolic-ref", "--short", "-q", "HEAD", allow_failure=True) or None
    collected_at = clock()
    warnings: list[str] = []
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    entries = sorted(
        manifest.get("sources", []),
        key=lambda item: (
            (str(item.get("id", "")), str(item.get("path", "")))
            if isinstance(item, dict)
            else ("", "")
        ),
    )
    for entry in entries:
        if not isinstance(entry, dict):
            raise TorcError("every evidence source must be an object")
        source_id = entry.get("id")
        if not isinstance(source_id, str) or not source_id:
            raise TorcError("every evidence source requires a non-empty id")
        if source_id in seen:
            raise TorcError(f"duplicate evidence source id: {source_id}")
        seen.add(source_id)
        target, relative = _safe_source(repo, entry.get("path"))
        if not target.is_file():
            requirement = "required" if entry.get("required", True) else "optional"
            message = f"{requirement} source missing: {relative}"
            if entry.get("required", True):
                raise TorcError(message)
            warnings.append(message)
            continue
        try:
            content = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            message = f"source unreadable: {relative}: {exc}"
            if entry.get("required", True):
                raise TorcError(message) from exc
            warnings.append(message)
            continue
        selector = entry.get("selector", {"type": "whole-file"})
        if not isinstance(selector, dict) or selector.get("type") not in {
            "whole-file",
            "line-range",
        }:
            raise TorcError(f"unsupported selector for {relative}")
        selected = _selected_content(content, selector)
        sources.append(
            {
                "source_id": source_id,
                "type": "git-file",
                "repository": repository_id,
                "commit": commit,
                "path": relative,
                "selector": selector,
                "content_sha256": "sha256:" + hashlib.sha256(selected.encode("utf-8")).hexdigest(),
                "collected_at": collected_at,
                "content": selected,
            }
        )
    modified, untracked = _git_state(repo)
    bundle = seal_content_id(
        {
            "schema": "urn:lugos:artifact:evidence-bundle:v1alpha1",
            "bundle_id": "",
            "collected_at": collected_at,
            "collector": {"name": "torc", "version": __version__},
            "scope": {
                "repositories": [{"repository": repository_id, "commit": commit, "branch": branch}]
            },
            "sources": sources,
            "git_state": [
                {
                    "repository": repository_id,
                    "commit": commit,
                    "branch": branch,
                    "clean": not modified and not untracked,
                    "modified_paths": modified,
                    "untracked_paths": untracked,
                    "recent_commits": _recent_commits(
                        repo, int(manifest.get("recent_commits", 10))
                    ),
                }
            ],
            "warnings": sorted(warnings),
        },
        "bundle_id",
    )
    validation = validate_evidence_bundle(bundle, schema_dir)
    if not validation.valid:
        raise TorcError("collected Evidence Bundle is invalid: " + "; ".join(validation.errors))
    return bundle

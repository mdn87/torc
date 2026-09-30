"""Hash-pinned staging and deterministic scoring for smoke fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from torc.canonical import canonical_json, payload_sha256  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = EXPERIMENT_ROOT / "fixtures"
MANIFEST_PATH = EXPERIMENT_ROOT / "fixtures-manifest.json"
_IGNORED_TREE_PARTS = {".git", ".pytest_cache", "__pycache__"}


class FixtureControlError(RuntimeError):
    """Raised when fixture isolation or integrity cannot be established."""


def tree_entries(root: Path) -> list[dict[str, Any]]:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise FixtureControlError(f"fixture tree does not exist: {resolved}")
    entries = []
    for path in sorted(item for item in resolved.rglob("*") if item.is_file()):
        relative = path.relative_to(resolved).as_posix()
        relative_parts = Path(relative).parts
        if (
            _IGNORED_TREE_PARTS.intersection(relative_parts)
            or relative.endswith((".pyc", ".pyo"))
        ):
            continue
        content = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        )
    if not entries:
        raise FixtureControlError(f"fixture tree is empty: {resolved}")
    return entries


def tree_sha256(root: Path) -> str:
    return payload_sha256(tree_entries(root))


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureControlError(f"fixture manifest cannot be read: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise FixtureControlError("fixture manifest schema version is unsupported")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, dict) or not fixtures:
        raise FixtureControlError("fixture manifest contains no fixtures")
    return manifest


def verify_fixture(fixture_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest["fixtures"].get(fixture_id)
    if not isinstance(expected, dict):
        raise FixtureControlError(f"fixture is not pinned: {fixture_id}")
    fixture_root = FIXTURES_ROOT / fixture_id
    actual = {
        "agent_visible_sha256": tree_sha256(fixture_root / "agent-visible"),
        "oracle_sha256": tree_sha256(fixture_root / "oracle"),
    }
    for field, digest in actual.items():
        if expected.get(field) != digest:
            raise FixtureControlError(
                f"fixture {fixture_id!r} failed {field} integrity verification"
            )
    return {"fixture_id": fixture_id, **actual, "valid": True}


def verify_all(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_manifest(path)
    results = [verify_fixture(fixture_id, manifest) for fixture_id in manifest["fixtures"]]
    on_disk = {
        path.name
        for path in FIXTURES_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    pinned = set(manifest["fixtures"])
    if on_disk != pinned:
        raise FixtureControlError(
            f"fixture manifest mismatch: unpinned={sorted(on_disk - pinned)}, "
            f"missing={sorted(pinned - on_disk)}"
        )
    return {"schema_version": 1, "valid": True, "fixtures": results}


def stage_fixture(fixture_id: str, destination: Path) -> dict[str, Any]:
    manifest = load_manifest()
    evidence = verify_fixture(fixture_id, manifest)
    resolved_destination = destination.resolve()
    if resolved_destination.exists():
        raise FixtureControlError(f"stage destination already exists: {resolved_destination}")
    source = FIXTURES_ROOT / fixture_id / "agent-visible"
    shutil.copytree(source, resolved_destination)
    git_commands = (
        ["git", "init", "--quiet"],
        ["git", "add", "--all"],
        [
            "git",
            "-c",
            "user.name=TORC Fixture",
            "-c",
            "user.email=torc-fixture@invalid.local",
            "commit",
            "--quiet",
            "-m",
            "fixture baseline",
        ],
    )
    for command in git_commands:
        completed = subprocess.run(
            command,
            cwd=resolved_destination,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode:
            raise FixtureControlError(
                f"fixture git initialization failed: {completed.stderr.strip()}"
            )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=resolved_destination,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    return {
        **evidence,
        "workspace": str(resolved_destination),
        "staged_tree_sha256": tree_sha256(resolved_destination),
        "baseline_revision": revision,
        "oracle_staged": False,
    }


def _run_test(command: list[str], workspace: Path) -> dict[str, Any]:
    effective = [sys.executable if command[0] == "python" else command[0], *command[1:]]
    completed = subprocess.run(
        effective,
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "command": effective,
        "exit_status": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def score_fixture(fixture_id: str, workspace: Path) -> dict[str, Any]:
    manifest = load_manifest()
    integrity = verify_fixture(fixture_id, manifest)
    resolved_workspace = workspace.resolve()
    if not resolved_workspace.is_dir():
        raise FixtureControlError(f"workspace does not exist: {resolved_workspace}")
    oracle_root = FIXTURES_ROOT / fixture_id / "oracle"
    oracle = json.loads((oracle_root / "oracle.json").read_text(encoding="utf-8"))
    visible = _run_test(list(oracle["visible_command"]), resolved_workspace)
    hidden = _run_test(
        ["python", "-m", "pytest", "-q", str(oracle_root / oracle["hidden_test"])],
        resolved_workspace,
    )
    diff = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--binary", "HEAD"],
        cwd=resolved_workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=resolved_workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()
    return {
        "schema_version": 1,
        "fixture_id": fixture_id,
        "fixture_integrity": integrity,
        "workspace_tree_sha256": tree_sha256(resolved_workspace),
        "visible": visible,
        "hidden": hidden,
        "workspace_diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "workspace_diff_bytes": len(diff.encode("utf-8")),
        "workspace_status": status,
        "accepted": visible["exit_status"] == 0 and hidden["exit_status"] == 0,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    stage = subparsers.add_parser("stage")
    stage.add_argument("fixture_id")
    stage.add_argument("destination", type=Path)
    score = subparsers.add_parser("score")
    score.add_argument("fixture_id")
    score.add_argument("workspace", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_all()
        elif args.command == "stage":
            result = stage_fixture(args.fixture_id, args.destination)
        else:
            result = score_fixture(args.fixture_id, args.workspace)
        print(canonical_json(result))
        return 0 if result.get("accepted", True) else 1
    except (FixtureControlError, OSError, subprocess.SubprocessError) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Reproduce retained experiment evidence with its pinned historical source tree.

This is an archival tool, not the current-runtime regression lane. It never
updates expected reports, checks out a branch, fetches history, or invokes models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

PINNED_COMMIT = "45fae25a6db0ea393dd6e997ed51c575184cb1e4"
DOCS = "docs/experiments/session-continuation-001"
EXPERIMENT = "experiments/session-continuation-001"
SCRIPTS = {
    "offline": f"{DOCS}/replay.py",
    "comparison": f"{DOCS}/comparison.py",
    "contexts": f"{EXPERIMENT}/contexts.py",
}
REPORTS = {
    f"{DOCS}/offline-report.json": None,
    f"{DOCS}/comparison-report.json": SCRIPTS["comparison"],
    f"{EXPERIMENT}/contexts-report.json": None,
}


class RetainedReplayError(ValueError):
    """Historical source or retained evidence is missing or inconsistent."""


def _safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise RetainedReplayError(f"invalid historical path: {relative}")
    return root.joinpath(*path.parts)


def verify_retained_assets(repository: Path, snapshot: Path) -> None:
    """Check recorded source pins and current copies of immutable experiment assets.

    Current production modules may evolve. Their recorded historical hashes are
    checked against the separately reconstructed snapshot, never substituted with
    current hashes. Reports, scripts, fixtures, and briefings retain exact custody.
    """
    repository, snapshot = Path(repository), Path(snapshot)
    immutable = set(REPORTS)
    for report_path, scalar_source in REPORTS.items():
        report = json.loads(_safe_path(snapshot, report_path).read_bytes())
        pins = report["source_sha256"]
        if scalar_source is not None:
            pins = {scalar_source: pins}
        for relative, expected in pins.items():
            historical = _safe_path(snapshot, relative)
            if (not historical.is_file()
                    or hashlib.sha256(historical.read_bytes()).hexdigest() != expected):
                raise RetainedReplayError(f"recorded source digest differs: {relative}")
            if not relative.startswith("src/"):
                immutable.add(relative)
    immutable.update(
        path.relative_to(snapshot).as_posix()
        for path in (snapshot / EXPERIMENT / "briefs").rglob("*") if path.is_file()
    )
    for relative in sorted(immutable):
        current, historical = _safe_path(repository, relative), _safe_path(snapshot, relative)
        if (current.is_symlink() or not current.is_file()
                or current.read_bytes() != historical.read_bytes()):
            raise RetainedReplayError(f"retained asset differs from {PINNED_COMMIT}: {relative}")


def _git(repository: Path, *args: str) -> bytes:
    environment = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        environment.pop(name, None)
    return subprocess.run(
        ["git", "-C", str(repository), *args], env=environment,
        capture_output=True, check=True, timeout=60,
    ).stdout


@dataclass(frozen=True)
class RetainedRuntime:
    """A temporary historical clone with independent refs, index, and working tree."""

    root: Path
    repository: Path

    def run(self, kind: str, arguments: list[str]) -> subprocess.CompletedProcess:
        if kind not in SCRIPTS:
            raise RetainedReplayError(f"unknown retained replay: {kind}")
        verify_retained_assets(self.repository, self.root)
        environment = dict(os.environ, PYTHONPATH=str(self.root / "src"),
                           GIT_NO_REPLACE_OBJECTS="1")
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
            environment.pop(name, None)
        return subprocess.run(
            [sys.executable, str(self.root / SCRIPTS[kind]), *arguments],
            cwd=self.root, env=environment, capture_output=True, check=True, timeout=180,
        )

    def replay(self, kind: str, output_dir: Path) -> subprocess.CompletedProcess:
        destination = str(Path(output_dir).resolve())
        arguments = {
            "offline": ["--output-dir", destination],
            "comparison": ["demo", "--output-dir", destination],
            "contexts": ["replay", "--destination", destination],
        }
        if kind not in arguments:
            raise RetainedReplayError(f"unknown retained replay: {kind}")
        return self.run(kind, arguments[kind])


@contextmanager
def retained_runtime(repository: Path):
    """Open the recorded source snapshot without changing the repository checkout.

    The caller needs the existing development environment and full local Git
    history. Git remains available for the historical workload's older snapshots.
    """
    repository = Path(repository).resolve()
    try:
        _git(repository, "cat-file", "-e", f"{PINNED_COMMIT}^{{commit}}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise RetainedReplayError(
            f"Cannot read pinned historical commit {PINNED_COMMIT}; "
            "use a TORC checkout with full Git history and Git on PATH. No history was fetched."
        ) from exc
    with tempfile.TemporaryDirectory(prefix="torc-retained-") as temporary:
        snapshot = Path(temporary)
        # --local forbids a network fetch. Shared objects are read from the source,
        # while every ref, index and checkout operation belongs to this disposable clone.
        _git(repository, "clone", "--local", "--shared", "--no-checkout",
             str(repository), str(snapshot))
        hooks = snapshot / ".git" / "retained-no-hooks"
        hooks.mkdir()
        _git(snapshot, "-c", "core.autocrlf=false", "-c", f"core.hooksPath={hooks}",
             "checkout", "--no-recurse-submodules", "--detach", PINNED_COMMIT)
        verify_retained_assets(repository, snapshot)
        yield RetainedRuntime(snapshot, repository)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=SCRIPTS)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with retained_runtime(args.repository) as runtime:
            print(f"Archival replay uses pinned TORC source {PINNED_COMMIT}.", file=sys.stderr)
            result = runtime.replay(args.kind, args.output_dir)
            sys.stdout.buffer.write(result.stdout)
            sys.stderr.buffer.write(result.stderr)
    except RetainedReplayError as exc:
        parser.exit(1, f"{exc}\n")
    except subprocess.CalledProcessError as exc:
        sys.stderr.buffer.write(exc.stderr or b"")
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pinned historical TORC tasks and arm-blind scoring preparation.

Only verify-references executes code here: it runs trusted implementations from
the pinned historical commit, never a supplied worker candidate. Candidate
scoring is prepared for a separately qualified isolated execution owner.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from copy import deepcopy
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "a798bbc4c45527952510a5f3d239f49c5b67a2de"
REFERENCE = "9d96039a0e1fefecfc75948fc31464dc6706fee9"
TASKS = {
    "capsule-context": {
        "editable_paths": ["src/torc/continuation_context.py"],
        "hidden_tests": ["tests/test_continuation_context.py"],
        "brief": "capsule-context.md",
    },
    "whole-task-usage": {
        "editable_paths": ["src/torc/continuation_usage.py"],
        "hidden_tests": ["tests/test_continuation_usage.py"],
        "brief": "whole-task-usage.md",
    },
}
IGNORED = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json_hash(value):
    return _hash(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          check=True, timeout=30).stdout


@cache
def _snapshot():
    files = {}
    with tarfile.open(fileobj=io.BytesIO(_git("archive", "--format=tar", BASE))) as archive:
        for item in archive:
            path = Path(item.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("invalid snapshot path")
            if item.isdir():
                continue
            if not item.isfile():
                raise ValueError("snapshot contains a non-regular file")
            files[path.as_posix()] = archive.extractfile(item).read()
    return files


def specification(workload_id):
    if workload_id not in TASKS:
        raise ValueError("unknown workload")
    spec = deepcopy(TASKS[workload_id])
    return {**spec, "workload_id": workload_id, "base_commit": BASE,
            "reference_commit": REFERENCE, "evidence_class": "historical_repository_task",
            "generalization": "pilot only; historical replays are not adoption samples",
            "history_kind": "operator-authored briefing; native seed session not yet created"}


def _expected(workload_id):
    spec = specification(workload_id)
    files = dict(_snapshot())
    files["CONTINUATION_TASK.md"] = (HERE / "briefs" / spec["brief"]).read_bytes()
    files["CONTINUATION_RULES.md"] = (HERE / "briefs/common.md").read_bytes()
    return files


def _entries(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError("candidate symlink is not supported")
        if set(relative.parts) & IGNORED:
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("candidate contains a non-regular file")
        result[relative.as_posix()] = path.read_bytes()
    return result


def _tree_hash(files):
    return _json_hash({path: _hash(data) for path, data in sorted(files.items())})


def tree_sha256(root):
    return _tree_hash(_entries(Path(root)))


def _write_tree(files, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("destination already exists")
    destination.mkdir(parents=True, mode=0o700)
    for relative, data in files.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            path.chmod(0o600)
            stream.write(data)


def stage(workload_id, destination):
    """Stage only pre-change files and public requirements; no Git object store."""
    files = _expected(workload_id)
    _write_tree(files, destination)
    spec = specification(workload_id)
    return {**spec, "workspace_sha256": _tree_hash(files),
            "source_tree_sha256": _tree_hash(_snapshot()),
            "public_brief_sha256": _hash(files["CONTINUATION_TASK.md"]),
            "common_rules_sha256": _hash(files["CONTINUATION_RULES.md"]),
            "worker_may_read_oracle": False}


def prepare_score(workload_id, candidate, destination):
    """Freeze an arm-blind scoring copy without executing candidate code.

    Call only after the execution owner confirms the worker is terminal. The
    caller must deliver this copy to its qualified isolated scorer, then bind
    the actual test receipt to candidate_sha256. No live admission occurs here.
    """
    spec = specification(workload_id)
    expected = _expected(workload_id)
    observed = _entries(Path(candidate))
    protected = sorted(path for path in set(expected) | set(observed)
                       if path not in spec["editable_paths"]
                       and expected.get(path) != observed.get(path))
    if protected:
        raise ValueError("protected paths changed: " + ", ".join(protected[:10]))
    before = _tree_hash(observed)
    scoring_files = dict(observed)
    tests = {}
    for path in spec["hidden_tests"]:
        data = _git("show", f"{REFERENCE}:{path}")
        scoring_files[path] = data
        tests[path] = _hash(data)
    _write_tree(scoring_files, destination)
    if tree_sha256(candidate) != before:
        raise ValueError("candidate changed while preparing scoring")
    return {"schema_version": 1, "workload_id": workload_id,
            "candidate_sha256": before, "scoring_tree_sha256": _tree_hash(scoring_files),
            "hidden_test_sha256": tests, "worker_workspace_modified": False,
            "command": ["python", "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "--basetemp=.score-tmp", *spec["hidden_tests"]],
            "required_environment": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
            "requires_qualified_isolated_execution": True}


def _trusted_test(job, workspace):
    # Private helper: verify_references supplies only pinned repository bytes.
    command = [sys.executable, *job["command"][1:]]
    environment = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    environment.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(command, cwd=workspace, env=environment, capture_output=True,
                            text=True, timeout=120)
    return {"candidate_sha256": job["candidate_sha256"], "exit_status": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def verify_references(destination):
    """Prove task discrimination using trusted historical code, without models."""
    destination = Path(destination)
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    rows = []
    for identity in TASKS:
        candidate = destination / identity / "candidate"
        staged = stage(identity, candidate)
        baseline_dir = destination / identity / "baseline-score"
        job = prepare_score(identity, candidate, baseline_dir)
        baseline = _trusted_test(job, baseline_dir)
        for path in TASKS[identity]["editable_paths"]:
            (candidate / path).write_bytes(_git("show", f"{REFERENCE}:{path}"))
        reference_dir = destination / identity / "reference-score"
        job = prepare_score(identity, candidate, reference_dir)
        reference = _trusted_test(job, reference_dir)
        # Deliberately break one material invariant in otherwise working code.
        # These controls test the scorer, not a model's ability to match a patch.
        target = candidate / TASKS[identity]["editable_paths"][0]
        text = target.read_text()
        if identity == "capsule-context":
            old = ('current.update(lineage_id=lineage_id, '
                   'lineage_revision_id=lineage["head_revision_id"])')
            new = 'current.update(lineage_id=lineage_id)  # stale caller revision survives'
        else:
            old = 'ordered[-1][f] if ordered else None'
            new = '_sum([n[f] for n in ordered]) if ordered else None'
        if text.count(old) != 1:
            raise ValueError("historical negative-control site changed")
        target.write_bytes(text.replace(old, new).encode("utf-8"))
        mutant_dir = destination / identity / "mutant-score"
        job = prepare_score(identity, candidate, mutant_dir)
        mutant = _trusted_test(job, mutant_dir)
        (candidate / "src/torc/p5_capsules.py").write_text("# forbidden change\n")
        try:
            prepare_score(identity, candidate, destination / identity / "forbidden-score")
        except ValueError as error:
            rejected = "protected" in str(error)
        else:
            rejected = False
        rows.append({"workload_id": identity, "staged": staged, "baseline": baseline,
                     "reference": reference, "mutant": mutant,
                     "protected_change_rejected": rejected})
    return {"schema_version": 1, "live_model_trials": 0, "workloads": rows,
            "all_passed": all(r["baseline"]["exit_status"] != 0
                              and r["reference"]["exit_status"] == 0
                              and r["mutant"]["exit_status"] == 1
                              and r["protected_change_rejected"] for r in rows),
            "untrusted_candidate_execution_qualified": False}


def reference_summary(report):
    """Stable report projection; raw pytest timings/temporary paths stay in the full receipt."""
    return {"schema_version": 1, "live_model_trials": 0, "all_passed": report["all_passed"],
            "untrusted_candidate_execution_qualified": False,
            "source_sha256": _hash(Path(__file__).read_bytes()),
            "workloads": [{"workload_id": row["workload_id"], "staged": row["staged"],
                           "protected_change_rejected": row["protected_change_rejected"],
                           **{kind: {"candidate_sha256": row[kind]["candidate_sha256"],
                                     "exit_status": row[kind]["exit_status"]}
                              for kind in ("baseline", "reference", "mutant")}}
                          for row in report["workloads"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    staging = commands.add_parser("stage")
    staging.add_argument("workload", choices=TASKS)
    staging.add_argument("--destination", required=True, type=Path)
    scoring = commands.add_parser("prepare-score")
    scoring.add_argument("workload", choices=TASKS)
    scoring.add_argument("--candidate", required=True, type=Path)
    scoring.add_argument("--destination", required=True, type=Path)
    verification = commands.add_parser("verify-references")
    verification.add_argument("--destination", required=True, type=Path)
    verification.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    if args.command == "stage":
        report = stage(args.workload, args.destination)
    elif args.command == "prepare-score":
        report = prepare_score(args.workload, args.candidate, args.destination)
    else:
        report = verify_references(args.destination)
        if args.summary:
            report = reference_summary(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.command == "verify-references" and not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

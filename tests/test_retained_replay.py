"""Historical source custody and current-runtime regression checks are separate."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

import torc.retained_replay as replay_module
from torc.retained_replay import (
    RetainedReplayError,
    retained_runtime,
    verify_retained_assets,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = "docs/experiments/session-continuation-001"


def test_temporary_path_alias_is_resolved_before_historical_execution(tmp_path, monkeypatch):
    original_temporary_directory = replay_module.tempfile.TemporaryDirectory
    temporary_parent = tmp_path / ("nested-" + "x" * 40)
    alias_parent = temporary_parent / "alias-parent"
    alias_parent.mkdir(parents=True)
    # Reproduce Git for Windows defaults even if the developer enabled long paths.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.longpaths")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")

    @contextmanager
    def aliased_temporary_directory(**kwargs):
        with original_temporary_directory(dir=temporary_parent, **kwargs) as canonical:
            # A portable lexical alias exercises the same mismatch as macOS
            # /var -> /private/var without requiring symlink privileges.
            yield str(alias_parent / ".." / Path(canonical).name)

    monkeypatch.setattr(replay_module.tempfile, "TemporaryDirectory", aliased_temporary_directory)
    with retained_runtime(ROOT) as runtime:
        assert runtime.root == runtime.root.resolve()
        result = runtime.replay("offline", tmp_path / "aliased-replay")
        assert result.stdout == (ROOT / DOCS / "offline-report.json").read_bytes()


def test_runtime_drift_is_allowed_but_retained_source_and_report_tampering_reject(tmp_path):
    with retained_runtime(ROOT) as runtime:
        current = tmp_path / "current"
        shutil.copytree(runtime.root, current, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        production = current / "src/torc/store.py"
        production.write_text("# A newer production implementation.\n", encoding="utf-8")
        verify_retained_assets(current, runtime.root)
        for relative in (
            f"{DOCS}/replay.py", f"{DOCS}/offline-report.json",
            f"{DOCS}/fixtures/interrupted.jsonl",
            "experiments/session-continuation-001/briefs/capsule-context.md",
        ):
            path = current / relative
            original = path.read_bytes()
            path.write_bytes(original + b"\nchanged retained evidence\n")
            with pytest.raises(RetainedReplayError, match="retained asset differs"):
                verify_retained_assets(current, runtime.root)
            path.write_bytes(original)
        (runtime.root / "src/torc/store.py").write_text("# tampered snapshot\n", encoding="utf-8")
        with pytest.raises(RetainedReplayError, match="recorded source digest differs"):
            runtime.replay("offline", tmp_path / "must-not-run")
        assert not (tmp_path / "must-not-run").exists()


def test_missing_pinned_history_is_an_explicit_failure(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(RetainedReplayError, match="pinned historical commit.*full Git history"):
        with retained_runtime(tmp_path):
            pytest.fail("missing history must not fall back to current sources")


def test_archival_cli_reproduces_original_report_without_changing_checkout(tmp_path):
    def source_state():
        def git(*args):
            return subprocess.run(["git", "--no-optional-locks", *args], cwd=ROOT,
                                  capture_output=True, check=True).stdout

        index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index")
                     .decode().strip())
        tracked = [path.decode() for path in git("ls-files", "-z").split(b"\0") if path]
        return {
            "head": git("rev-parse", "HEAD"), "index": index.read_bytes(),
            "status": git("status", "--porcelain"),
            "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                      for path in tracked if (ROOT / path).is_file()},
        }

    before = source_state()
    result = subprocess.run(
        [sys.executable, "-m", "torc.retained_replay", "offline", "--repository", str(ROOT),
         "--output-dir", str(tmp_path / "archival")],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        cwd=tmp_path, capture_output=True, check=True,
    )
    assert result.stdout == (ROOT / DOCS / "offline-report.json").read_bytes()
    assert b"45fae25" in result.stderr
    assert before == source_state()


@pytest.mark.parametrize("kind", ["offline", "comparison", "contexts"])
def test_current_runtime_replays_remain_self_consistent_and_keep_honest_provenance(tmp_path, kind):
    scripts = {
        "offline": (f"{DOCS}/replay.py", [], "--output-dir"),
        "comparison": (f"{DOCS}/comparison.py", ["demo"], "--output-dir"),
        "contexts": ("experiments/session-continuation-001/contexts.py",
                     ["replay"], "--destination"),
    }
    script, args, flag = scripts[kind]
    reports = []
    for name in ("first", "second"):
        destination = tmp_path / name
        run = subprocess.run(
            [sys.executable, str(ROOT / script), *args, flag, str(destination)],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True, check=True,
        )
        reports.append(run.stdout)
        report = json.loads(run.stdout)
        assert report["live_model_trials"] == 0
        if kind == "offline":
            assert report["state_store_unchanged"] is True
            refs = [*report["artifacts"].values(), *(c["artifact"] for c in report["usage_cases"])]
        elif kind == "comparison":
            assert report["launch_authorized"] is False
            assert report["cases"]["complete_synthetic"]["attempt_count"] == 24
            assert report["cases"]["false_completion"]["critical_failure_count"] == 1
            refs = [report["plan"], report["manifest"]]
            refs += [case[field] for case in report["cases"].values()
                     for field in ("results", "analysis")]
        else:
            refs = []
            for task, record in report["tasks"].items():
                assert record["state_store_unchanged_during_verification"] is True
                assert record["bridge"]["authority_transferred"] is False
                verified = subprocess.run(
                    [sys.executable, str(ROOT / script), "verify",
                     "--root", str(destination / task),
                     "--expected-manifest-id", record["manifest_id"]],
                    cwd=ROOT, capture_output=True, check=True,
                )
                assert json.loads(verified.stdout)["torc_capsule"]["retry_authorized"] is False
        for ref in refs:
            path = destination / ref
            assert hashlib.sha256(path.read_bytes()).hexdigest() == path.stem
        source_pins = report["source_sha256"]
        if isinstance(source_pins, str):
            source_pins = {script: source_pins}
        for path, digest in source_pins.items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert reports[0] == reports[1]

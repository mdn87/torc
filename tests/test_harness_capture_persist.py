"""Derived publication is create-once and does not touch canonical state."""

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from torc.harness_capture.persist import publish


def test_overlapping_identical_writers_publish_one_complete_artifact(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(lambda _: publish(tmp_path, "capture", {"value": 1}), range(16)))
    assert len(set(paths)) == 1
    path = paths[0]
    assert path.read_bytes() == b'{"value":1}\n'
    assert path.stem == hashlib.sha256(path.read_bytes()).hexdigest()
    assert list((tmp_path / "capture").iterdir()) == [path]
    assert path.stat().st_mode & 0o777 == 0o600


def test_existing_different_bytes_are_never_overwritten(tmp_path):
    path = publish(tmp_path, "capture", {"value": 1})
    path.write_bytes(b"corrupt existing artifact")
    with pytest.raises(ValueError, match="different bytes"):
        publish(tmp_path, "capture", {"value": 1})
    assert path.read_bytes() == b"corrupt existing artifact"


def test_interruption_before_publication_preserves_previous_artifact(tmp_path):
    old = publish(tmp_path, "capture", {"value": "previous"})
    before = old.read_bytes()
    # A hard process exit after the private temporary is complete and before
    # atomic publication must not expose the new body at a published path.
    code = """
import os, sys
from torc.harness_capture import persist
def interrupt(*args):
    os._exit(23)
persist.os.link = interrupt
persist.publish(sys.argv[1], 'capture', {'value': 'new'})
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=env, check=False)
    assert result.returncode == 23
    assert old.read_bytes() == before
    assert list((tmp_path / "capture").glob("*.json")) == [old]
    new = publish(tmp_path, "capture", {"value": "new"})
    assert json.loads(new.read_bytes()) == {"value": "new"}
    assert old.read_bytes() == before


@pytest.mark.parametrize("kind", ["../escape", "capture/path", "", ".", "latest.json"])
def test_publication_kind_cannot_escape_output_directory(tmp_path, kind):
    with pytest.raises(ValueError):
        publish(tmp_path, kind, {})


def test_capture_paths_leave_canonical_store_unchanged(tmp_path):
    from test_harness_capture import capture, report
    from test_p5_capsule_adapter import _prepared, _unchanged

    state = tmp_path / "canonical"
    _prepared(state)
    with _unchanged(state):
        manifest = capture()
        result = report(manifest)
        publish(tmp_path / "derived", "capture", manifest)
        publish(tmp_path / "derived", "reconciliation", result)
        assert report(capture(b'{"type":'))["status"] == "held"
        with pytest.raises(ValueError):
            capture(b"", prefix_length=1)


def test_no_execution_or_provider_modules_in_capture_import_graph():
    # Import in a clean interpreter so unrelated pytest plugins cannot mask the
    # dependency boundary. No store, CLI, provider client or networking imports.
    code = """
import sys
from torc.harness_capture import parser, classify, manifest, reconcile, persist
for name in sys.modules:
    assert name.split('.')[0] not in {'socket', 'http', 'urllib', 'requests', 'anthropic', 'openai'}
assert 'torc.store' not in sys.modules
assert 'subprocess' not in sys.modules
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    subprocess.run([sys.executable, "-c", code], env=env, check=True)

"""The approved smaller pilot stays an immutable, non-authorizing plan."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from torc.continuation_trials import verify_manifest


def test_diagnostic_pins_six_trials_two_seeds_and_no_cold_claim(tmp_path):
    source = Path(__file__).resolve().parents[1] / "experiments/session-continuation-001"
    spec = importlib.util.spec_from_file_location(
        "continuation_diagnostic", source / "diagnostic.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(source))
    try:
        spec.loader.exec_module(module)
        destination = tmp_path / "prepared"
        result = module.prepare(destination)
    finally:
        sys.path.pop(0)
    manifest = json.loads((destination / "manifest.json").read_bytes())
    launch = json.loads((destination / "launch-intent.json").read_bytes())
    assert len(result["schedule"]) == 6
    assert {row["arm"] for row in result["schedule"]} == {
        "compiled_prompt", "torc_capsule", "native_warm"}
    assert len(launch["seed_intents"]) == 2
    assert launch["planned_total_invocations"] == 8 <= launch["max_total_invocations"] == 9
    assert not manifest["launch_authorized"] and not launch["launch_authorized"]
    assert not manifest["plan"]["telemetry"]["proxy_compatible"]
    assert launch["paid_api_ceiling_usd"] == 0
    verify_manifest(manifest, destination, expected_manifest_id=result["manifest_id"])
    prompt = destination / manifest["plan"]["workloads"][0]["contexts"]["torc_capsule"]["path"]
    prompt.write_bytes(prompt.read_bytes() + b"unregistered edit")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_manifest(manifest, destination, expected_manifest_id=result["manifest_id"])

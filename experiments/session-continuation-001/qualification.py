"""Model-free macOS workspace qualification through the existing Autowork owner.

This invokes the inspected macOS deterministic capability path. It does not
install provider policy, repair credentials or qualify model/session behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

CAPABILITY_SOURCE_SHA256 = {
    "6aa24380afdc39eeeb430b2aff9d9a398486d019eb1d69d867fa2f5affbc04e9",
    # Scoped usage-record schema change; model-free execution path unchanged.
    "74104ed4a457f98f7eaf5e82998a92c837f57d22dfe3840a0e591e31fb75f563",
}


def probe(owner):
    if sys.platform != "darwin":
        raise ValueError("only the inspected model-free macOS qualification path is supported")
    owner = Path(owner).expanduser().resolve()
    source = owner / "src"
    sys.path.insert(0, str(source))
    capabilities = importlib.import_module("autowork.campaign.capability_attestation")
    if not Path(capabilities.__file__).resolve().is_relative_to(source.resolve()):
        raise ValueError("loaded capability owner is outside the declared checkout")
    digest = hashlib.sha256(Path(capabilities.__file__).read_bytes()).hexdigest()
    if digest not in CAPABILITY_SOURCE_SHA256:
        raise ValueError("capability owner changed; inspect its model-free macOS path again")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=owner, check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    original = capabilities.run_process

    def no_model_process(argv, **kwargs):
        # Add a refusal, never relax the owner's provider/credential guards.
        # The strict-config negative control fails before inference; every
        # other exec invocation is prohibited, including any fallback path.
        if "exec" in argv and "autowork_unknown_control=true" not in argv:
            raise RuntimeError("model execution forbidden during offline qualification")
        return original(argv, **kwargs)

    capabilities.run_process = no_model_process
    previous = Path.cwd()
    report = {"schema_version": 1, "owner_commit": revision,
              "capability_source_sha256": digest,
              "owner_source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in (source / "autowork/campaign").glob("*.py")},
              "interpreter": str(Path(sys.executable).resolve()),
              "python_version": sys.version.split()[0],
              "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
              "platform": "macos", "requested_sandbox": "workspace-write",
              "live_model_calls": 0, "native_resume_qualified": False,
              "telemetry_qualified": False, "live_launch_authorized": False}
    try:
        with tempfile.TemporaryDirectory(prefix="torc-sandbox-candidate-") as candidate:
            os.chdir(candidate)
            Path("TASK.md").write_text("Disposable capability test; no model execution.")
            try:
                result = capabilities.run_live_attestation_smoke(sandbox="workspace-write")
                report.update(status="passed", attestation=result.attestation.to_dict(),
                              cache_hit=result.cache_hit,
                              usage=result.usage.to_dict() if result.usage else None)
            except Exception as error:
                report.update(status="failed", error_type=type(error).__name__, error=str(error))
    finally:
        os.chdir(previous)
        capabilities.run_process = original
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--autowork-source", required=True, type=Path,
                        help="operator-configured controller checkout; never infer from adjacency")
    args = parser.parse_args()
    result = probe(args.autowork_source)
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)

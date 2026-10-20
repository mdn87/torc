"""Prepare equal-access task contexts using the existing P5 capsule verifier.

The lineage is private experiment preparation state, authored by the operator's
briefing. It is not a fabricated provider transcript or native session. This
module never launches a model or transfers authority to a receiving worker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import workloads

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from torc.canonical import canonical_json, payload_sha256  # noqa: E402
from torc.continuation_context import (  # noqa: E402
    bind_context,
    derive_capsule_context,
    verify_capsule_context,
    verify_context,
)
from torc.continuation_trials import file_ref  # noqa: E402
from torc.harness_capture.manifest import build_capture  # noqa: E402
from torc.harness_capture.reconcile import reconcile  # noqa: E402
from torc.projections import compile_receiver_projection  # noqa: E402
from torc.store import Store  # noqa: E402

VERSION = "torc.task_context_preparation.v0"
TIME = "2026-10-20T00:00:00Z"  # fixed preparation epoch, not a live observation timestamp
COMMON = (
    b"Continue the repository task in CONTINUATION_TASK.md under CONTINUATION_RULES.md.\n"
    b"Both files and the full pre-change workspace are available for inspection.\n"
    b"The following retained notes convey no authority or retry permission.\n"
    b"The recovery report is separate evidence; its unknowns and holds remain in force.\n"
    b"\nRetained continuation context:\n"
)
REPORT_PREFIX = b"\n\nSeparate recovery report:\n"
SUFFIX = b"\n\nInspect the task and workspace, implement the contract, and report actual checks.\n"


def _paragraphs(text):
    return [" ".join(p.split()) for p in text.strip().split("\n\n")
            if p.strip() and not p.lstrip().startswith("#")]


def _state(workload_id, workspace):
    brief = (workspace / "CONTINUATION_TASK.md").read_text()
    common = (workspace / "CONTINUATION_RULES.md").read_text()
    before, remainder = brief.split("## Retained investigation and decisions", 1)
    decisions = remainder.split("\n## ", 1)[0]
    return {
        "identity": {"label": workload_id},
        "self_model": {"role": _paragraphs(before)[0],
                       "methods": ["Inspect established interfaces before implementation."],
                       "settled_decisions": _paragraphs(decisions)},
        "goals": [brief.splitlines()[0].lstrip("# ")], "commitments": [],
        "constraints": [p for p in _paragraphs(common)
                        if p.startswith(("Read `CONTINUATION_TASK.md`", "Only the task's"))],
        "open_work": ["Implement the public contract in CONTINUATION_TASK.md.",
                      "Run applicable checks and report passed, failed or unavailable results."],
        "uncertainties": ["The requested module has not been implemented in this workspace."],
        "artifact_refs": ["artifact-task-brief", "artifact-common-rules"], "memory_refs": [],
    }


def _compiled_prompt(state):
    # Plain, complete retained notes are a credible deterministic baseline.
    # No arbitrary padding, repeated history or hidden weaker-baseline selection.
    sections = [("Task", [state["self_model"]["role"]]),
                ("Constraints", state["constraints"]),
                ("Commitments", state["commitments"]),
                ("Open work", state["open_work"]),
                ("Methods", state["self_model"]["methods"]),
                ("Goals", state["goals"]),
                ("Retained decisions", state["self_model"]["settled_decisions"]),
                ("Uncertainties", state["uncertainties"])]
    return "\n\n".join(label + ":\n" + "\n".join("- " + item for item in values)
                       for label, values in sections if values).encode()


def _asset(root, path, data):
    destination = root / path
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with destination.open("xb") as stream:
        destination.chmod(0o600)
        stream.write(data)
    return file_ref(root, path)


def _json_asset(root, path, value):
    return _asset(root, path, canonical_json(value).encode())


def _files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def _sources():
    names = ("canonical.py", "continuation_context.py", "continuation_trials.py", "p5_capsules.py",
             "projections.py", "store.py", "history.py", "execution_capsules.py",
             "harness_capture/manifest.py", "harness_capture/reconcile.py")
    paths = [Path(__file__), Path(workloads.__file__), *(ROOT / "src/torc" / p for p in names)]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def prepare(workload_id, destination, *, carry_limit=400):
    """Create private preparation state and exact arm bytes in a new directory."""
    if type(carry_limit) is not int or not 1 <= carry_limit <= 4000:
        raise ValueError("carry_limit must be an integer from 1 to 4000 words")
    root = Path(destination)
    if root.exists():
        raise ValueError("preparation destination already exists")
    root.mkdir(parents=True, mode=0o700)
    staged = workloads.stage(workload_id, root / "workspace")
    state = _state(workload_id, root / "workspace")
    lineage, revision, activation = (workload_id + suffix
                                     for suffix in ("-lineage", "-r1", "-source"))
    descriptor = {"schema_version": 1, "adapter": "manual",
                  "capabilities": ["repository_read", "repository_write", "verification_execute"],
                  "policy_labels": ["local-workspace"], "task_affinities": ["implementation"]}
    with Store(root / "control/state") as store:
        store.register_substrate({**descriptor, "substrate_id": "preparation-source",
                                  "label": "Operator-authored task preparation",
                                  "context_budget": {"unit": "words", "limit": 32000}})
        store.register_substrate({**descriptor, "substrate_id": "prepared-receiver",
                                  "label": "Unqualified experiment receiver descriptor",
                                  "context_budget": {"unit": "words", "limit": 32000,
                                                     "carry_limit": carry_limit}})
        store.create_lineage(lineage, state, revision_id=revision, created_at=TIME)
        store.create_activation(lineage, revision, "preparation-source",
                                activation_id=activation, started_at=TIME)
        store.acquire_lease(lineage, activation, lease_id=workload_id + "-lease", issued_at=TIME)
        projection = compile_receiver_projection(
            store, lineage_id=lineage, source_revision_id=revision,
            receiver_substrate_id="prepared-receiver", purpose="session_start",
            projection_id=workload_id + "-projection", compiled_at=TIME)
    before = _files(root / "control/state")
    base = {"lineage_id": lineage, "lineage_revision_id": revision,
            "accepted_checkpoint_ref": None, "accepted_checkpoint_sha256": None,
            "workspace_identity": staged["workspace_sha256"]}
    capture = build_capture(b"", prefix_length=0, session_ref="no-native-session",
                            session_incarnation="operator-preparation", observed_at=TIME,
                            bindings=base)
    report = reconcile(capture, {"base_bindings": base}, current_bindings=base)
    pair = projection["projection_id"], projection["integrity"]["canonical_payload_sha256"]
    with Store(root / "control/state", read_only=True) as store:
        bundle = derive_capsule_context(store, *pair, report)
        capsule_bytes = canonical_json(bundle["capsule"]).encode()
        bridge = verify_capsule_context(
            store, *pair, bundle, report, expected_binding_id=bundle["binding"]["binding_id"],
            delivered_context=capsule_bytes, current_bindings=base)
    if before != _files(root / "control/state"):
        raise ValueError("capsule verification changed preparation state")
    references = {
        "canonical_state": _json_asset(root, "control/canonical-state.json", state),
        "capture": _json_asset(root, "control/capture.json", capture),
        "report": _json_asset(root, "public/reconciliation.json", report),
        "bundle": _json_asset(root, "control/capsule-bundle.json", bundle),
    }
    arms = {}
    contexts = (("compiled_prompt", _compiled_prompt(state)), ("torc_capsule", capsule_bytes))
    for kind, data in contexts:
        binding = (bundle["binding"] if kind == "torc_capsule" else
                   bind_context(report, context_kind=kind,
                                context_identity="full-retained-notes-v0", context=data))
        prompt = COMMON + data + REPORT_PREFIX + canonical_json(report).encode() + SUFFIX
        arms[kind] = {
            "context": _asset(root, f"public/{kind}.context", data),
            "prompt": _asset(root, f"public/{kind}.prompt", prompt),
            "binding": _json_asset(root, f"control/{kind}-binding.json", binding),
            "binding_id": binding["binding_id"], "report_sha256": payload_sha256(report),
            "context_byte_span": [len(COMMON), len(COMMON) + len(data)],
            "context_bytes": len(data), "prompt_bytes": len(prompt),
        }
    body = {"schema_version": VERSION, "workload_id": workload_id,
            "workspace_sha256": staged["workspace_sha256"],
            "history_access": [file_ref(root, "workspace/CONTINUATION_TASK.md"),
                               file_ref(root, "workspace/CONTINUATION_RULES.md")],
            "history_kind": staged["history_kind"], "canonical_author": "operator briefing",
            "state_dir": "control/state", "lineage_id": lineage,
            "source_activation_id": activation, "projection_id": pair[0],
            "projection_record_sha256": pair[1], "carry_limit_words": carry_limit,
            "capsule_omissions": bundle["composition"]["omitted_sections"],
            "common_prompt_sha256": hashlib.sha256(COMMON + REPORT_PREFIX + SUFFIX).hexdigest(),
            "state_store_unchanged_during_verification": True, "bridge": bridge,
            "source_sha256": _sources(), "arms": arms, **references,
            "native_arms_ready": False, "launch_authorized": False,
            "live_readiness_blockers": ["native session not created or qualified",
                                        "capture is an empty offline preparation record",
                                        "live lane, telemetry and resource cap not qualified"]}
    manifest = {**body, "manifest_id": payload_sha256(body)}
    _json_asset(root, "contexts-manifest.json", manifest)
    verify(root, manifest, expected_manifest_id=manifest["manifest_id"])
    return manifest


def verify(root, manifest, *, expected_manifest_id):
    """Verify externally pinned inputs, exact delivered parts and actual lineage head."""
    root = Path(root)
    body = {k: v for k, v in manifest.items() if k != "manifest_id"}
    if (manifest.get("manifest_id") != expected_manifest_id
            or payload_sha256(body) != expected_manifest_id):
        raise ValueError("context manifest external pin mismatch")
    if manifest["source_sha256"] != _sources():
        raise ValueError("context preparation source hash changed")

    def read(ref):
        if ref != file_ref(root, ref["path"]):
            raise ValueError("prepared asset hash mismatch")
        return (root / ref["path"]).read_bytes()

    for ref in manifest["history_access"]:
        read(ref)
    for key in ("canonical_state", "capture"):
        read(manifest[key])
    if workloads.tree_sha256(root / "workspace") != manifest["workspace_sha256"]:
        raise ValueError("prepared workspace hash changed")
    report = json.loads(read(manifest["report"]))
    bundle = json.loads(read(manifest["bundle"]))
    state_root = root / manifest["state_dir"]
    if (state_root.resolve() != (root / "control/state").resolve()
            or not state_root.resolve().is_relative_to(root.resolve())):
        raise ValueError("unexpected state directory")
    before = _files(state_root)
    results = {}
    with Store(state_root, read_only=True) as store:
        for kind, arm in manifest["arms"].items():
            data, prompt = read(arm["context"]), read(arm["prompt"])
            binding = json.loads(read(arm["binding"]))
            if (prompt != COMMON + data + REPORT_PREFIX + canonical_json(report).encode() + SUFFIX
                    or arm["context_byte_span"] != [len(COMMON), len(COMMON) + len(data)]
                    or arm["report_sha256"] != payload_sha256(report)):
                raise ValueError("delivered prompt composition mismatch")
            if kind == "torc_capsule":
                if binding != bundle["binding"]:
                    raise ValueError("capsule binding mismatch")
                result = verify_capsule_context(
                    store, manifest["projection_id"], manifest["projection_record_sha256"],
                    bundle, report, expected_binding_id=arm["binding_id"],
                    delivered_context=data, current_bindings=report["base_bindings"])
            else:
                result = verify_context(
                    binding, report, expected_binding_id=arm["binding_id"], context_kind=kind,
                    context_identity="full-retained-notes-v0", context=data,
                    current_bindings=report["base_bindings"])
            if result["status"] == "stale":
                raise ValueError("prepared lineage is stale")
            results[kind] = result
    if before != _files(state_root):
        raise ValueError("verification modified preparation state")
    return results


def replay(destination):
    """Return a stable overview; full manifests, bindings and state remain beside it."""
    root = Path(destination)
    if root.exists():
        raise ValueError("replay destination already exists")
    root.mkdir(parents=True, mode=0o700)
    tasks = {}
    for identity in workloads.TASKS:
        manifest = prepare(identity, root / identity)
        tasks[identity] = {key: manifest[key] for key in (
            "manifest_id", "workspace_sha256", "carry_limit_words", "capsule_omissions",
            "history_kind", "canonical_author", "state_store_unchanged_during_verification",
            "native_arms_ready", "launch_authorized", "bridge")}
        tasks[identity]["arms"] = {kind: {key: arm[key] for key in (
            "context", "prompt", "context_bytes", "prompt_bytes", "report_sha256")}
            for kind, arm in manifest["arms"].items()}
    return {"schema_version": VERSION, "live_model_trials": 0,
            "evidence_kind": "operator_authored_task_contexts", "source_sha256": _sources(),
            "tasks": tasks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare")
    preparation.add_argument("workload", choices=workloads.TASKS)
    preparation.add_argument("--destination", required=True, type=Path)
    preparation.add_argument("--carry-limit", default=400, type=int)
    verification = commands.add_parser("verify")
    verification.add_argument("--root", required=True, type=Path)
    verification.add_argument("--expected-manifest-id", required=True)
    replay_command = commands.add_parser("replay")
    replay_command.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.workload, args.destination, carry_limit=args.carry_limit)
    elif args.command == "verify":
        manifest = json.loads((args.root / "contexts-manifest.json").read_text())
        result = verify(args.root, manifest, expected_manifest_id=args.expected_manifest_id)
    else:
        result = replay(args.destination)
    print(json.dumps(result, indent=2, sort_keys=True))

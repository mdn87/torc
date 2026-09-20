from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .artifacts.acceptance import accept_project_snapshot
from .artifacts.collection import collect_evidence_bundle
from .artifacts.producer import CommandProjectSnapshotProducer
from .artifacts.render import render_snapshot_html
from .artifacts.storage import ArtifactStore
from .artifacts.validation import validate_project_snapshot
from .artifacts.view import build_current_snapshot_view, build_snapshot_view
from .demo import inspect_lineage, run_demo
from .errors import TorcError
from .experiment_adapters import adapter_for
from .experiment_lanes import (
    materialize_compiled_prompt,
    materialize_native_persistence,
    materialize_torc_projection,
    record_torc_reconstruction,
)
from .experiment_runs import (
    append_target_attempt,
    assert_manifest_adapter,
    build_artifact_manifest,
    build_visible_workspace,
    load_run,
    prepare_run,
    select_final_attempt,
    verify_experiment_run,
    write_canonical_artifact,
    write_stage_receipt,
)
from .experiment_scoring import score_run
from .operator import (
    branch_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    load_json_object,
    operator_lineage_status,
    prepare_operator_handoff,
    prepare_operator_recovery,
    resolve_operator_handoff,
    resolve_operator_recovery,
    rollback_operator_lineage,
    validate_canonical_state,
    validate_handoff_plan,
    validate_lineage_creation,
)
from .store import Store
from .verify import verify_store
from .visibility import build_lineage_explanation, render_lineage_explanation
from .vocabulary import HANDOFF_REASON_CODES

_REQUIRED_PATHS = (
    "README.md",
    "AGENTS.md",
    "docs/project-brief.md",
    "docs/architecture.md",
    "docs/domain-model.md",
    "docs/vertical-slice.md",
    "docs/integration-boundaries.md",
    "docs/prompts/CODEX_BOOTSTRAP_PROMPT.md",
    "schemas/lineage-revision.schema.json",
    "schemas/execution-projection.schema.json",
    "schemas/fit-decision.schema.json",
    "schemas/handoff-snapshot.schema.json",
    "schemas/handoff-result.schema.json",
    "schemas/operator-view.schema.json",
    "schemas/evidence-bundle.v1alpha1.schema.json",
    "schemas/project-snapshot.v1alpha1.schema.json",
    "schemas/acceptance-receipt.v1alpha1.schema.json",
    "docs/artifacts/cold-agent-refresh.md",
)


def _find_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "docs").is_dir():
            return candidate
    return None


def _doctor_payload() -> dict[str, object]:
    root = _find_repo_root()
    missing: list[str] = []
    if root is None:
        missing = list(_REQUIRED_PATHS)
    else:
        missing = [path for path in _REQUIRED_PATHS if not (root / path).exists()]

    return {
        "project": "torc",
        "version": __version__,
        "status": "p0_ready" if not missing else "incomplete",
        "implementation_status": "p4_operator_visibility_implemented",
        "roadmap_phase": "p4_complete",
        "repository_root": str(root) if root is not None else None,
        "missing_required_paths": missing,
        "handoff_reason_codes": list(HANDOFF_REASON_CODES),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="torc",
        description="TORC lineage and continuity control plane.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    about = subparsers.add_parser("about", help="Print TORC's architectural purpose.")
    about.add_argument("--json", action="store_true", dest="as_json")

    doctor = subparsers.add_parser("doctor", help="Verify the repository and P0 surface.")
    doctor.add_argument("--json", action="store_true", dest="as_json")

    demo = subparsers.add_parser("demo", help="Run the deterministic P0 handoff.")
    demo.add_argument("--state-dir", type=Path, required=True)
    demo.add_argument("--json", action="store_true", dest="as_json")

    inspect = subparsers.add_parser("inspect", help="Inspect a lineage without mutation.")
    inspect.add_argument("--state-dir", type=Path, required=True)
    inspect.add_argument("--lineage", required=True)
    inspect.add_argument("--json", action="store_true", dest="as_json")

    verify = subparsers.add_parser("verify", help="Verify stored TORC provenance.")
    verify.add_argument("--state-dir", type=Path, required=True)
    verify.add_argument("--lineage")
    verify.add_argument("--json", action="store_true", dest="as_json")

    lineage = subparsers.add_parser(
        "lineage", help="Operate a real local lineage through its authority lease."
    )
    lineage_commands = lineage.add_subparsers(dest="lineage_command", required=True)
    lineage_create = lineage_commands.add_parser("create")
    lineage_create.add_argument("--state-dir", type=Path, required=True)
    lineage_create.add_argument("--lineage", required=True)
    lineage_create.add_argument("--state-file", type=Path, required=True)
    lineage_create.add_argument("--substrate-file", type=Path, required=True)
    lineage_create.add_argument("--activation-id")
    lineage_create.add_argument("--json", action="store_true", dest="as_json")
    lineage_checkpoint = lineage_commands.add_parser("checkpoint")
    lineage_checkpoint.add_argument("--state-dir", type=Path, required=True)
    lineage_checkpoint.add_argument("--lineage", required=True)
    lineage_checkpoint.add_argument("--activation", required=True)
    lineage_checkpoint.add_argument("--state-file", type=Path, required=True)
    lineage_checkpoint.add_argument(
        "--event-type", choices=("checkpoint", "self_model_revised"), default="checkpoint"
    )
    lineage_checkpoint.add_argument(
        "--evidence-ref", action="append", default=[], dest="evidence_refs"
    )
    lineage_checkpoint.add_argument("--json", action="store_true", dest="as_json")
    lineage_status = lineage_commands.add_parser("status")
    lineage_status.add_argument("--state-dir", type=Path, required=True)
    lineage_status.add_argument("--lineage", required=True)
    lineage_status.add_argument("--json", action="store_true", dest="as_json")
    lineage_explain = lineage_commands.add_parser(
        "explain", help="Explain verified authority and continuity provenance."
    )
    lineage_explain.add_argument("--state-dir", type=Path, required=True)
    lineage_explain.add_argument("--lineage", required=True)
    lineage_explain.add_argument("--json", action="store_true", dest="as_json")
    lineage_rollback = lineage_commands.add_parser("rollback")
    lineage_rollback.add_argument("--state-dir", type=Path, required=True)
    lineage_rollback.add_argument("--lineage", required=True)
    lineage_rollback.add_argument("--activation", required=True)
    lineage_rollback.add_argument("--expected-head", required=True)
    lineage_rollback.add_argument("--target-revision", required=True)
    lineage_rollback.add_argument("--operator-ref", required=True)
    lineage_rollback.add_argument("--rationale", required=True)
    lineage_rollback.add_argument(
        "--evidence-ref", action="append", required=True, dest="evidence_refs"
    )
    lineage_rollback.add_argument("--json", action="store_true", dest="as_json")
    lineage_branch = lineage_commands.add_parser("branch")
    lineage_branch.add_argument("--state-dir", type=Path, required=True)
    lineage_branch.add_argument("--source-lineage", required=True)
    lineage_branch.add_argument("--source-activation", required=True)
    lineage_branch.add_argument("--expected-head", required=True)
    lineage_branch.add_argument("--child-lineage", required=True)
    lineage_branch.add_argument("--child-activation", required=True)
    lineage_branch.add_argument("--substrate-file", type=Path, required=True)
    lineage_branch.add_argument("--operator-ref", required=True)
    lineage_branch.add_argument("--target-assignment-ref", required=True)
    lineage_branch.add_argument("--rationale", required=True)
    lineage_branch.add_argument(
        "--evidence-ref", action="append", required=True, dest="evidence_refs"
    )
    lineage_branch.add_argument("--json", action="store_true", dest="as_json")

    handoff = subparsers.add_parser(
        "handoff", help="Prepare or resolve an acceptance-gated lineage handoff."
    )
    handoff_commands = handoff.add_subparsers(dest="handoff_command", required=True)
    handoff_prepare = handoff_commands.add_parser("prepare")
    handoff_prepare.add_argument("--state-dir", type=Path, required=True)
    handoff_prepare.add_argument("--lineage", required=True)
    handoff_prepare.add_argument("--source-activation", required=True)
    handoff_prepare.add_argument("--plan-file", type=Path, required=True)
    handoff_prepare.add_argument("--json", action="store_true", dest="as_json")
    handoff_resolve = handoff_commands.add_parser("resolve")
    handoff_resolve.add_argument("--state-dir", type=Path, required=True)
    handoff_resolve.add_argument("--handoff", required=True)
    handoff_resolve.add_argument("--target-activation", required=True)
    handoff_resolve.add_argument("--reconstruction-file", type=Path, required=True)
    handoff_resolve.add_argument("--json", action="store_true", dest="as_json")

    recovery = subparsers.add_parser(
        "recovery", help="Prepare or resolve operator-declared activation recovery."
    )
    recovery_commands = recovery.add_subparsers(
        dest="recovery_command", required=True
    )
    recovery_prepare = recovery_commands.add_parser("prepare")
    recovery_prepare.add_argument("--state-dir", type=Path, required=True)
    recovery_prepare.add_argument("--lineage", required=True)
    recovery_prepare.add_argument("--failed-activation", required=True)
    recovery_prepare.add_argument("--plan-file", type=Path, required=True)
    recovery_prepare.add_argument(
        "--evidence-ref", action="append", required=True, dest="evidence_refs"
    )
    recovery_prepare.add_argument("--json", action="store_true", dest="as_json")
    recovery_resolve = recovery_commands.add_parser("resolve")
    recovery_resolve.add_argument("--state-dir", type=Path, required=True)
    recovery_resolve.add_argument("--handoff", required=True)
    recovery_resolve.add_argument("--target-activation", required=True)
    recovery_resolve.add_argument(
        "--reconstruction-file", type=Path, required=True
    )
    recovery_resolve.add_argument("--json", action="store_true", dest="as_json")

    experiment = subparsers.add_parser(
        "experiment", help="Prepare and operate a P1a experiment run."
    )
    experiment_commands = experiment.add_subparsers(
        dest="experiment_command", required=True
    )
    prepare = experiment_commands.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument(
        "--lane",
        required=True,
        choices=("compiled-prompt", "native-persistence", "torc"),
    )
    prepare.add_argument("--run-dir", type=Path, required=True)
    prepare.add_argument("--run-id")
    prepare.add_argument("--json", action="store_true", dest="as_json")
    source = experiment_commands.add_parser("source")
    source.add_argument("--run-dir", type=Path, required=True)
    source.add_argument("--adapter", choices=("codex", "replay"), required=True)
    source.add_argument("--json", action="store_true", dest="as_json")
    target = experiment_commands.add_parser("target")
    target.add_argument("--run-dir", type=Path, required=True)
    target.add_argument(
        "--adapter", choices=("claude-code", "replay"), required=True
    )
    target.add_argument("--json", action="store_true", dest="as_json")
    score = experiment_commands.add_parser("score")
    score.add_argument("--run-dir", type=Path, required=True)
    score.add_argument("--json", action="store_true", dest="as_json")
    experiment_inspect = experiment_commands.add_parser("inspect")
    experiment_inspect.add_argument("--run-dir", type=Path, required=True)
    experiment_inspect.add_argument("--json", action="store_true", dest="as_json")
    experiment_verify = experiment_commands.add_parser("verify")
    experiment_verify.add_argument("--run-dir", type=Path, required=True)
    experiment_verify.add_argument("--json", action="store_true", dest="as_json")

    artifact = subparsers.add_parser(
        "artifact", help="Collect, validate, accept, and render project snapshots."
    )
    artifact_commands = artifact.add_subparsers(
        dest="artifact_command", required=True
    )
    artifact_collect = artifact_commands.add_parser("collect")
    artifact_collect.add_argument("--repository", type=Path, default=Path.cwd())
    artifact_collect.add_argument("--config", type=Path, required=True)
    artifact_collect.add_argument(
        "--store", type=Path, default=Path(".lugos/artifacts/project-snapshot")
    )
    artifact_collect.add_argument("--out", type=Path)
    artifact_collect.add_argument("--json", action="store_true", dest="as_json")
    artifact_validate = artifact_commands.add_parser("validate")
    artifact_validate.add_argument("candidate", type=Path)
    artifact_validate.add_argument("--evidence", type=Path, required=True)
    artifact_validate.add_argument("--json", action="store_true", dest="as_json")
    artifact_produce = artifact_commands.add_parser("produce")
    artifact_produce.add_argument("--evidence", type=Path, required=True)
    artifact_produce.add_argument(
        "--store", type=Path, default=Path(".lugos/artifacts/project-snapshot")
    )
    artifact_produce.add_argument("--out", type=Path)
    artifact_produce.add_argument("--timeout-seconds", type=float, default=120)
    artifact_produce.add_argument("--json", action="store_true", dest="as_json")
    artifact_produce.add_argument("producer_command", nargs=argparse.REMAINDER)
    artifact_accept = artifact_commands.add_parser("accept")
    artifact_accept.add_argument("candidate", type=Path)
    artifact_accept.add_argument("--evidence", type=Path, required=True)
    artifact_accept.add_argument(
        "--store", type=Path, default=Path(".lugos/artifacts/project-snapshot")
    )
    artifact_accept.add_argument("--json", action="store_true", dest="as_json")
    artifact_current = artifact_commands.add_parser("current")
    artifact_current.add_argument(
        "--store", type=Path, default=Path(".lugos/artifacts/project-snapshot")
    )
    artifact_current.add_argument("--json", action="store_true", dest="as_json")
    artifact_view = artifact_commands.add_parser("view")
    artifact_view.add_argument(
        "--store", type=Path, default=Path(".lugos/artifacts/project-snapshot")
    )
    artifact_view.add_argument("--json", action="store_true", dest="as_json")
    artifact_render = artifact_commands.add_parser("render")
    artifact_render.add_argument("--artifact", required=True)
    artifact_render.add_argument("--evidence", type=Path)
    artifact_render.add_argument("--receipt", type=Path)
    artifact_render.add_argument(
        "--store", type=Path, default=Path(".lugos/artifacts/project-snapshot")
    )
    artifact_render.add_argument("--format", choices=("html",), default="html")
    artifact_render.add_argument("--out", type=Path, required=True)
    artifact_render.add_argument("--json", action="store_true", dest="as_json")

    return parser


def _run_about(as_json: bool) -> int:
    payload = {
        "project": "TORC Plane",
        "purpose": "Lineage and continuity control plane for Lugos agents.",
        "principle": "The agent is the governed lineage, not the transient activation.",
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["project"])
        print(payload["purpose"])
        print(payload["principle"])
    return 0


def _run_doctor(as_json: bool) -> int:
    payload = _doctor_payload()
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"TORC status: {payload['status']}")
        print(f"Implementation: {payload['implementation_status']}")
        missing = payload["missing_required_paths"]
        if missing:
            print("Missing required paths:")
            for path in missing:
                print(f"  - {path}")
    return 0 if not payload["missing_required_paths"] else 1


def _print_payload(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")


def _run_ref(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _experiment_context(run_dir: Path) -> dict[str, object]:
    context = load_run(run_dir)
    context["repo_root"] = _find_repo_root()
    return context


def _source_experiment(run_dir: Path, adapter_name: str) -> dict[str, object]:
    context = _experiment_context(run_dir)
    root = context["run_dir"]
    manifest = context["manifest"]
    assert isinstance(root, Path)
    assert isinstance(manifest, dict)
    assert_manifest_adapter(manifest, "source", adapter_name)
    payload_path = root / "artifacts" / "continuity-payload.json"
    if (root / "receipts" / "payload-frozen.json").is_file():
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "run_id": manifest["run_id"],
            "lane": manifest["selected_lane"],
            "disposition": payload["status"],
            "payload_sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            "idempotent": True,
        }
    repo = context["repo_root"]
    assert isinstance(repo, Path)
    allowlist = [
        (repo / entry["path"], Path(entry["path"]).name)
        for entry in manifest["fixture"]["agent_visible"]
    ]
    visible = build_visible_workspace(root, "source", allowlist)
    context["source_workspace"] = root / "workspaces" / "source"
    context["source_allowed_paths"] = [
        item["path"] for item in visible["allowed_paths"]
    ]
    adapter = adapter_for(adapter_name)
    capture = adapter.capture_source(context)
    capture_path = root / "artifacts" / "source-capture.json"
    write_canonical_artifact(capture_path, capture)
    source_ref = _run_ref(root, capture_path)
    write_stage_receipt(
        root,
        "source-captured",
        [_run_ref(root, root / "fixture-manifest.json")],
        [source_ref],
        evidence={"adapter": adapter_name, "workspace": visible},
    )
    if capture["disposition"] != "accepted":
        return {
            "ok": False,
            "run_id": manifest["run_id"],
            "disposition": capture["disposition"],
            "evidence": capture["harness_evidence"],
        }
    lane = manifest["selected_lane"]
    if lane == "compiled-prompt":
        payload = materialize_compiled_prompt(context, capture)
    elif lane == "native-persistence":
        payload = materialize_native_persistence(
            context, adapter.probe(context, "source")
        )
    else:
        payload = materialize_torc_projection(context, capture)
    write_canonical_artifact(payload_path, payload)
    payload_ref = _run_ref(root, payload_path)
    write_stage_receipt(
        root, "payload-frozen", [source_ref], [payload_ref], evidence={"lane": lane}
    )
    if lane == "native-persistence":
        artifact_manifest = build_artifact_manifest(root)
        verification = verify_experiment_run(root)
        write_stage_receipt(
            root,
            "verified",
            [_run_ref(root, root / "artifacts" / "artifact-manifest.json")],
            [],
            evidence=verification,
        )
        return {
            "ok": verification["valid"],
            "run_id": manifest["run_id"],
            "disposition": "unavailable",
            "artifact_count": len(artifact_manifest["artifacts"]),
        }
    return {
        "ok": True,
        "run_id": manifest["run_id"],
        "lane": lane,
        "payload_sha256": payload_ref["sha256"],
    }


def _target_experiment(run_dir: Path, adapter_name: str) -> dict[str, object]:
    context = _experiment_context(run_dir)
    root = context["run_dir"]
    manifest = context["manifest"]
    repo = context["repo_root"]
    assert isinstance(root, Path)
    assert isinstance(manifest, dict)
    assert isinstance(repo, Path)
    assert_manifest_adapter(manifest, "target", adapter_name)
    payload_path = root / "artifacts" / "continuity-payload.json"
    completed_receipt = root / "receipts" / "target-completed.json"
    if completed_receipt.is_file():
        receipt = json.loads(completed_receipt.read_text(encoding="utf-8"))
        current_hash = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        if receipt["inputs"][0]["sha256"] != current_hash:
            raise TorcError("frozen payload changed; create a new run")
        return {
            "ok": True,
            "run_id": manifest["run_id"],
            "attempt_id": receipt["evidence"]["attempt_id"],
            "disposition": receipt["evidence"]["disposition"],
            "idempotent": True,
        }
    allowlist = [
        (repo / entry["path"], Path(entry["path"]).name)
        for entry in manifest["fixture"]["agent_visible"]
    ]
    allowlist.append((payload_path, "continuity-payload.json"))
    visible = build_visible_workspace(root, "target", allowlist)
    context["target_workspace"] = root / "workspaces" / "target"
    context["target_allowed_paths"] = [
        item["path"] for item in visible["allowed_paths"]
    ]
    adapter = adapter_for(adapter_name)
    started = adapter.start_target(context)
    collected = (
        adapter.collect_target(context)
        if started["disposition"] == "accepted"
        else started
    )
    attempts = sorted((root / "attempts").glob("attempt-*"))
    attempt_id = f"attempt-{len(attempts) + 1:04d}"
    payload_sha = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    disposition = collected["disposition"]
    reconstruction = collected.get("reconstruction", {})
    record = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "activation_ref": started.get("activation_ref"),
        "payload_sha256": payload_sha,
        "started_at": "2026-08-06T12:07:00Z",
        "ended_at": "2026-08-06T12:08:00Z",
        "disposition": disposition,
    }
    stored = append_target_attempt(
        root,
        {
            "attempt_id": attempt_id,
            "record": record,
            "target_output": collected.get("task_output", collected),
            "reconstruction": reconstruction,
        },
    )
    attempt_path = root / "attempts" / attempt_id / "attempt.json"
    if disposition != "accepted":
        return {
            "ok": False,
            "run_id": manifest["run_id"],
            "attempt_id": attempt_id,
            "disposition": disposition,
        }
    write_stage_receipt(
        root,
        "target-completed",
        [_run_ref(root, payload_path)],
        [_run_ref(root, attempt_path)],
        evidence={"attempt_id": attempt_id, "disposition": disposition},
    )
    reference = select_final_attempt(root, attempt_id)
    reconstruction_path = root / "artifacts" / "reconstruction.json"
    outputs = [_run_ref(root, reconstruction_path)]
    if manifest["selected_lane"] == "torc":
        result = record_torc_reconstruction(context, stored, reconstruction)
        result_path = root / "artifacts" / "torc-handoff-result.json"
        write_canonical_artifact(result_path, result)
        outputs.append(_run_ref(root, result_path))
    write_stage_receipt(
        root,
        "reconstruction-recorded",
        [_run_ref(root, attempt_path)],
        outputs,
        evidence={"final_attempt": reference},
    )
    return {
        "ok": True,
        "run_id": manifest["run_id"],
        "attempt_id": attempt_id,
        "disposition": disposition,
    }


def _score_experiment(run_dir: Path) -> dict[str, object]:
    context = load_run(run_dir)
    root = context["run_dir"]
    score_path = root / "artifacts" / "score-report.json"
    if (root / "receipts" / "scored.json").is_file():
        report = json.loads(score_path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "run_id": context["manifest"]["run_id"],
            "score_core_sha256": report["score_core_sha256"],
            "idempotent": True,
        }
    report = score_run(root)
    write_canonical_artifact(score_path, report)
    write_stage_receipt(
        root,
        "scored",
        [
            _run_ref(root, root / "artifacts" / "reconstruction.json"),
            _run_ref(root, root / "artifacts" / "continuity-payload.json"),
        ],
        [_run_ref(root, score_path)],
        evidence={"score_core_sha256": report["score_core_sha256"]},
    )
    build_artifact_manifest(root)
    return {
        "ok": True,
        "run_id": context["manifest"]["run_id"],
        "score_core_sha256": report["score_core_sha256"],
    }


def _verify_experiment(run_dir: Path) -> dict[str, object]:
    verification = verify_experiment_run(run_dir)
    root = run_dir.resolve()
    if verification["valid"]:
        write_stage_receipt(
            root,
            "verified",
            [_run_ref(root, root / "artifacts" / "artifact-manifest.json")],
            [],
            evidence=verification,
        )
    return verification


def _inspect_experiment(run_dir: Path) -> dict[str, object]:
    context = load_run(run_dir)
    root = context["run_dir"]
    receipt_paths = sorted((root / "receipts").glob("*.json"))
    receipts = [
        json.loads(path.read_text(encoding="utf-8")) for path in receipt_paths
    ]
    attempts = []
    for path in sorted((root / "attempts").glob("*/attempt.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        artifact_paths = [
            path.parent / "attempt.json",
            path.parent / "target-output.json",
            path.parent / "reconstruction.json",
        ]
        attempts.append(
            {
                "attempt_id": record["attempt_id"],
                "payload_sha256": record["payload_sha256"],
                "started_at": record["started_at"],
                "ended_at": record["ended_at"],
                "disposition": record["disposition"],
                "artifacts": [_run_ref(root, item) for item in artifact_paths],
            }
        )
    lane = context["manifest"]["selected_lane"]
    disposition = "pending"
    if lane == "native-persistence" and (root / "receipts" / "verified.json").is_file():
        disposition = "unavailable"
    elif attempts:
        disposition = attempts[-1]["disposition"]
    return {
        "schema_version": 1,
        "run_id": context["manifest"]["run_id"],
        "experiment_id": context["manifest"]["experiment_id"],
        "lane": lane,
        "created_at": receipts[0]["recorded_at"],
        "disposition": disposition,
        "stage_receipts": [_run_ref(root, path) for path in receipt_paths],
        "target_attempts": attempts,
        "operator_interventions": [],
        "adapter_evidence": [
            receipt["evidence"]
            for receipt in receipts
            if receipt.get("evidence", {}).get("adapter")
        ],
    }


def _artifact_schema_dir() -> Path:
    packaged = Path(__file__).resolve().parent / "schemas"
    if packaged.is_dir():
        return packaged
    root = _find_repo_root()
    if root is None:
        raise TorcError("could not locate TORC artifact schemas")
    return root / "schemas"


def _load_artifact_record(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TorcError(f"artifact record must be a JSON object: {path}")
    return value


def _write_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _run_artifact(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    action = args.artifact_command
    schemas = _artifact_schema_dir()
    if action == "collect":
        bundle = collect_evidence_bundle(args.repository, args.config, schemas)
        if args.out is not None:
            path = args.out / f"{bundle['bundle_id'].removeprefix('sha256:')}.json"
            write_canonical_artifact(path, bundle)
        else:
            path = ArtifactStore(args.store).write_evidence(bundle)
        return {
            "ok": True,
            "bundle_id": bundle["bundle_id"],
            "path": str(path),
            "warnings": bundle["warnings"],
        }, 0
    if action == "validate":
        snapshot = _load_artifact_record(args.candidate)
        evidence = _load_artifact_record(args.evidence)
        result = validate_project_snapshot(snapshot, evidence, schemas)
        return result.as_dict(), 0 if result.valid else 1
    if action == "produce":
        evidence = _load_artifact_record(args.evidence)
        command = list(args.producer_command)
        if command and command[0] == "--":
            command = command[1:]
        producer = CommandProjectSnapshotProducer(
            command, schemas, timeout_seconds=args.timeout_seconds
        )
        snapshot = producer.produce(evidence)
        if args.out is not None:
            write_canonical_artifact(args.out, snapshot)
            path = args.out
        else:
            store = ArtifactStore(args.store)
            store.write_evidence(evidence)
            path = store.write_candidate(snapshot)
        return {
            "ok": True,
            "artifact_id": snapshot["artifact_id"],
            "evidence_bundle_id": evidence["bundle_id"],
            "path": str(path),
        }, 0
    if action == "accept":
        snapshot = _load_artifact_record(args.candidate)
        evidence = _load_artifact_record(args.evidence)
        receipt = accept_project_snapshot(
            snapshot, evidence, ArtifactStore(args.store), schemas
        )
        return receipt, 0 if receipt["status"] == "accepted" else 1
    store = ArtifactStore(args.store)
    if action == "current":
        snapshot = store.current_artifact()
        receipt = store.receipt_for_artifact(snapshot["artifact_id"])
        return {
            "ok": True,
            "artifact_id": snapshot["artifact_id"],
            "receipt_id": receipt["receipt_id"],
            "status": receipt["status"],
        }, 0
    if action == "view":
        return build_current_snapshot_view(store, schemas), 0
    if action == "render":
        if args.artifact == "current":
            view = build_current_snapshot_view(store, schemas)
        else:
            if args.evidence is None or args.receipt is None:
                raise TorcError(
                    "explicit artifact rendering requires --evidence and --receipt"
                )
            view = build_snapshot_view(
                _load_artifact_record(Path(args.artifact)),
                _load_artifact_record(args.evidence),
                _load_artifact_record(args.receipt),
                schemas,
            )
        snapshot = view["artifact"]
        receipt = view["receipt"]
        _write_html(args.out, render_snapshot_html(snapshot, receipt))
        return {
            "ok": True,
            "artifact_id": snapshot["artifact_id"],
            "receipt_id": receipt["receipt_id"],
            "format": "html",
            "path": str(args.out),
        }, 0
    raise TorcError(f"unsupported artifact command: {action}")


def _load_operator_documents(args: argparse.Namespace) -> dict[str, dict[str, object]]:
    """Load and validate operator documents before a writable store is opened.

    Opening a writable store creates or migrates the database, so malformed
    input has to be rejected first.
    """

    documents: dict[str, dict[str, object]] = {}
    if args.command == "lineage":
        if args.lineage_command in {"create", "checkpoint"}:
            documents["state"] = load_json_object(args.state_file)
        if args.lineage_command in {"create", "branch"}:
            documents["substrate"] = load_json_object(args.substrate_file)
        if args.lineage_command == "create":
            validate_lineage_creation(
                lineage_id=args.lineage,
                canonical_state=documents["state"],
                substrate=documents["substrate"],
                activation_id=args.activation_id,
            )
        elif args.lineage_command == "checkpoint":
            validate_canonical_state(documents["state"])
        return documents
    action = args.handoff_command if args.command == "handoff" else args.recovery_command
    if action == "prepare":
        documents["plan"] = load_json_object(args.plan_file)
        validate_handoff_plan(documents["plan"])
    elif action == "resolve":
        documents["reconstruction"] = load_json_object(args.reconstruction_file)
    return documents


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "about":
        return _run_about(args.as_json)
    if args.command == "doctor":
        return _run_doctor(args.as_json)
    try:
        if args.command == "demo":
            payload = run_demo(args.state_dir)
            _print_payload(payload, args.as_json)
            return 0 if payload["verification"]["valid"] else 1
        if args.command == "inspect":
            with Store(args.state_dir, read_only=True) as store:
                payload = inspect_lineage(store, args.lineage)
            _print_payload(payload, args.as_json)
            return 0 if payload["integrity"]["valid"] else 1
        if args.command == "verify":
            with Store(args.state_dir, read_only=True) as store:
                payload = verify_store(store, args.lineage)
            _print_payload(payload, args.as_json)
            return 0 if payload["valid"] else 1
        if args.command == "artifact":
            payload, status = _run_artifact(args)
            _print_payload(payload, args.as_json)
            return status
        if args.command == "lineage":
            if args.lineage_command == "explain":
                with Store(args.state_dir, read_only=True) as store:
                    payload = build_lineage_explanation(store, args.lineage)
                if args.as_json:
                    print(json.dumps(payload, indent=2, sort_keys=True))
                else:
                    print(render_lineage_explanation(payload))
                return 0 if payload["trusted"] else 1
            if args.lineage_command == "status":
                with Store(args.state_dir, read_only=True) as store:
                    payload = operator_lineage_status(store, args.lineage)
                _print_payload(payload, args.as_json)
                return 0
            documents = _load_operator_documents(args)
            creating = args.lineage_command == "create"
            with Store(args.state_dir, must_exist=not creating) as store:
                if creating:
                    payload = create_operator_lineage(
                        store,
                        lineage_id=args.lineage,
                        canonical_state=documents["state"],
                        substrate=documents["substrate"],
                        activation_id=args.activation_id,
                    )
                elif args.lineage_command == "checkpoint":
                    payload = checkpoint_operator_lineage(
                        store,
                        lineage_id=args.lineage,
                        activation_id=args.activation,
                        canonical_state=documents["state"],
                        event_type=args.event_type,
                        evidence_refs=args.evidence_refs,
                    )
                elif args.lineage_command == "rollback":
                    payload = rollback_operator_lineage(
                        store,
                        lineage_id=args.lineage,
                        activation_id=args.activation,
                        expected_head_revision_id=args.expected_head,
                        target_revision_id=args.target_revision,
                        operator_ref=args.operator_ref,
                        rationale=args.rationale,
                        evidence_refs=args.evidence_refs,
                    )
                elif args.lineage_command == "branch":
                    payload = branch_operator_lineage(
                        store,
                        source_lineage_id=args.source_lineage,
                        source_activation_id=args.source_activation,
                        expected_source_revision_id=args.expected_head,
                        child_lineage_id=args.child_lineage,
                        child_activation_id=args.child_activation,
                        child_substrate=documents["substrate"],
                        operator_ref=args.operator_ref,
                        target_assignment_ref=args.target_assignment_ref,
                        rationale=args.rationale,
                        evidence_refs=args.evidence_refs,
                    )
                else:
                    parser.error(f"Unsupported lineage command: {args.lineage_command}")
            _print_payload(payload, args.as_json)
            return 0 if payload.get("ok", True) else 1
        if args.command == "handoff":
            documents = _load_operator_documents(args)
            with Store(args.state_dir, must_exist=True) as store:
                if args.handoff_command == "prepare":
                    payload = prepare_operator_handoff(
                        store,
                        lineage_id=args.lineage,
                        source_activation_id=args.source_activation,
                        plan=documents["plan"],
                    )
                elif args.handoff_command == "resolve":
                    payload = resolve_operator_handoff(
                        store,
                        handoff_id=args.handoff,
                        target_activation_id=args.target_activation,
                        reconstruction=documents["reconstruction"],
                    )
                else:
                    parser.error(f"Unsupported handoff command: {args.handoff_command}")
            _print_payload(payload, args.as_json)
            return 0 if payload.get("ok", True) else 1
        if args.command == "recovery":
            documents = _load_operator_documents(args)
            with Store(args.state_dir, must_exist=True) as store:
                if args.recovery_command == "prepare":
                    payload = prepare_operator_recovery(
                        store,
                        lineage_id=args.lineage,
                        failed_activation_id=args.failed_activation,
                        plan=documents["plan"],
                        evidence_refs=args.evidence_refs,
                    )
                elif args.recovery_command == "resolve":
                    payload = resolve_operator_recovery(
                        store,
                        handoff_id=args.handoff,
                        target_activation_id=args.target_activation,
                        reconstruction=documents["reconstruction"],
                    )
                else:
                    parser.error(
                        f"Unsupported recovery command: {args.recovery_command}"
                    )
            _print_payload(payload, args.as_json)
            return 0 if payload.get("ok", True) else 1
        if args.command == "experiment":
            action = args.experiment_command
            if action == "prepare":
                payload = prepare_run(
                    args.manifest, args.lane, args.run_dir, run_id=args.run_id
                )
            elif action == "source":
                payload = _source_experiment(args.run_dir, args.adapter)
            elif action == "target":
                payload = _target_experiment(args.run_dir, args.adapter)
            elif action == "score":
                payload = _score_experiment(args.run_dir)
            elif action == "inspect":
                payload = _inspect_experiment(args.run_dir)
            elif action == "verify":
                payload = _verify_experiment(args.run_dir)
            else:
                parser.error(f"Unsupported experiment command: {action}")
            _print_payload(payload, args.as_json)
            return 0 if payload.get("ok", payload.get("valid", True)) else 1
    except (TorcError, OSError, ValueError) as exc:
        payload = {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        _print_payload(payload, getattr(args, "as_json", False))
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

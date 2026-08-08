from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
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
from .store import Store
from .verify import verify_store
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
        "implementation_status": "p0_lineage_handoff_implemented",
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
            with Store(args.state_dir) as store:
                payload = inspect_lineage(store, args.lineage)
            _print_payload(payload, args.as_json)
            return 0 if payload["integrity"]["valid"] else 1
        if args.command == "verify":
            with Store(args.state_dir) as store:
                payload = verify_store(store, args.lineage)
            _print_payload(payload, args.as_json)
            return 0 if payload["valid"] else 1
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

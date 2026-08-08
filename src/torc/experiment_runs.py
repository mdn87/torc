"""Immutable local evidence mechanics for P1a experiment runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .canonical import canonical_json, payload_sha256, utc_now
from .errors import IntegrityError, TorcError
from .store import Store
from .verify import verify_store

Clock = Callable[[], str]
STAGES = (
    "created",
    "source-captured",
    "payload-frozen",
    "target-completed",
    "reconstruction-recorded",
    "scored",
    "verified",
)
_DENIED_PARTS = {"oracle", "scoring", "plans"}
_CREDENTIALS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*\S+"),
)


def _bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_ref(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _bytes_sha256(data),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_canonical_artifact(path: Path | str, payload: Any) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical_json(payload) + "\n").encode("utf-8")
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    return {"path": target.as_posix(), "bytes": len(data), "sha256": _bytes_sha256(data)}


def write_stage_receipt(
    run_dir: Path | str,
    stage: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    *,
    clock: Clock = utc_now,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise TorcError(f"unsupported experiment stage: {stage}")
    root = Path(run_dir).resolve()
    path = root / "receipts" / f"{stage}.json"
    receipt = {
        "schema_version": 1,
        "stage": stage.replace("-", "_"),
        "recorded_at": clock(),
        "inputs": inputs,
        "outputs": outputs,
        "evidence": evidence or {},
    }
    if path.exists():
        existing = _read_json(path)
        comparable = {key: value for key, value in existing.items() if key != "recorded_at"}
        proposed = {key: value for key, value in receipt.items() if key != "recorded_at"}
        if comparable != proposed:
            raise TorcError(f"receipt inputs changed; create a new run: {stage}")
        return existing
    write_canonical_artifact(path, receipt)
    return receipt


def _repo_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise TorcError("could not locate TORC repository root")


def _verified_fixture(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    fixture = manifest["fixture"]
    entries = [*fixture["agent_visible"], fixture["oracle"], fixture["scoring"]]
    normalized: set[str] = set()
    for entry in entries:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise TorcError(f"fixture path must be repository-relative: {entry['path']}")
        key = relative.as_posix().casefold()
        if key in normalized:
            raise TorcError(f"duplicate or case-colliding fixture path: {entry['path']}")
        normalized.add(key)
        path = (repo_root / relative).resolve()
        if not path.is_relative_to(repo_root) or not path.is_file():
            raise TorcError(f"fixture file is unavailable: {entry['path']}")
        actual = _bytes_sha256(path.read_bytes())
        if actual != entry["sha256"]:
            raise IntegrityError(f"fixture hash mismatch: {entry['path']}")
    return fixture


def prepare_run(
    manifest_path: Path | str,
    lane: str,
    run_dir: Path | str,
    *,
    run_id: str | None = None,
    clock: Clock = utc_now,
) -> dict[str, Any]:
    if lane not in {"compiled-prompt", "native-persistence", "torc"}:
        raise TorcError(f"unsupported experiment lane: {lane}")
    source = Path(manifest_path).resolve()
    repo_root = _repo_root(source.parent)
    manifest = _read_json(source)
    fixture = _verified_fixture(manifest, repo_root)
    resolved_run_id = run_id or f"{manifest['experiment_id']}-{lane}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", resolved_run_id):
        raise TorcError(
            "run identifier must use letters, digits, dots, dashes, or underscores"
        )
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    frozen = dict(manifest)
    frozen["selected_lane"] = lane
    frozen["run_id"] = resolved_run_id
    if (root / "manifest.json").exists():
        if _read_json(root / "manifest.json") != frozen:
            raise TorcError("run directory is already bound to different inputs")
        if (root / "fixture-manifest.json").exists():
            if _read_json(root / "fixture-manifest.json") != fixture:
                raise TorcError("run directory fixture manifest changed")
            if (root / "receipts" / "created.json").exists():
                return {
                    "ok": True,
                    "run_id": resolved_run_id,
                    "lane": lane,
                    "manifest_sha256": _bytes_sha256(
                        (root / "manifest.json").read_bytes()
                    ),
                    "fixture_manifest_sha256": _bytes_sha256(
                        (root / "fixture-manifest.json").read_bytes()
                    ),
                    "idempotent": True,
                }
    manifest_ref = write_canonical_artifact(root / "manifest.json", frozen)
    fixture_ref = write_canonical_artifact(root / "fixture-manifest.json", fixture)
    outputs = [
        _file_ref(root / "manifest.json", root),
        _file_ref(root / "fixture-manifest.json", root),
    ]
    write_stage_receipt(root, "created", [], outputs, clock=clock)
    return {
        "ok": True,
        "run_id": resolved_run_id,
        "lane": lane,
        "manifest_sha256": manifest_ref["sha256"],
        "fixture_manifest_sha256": fixture_ref["sha256"],
    }


def load_run(run_dir: Path | str) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise TorcError(f"experiment run is not prepared: {root}")
    return {"run_dir": root, "manifest": _read_json(manifest_path)}


def assert_manifest_adapter(
    manifest: dict[str, Any], stage: str, adapter_name: str
) -> None:
    if stage not in {"source", "target"}:
        raise TorcError(f"unsupported adapter stage: {stage}")
    if adapter_name not in manifest["adapters"][stage]:
        raise TorcError(
            f"adapter {adapter_name!r} is not registered for {stage} in the manifest"
        )


def build_visible_workspace(
    run_dir: Path | str,
    role: str,
    allowlist: list[tuple[Path | str, str]],
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    workspace = root / "workspaces" / role
    workspace.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for source_value, destination_value in allowlist:
        source = Path(source_value).resolve()
        relative = Path(destination_value)
        if relative.is_absolute() or ".." in relative.parts:
            raise TorcError(f"workspace path escapes its root: {destination_value}")
        parts = {part.casefold() for part in relative.parts}
        if parts & _DENIED_PARTS or relative.name.casefold() in {
            ".env",
            "environment.json",
            "score-report.json",
        }:
            raise TorcError(f"runner-only material cannot enter a workspace: {relative}")
        key = relative.as_posix().casefold()
        if key in seen:
            raise TorcError(f"duplicate or case-colliding workspace path: {relative}")
        seen.add(key)
        if not source.is_file():
            raise TorcError(f"workspace source is not a file: {source}")
        destination = (workspace / relative).resolve()
        if not destination.is_relative_to(workspace):
            raise TorcError(f"workspace destination escapes its root: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.is_symlink():
            raise TorcError(f"workspace symlink is forbidden: {relative}")
        shutil.copyfile(source, destination)
        data = destination.read_bytes()
        entries.append(
            {
                "path": relative.as_posix(),
                "bytes": len(data),
                "sha256": _bytes_sha256(data),
            }
        )
    visible = {
        "schema_version": 1,
        "role": role,
        "allowed_paths": sorted(entries, key=lambda item: item["path"]),
    }
    write_canonical_artifact(workspace / "visible-workspace-manifest.json", visible)
    return visible


def append_target_attempt(
    run_dir: Path | str,
    attempt: dict[str, Any],
    *,
    clock: Clock = utc_now,
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    attempt_id = attempt["attempt_id"]
    directory = root / "attempts" / attempt_id
    if directory.exists():
        existing = _read_json(directory / "attempt.json")
        if any(
            existing.get(key) != value for key, value in attempt["record"].items()
        ):
            raise TorcError(f"attempt is immutable: {attempt_id}")
        return existing
    record = dict(attempt["record"])
    record.setdefault("started_at", clock())
    record.setdefault("ended_at", clock())
    write_canonical_artifact(directory / "target-output.json", attempt["target_output"])
    reconstruction_ref = write_canonical_artifact(
        directory / "reconstruction.json", attempt["reconstruction"]
    )
    record["artifacts"] = {
        "target_output": f"attempts/{attempt_id}/target-output.json",
        "reconstruction": f"attempts/{attempt_id}/reconstruction.json",
        "reconstruction_sha256": reconstruction_ref["sha256"],
    }
    write_canonical_artifact(directory / "attempt.json", record)
    return record


def select_final_attempt(run_dir: Path | str, attempt_id: str) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    attempt_path = root / "attempts" / attempt_id / "attempt.json"
    record = _read_json(attempt_path)
    reconstruction_path = root / record["artifacts"]["reconstruction"]
    reference = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "path": record["artifacts"]["reconstruction"],
        "sha256": _bytes_sha256(reconstruction_path.read_bytes()),
    }
    write_canonical_artifact(root / "artifacts" / "reconstruction.json", reference)
    return reference


def build_artifact_manifest(
    run_dir: Path | str, *, clock: Clock = utc_now
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    excluded = {
        "artifacts/artifact-manifest.json",
        "receipts/verified.json",
    }
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded or path.name.startswith("."):
            continue
        data = path.read_bytes()
        artifacts.append(
            {
                "path": relative,
                "media_type": (
                    "application/json" if path.suffix == ".json" else "application/octet-stream"
                ),
                "bytes": len(data),
                "sha256": _bytes_sha256(data),
            }
        )
    payload = {
        "schema_version": 1,
        "run_id": _read_json(root / "manifest.json")["run_id"],
        "created_at": clock(),
        "artifacts": artifacts,
    }
    write_canonical_artifact(root / "artifacts" / "artifact-manifest.json", payload)
    return payload


def scan_artifacts_for_credentials(run_dir: Path | str) -> list[dict[str, str]]:
    root = Path(run_dir).resolve()
    findings = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in _CREDENTIALS:
            if pattern.search(text):
                findings.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "finding": "credential-like pattern",
                    }
                )
                break
    return findings


def verify_experiment_run(run_dir: Path | str) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    manifest = _read_json(root / "manifest.json")
    fixture = _read_json(root / "fixture-manifest.json")
    repo_root = _repo_root(Path(__file__))
    _verified_fixture({"fixture": fixture}, repo_root)
    artifact_manifest = _read_json(root / "artifacts" / "artifact-manifest.json")
    errors = []
    excluded = {
        "artifacts/artifact-manifest.json",
        "receipts/verified.json",
    }
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() not in excluded
        and not path.name.startswith(".")
    }
    recorded_paths = {entry["path"] for entry in artifact_manifest["artifacts"]}
    for path in sorted(actual_paths - recorded_paths):
        errors.append(f"unmanifested artifact: {path}")
    for path in sorted(recorded_paths - actual_paths):
        errors.append(f"manifest references absent artifact: {path}")
    for entry in artifact_manifest["artifacts"]:
        path = root / entry["path"]
        if not path.is_file():
            errors.append(f"missing artifact: {entry['path']}")
            continue
        data = path.read_bytes()
        if len(data) != entry["bytes"] or _bytes_sha256(data) != entry["sha256"]:
            errors.append(f"artifact hash mismatch: {entry['path']}")
    receipt_names = {path.stem for path in (root / "receipts").glob("*.json")}
    prerequisites = {
        "source-captured": "created",
        "payload-frozen": "source-captured",
        "target-completed": "payload-frozen",
        "reconstruction-recorded": "target-completed",
        "scored": "reconstruction-recorded",
    }
    for stage, prerequisite in prerequisites.items():
        if stage in receipt_names and prerequisite not in receipt_names:
            errors.append(f"receipt {stage} is missing prerequisite {prerequisite}")
    for receipt_path in sorted((root / "receipts").glob("*.json")):
        receipt = _read_json(receipt_path)
        for reference in (*receipt.get("inputs", []), *receipt.get("outputs", [])):
            linked = root / reference["path"]
            if not linked.is_file():
                errors.append(
                    f"receipt {receipt_path.stem} references absent {reference['path']}"
                )
            elif _bytes_sha256(linked.read_bytes()) != reference["sha256"]:
                errors.append(
                    f"receipt {receipt_path.stem} hash mismatch: {reference['path']}"
                )
    lane = manifest["selected_lane"]
    payload = _read_json(root / "artifacts" / "continuity-payload.json")
    if payload["lane"] != lane:
        errors.append("payload lane does not match manifest")
    if lane == "native-persistence":
        forbidden = [
            root / "receipts" / "target-completed.json",
            root / "artifacts" / "reconstruction.json",
            root / "artifacts" / "score-report.json",
        ]
        if payload["status"] != "unavailable" or any(path.exists() for path in forbidden):
            errors.append("native-persistence unavailable artifact set is invalid")
        disposition = "unavailable"
    else:
        for required in (
            root / "receipts" / "target-completed.json",
            root / "receipts" / "reconstruction-recorded.json",
            root / "receipts" / "scored.json",
            root / "artifacts" / "reconstruction.json",
            root / "artifacts" / "score-report.json",
        ):
            if not required.is_file():
                errors.append(f"missing completed-run artifact: {required.relative_to(root)}")
        if (root / "artifacts" / "reconstruction.json").is_file():
            final = _read_json(root / "artifacts" / "reconstruction.json")
            reconstruction = root / final["path"]
            if (
                not reconstruction.is_file()
                or _bytes_sha256(reconstruction.read_bytes()) != final["sha256"]
            ):
                errors.append("final-attempt reconstruction reference is invalid")
            target_receipt = _read_json(root / "receipts" / "target-completed.json")
            if target_receipt["evidence"]["attempt_id"] != final["attempt_id"]:
                errors.append("target-completed does not identify the final attempt")
            attempt = _read_json(
                root / "attempts" / final["attempt_id"] / "attempt.json"
            )
            if attempt["payload_sha256"] != _bytes_sha256(
                (root / "artifacts" / "continuity-payload.json").read_bytes()
            ):
                errors.append("final attempt does not reference the frozen payload")
        if (root / "artifacts" / "score-report.json").is_file():
            score = _read_json(root / "artifacts" / "score-report.json")
            if score["score_core_sha256"] != payload_sha256(score["score_core"]):
                errors.append("score core hash mismatch")
            if score["scorer_version"] != manifest["scoring"]["scorer_version"]:
                errors.append("score version does not match manifest")
        if lane == "torc":
            with Store(root / "torc-state") as store:
                torc_verification = verify_store(store, "p1a-lineage")
            if not torc_verification["valid"]:
                errors.append("Lane C TORC provenance is invalid")
        disposition = "accepted" if not errors else "failed"
    findings = scan_artifacts_for_credentials(root)
    if findings:
        errors.append("credential-like material detected")
    return {
        "valid": not errors,
        "run_id": manifest["run_id"],
        "lane": lane,
        "disposition": disposition if not errors else "failed",
        "errors": errors,
        "credential_scan": {"best_effort": True, "findings": findings},
        "artifact_manifest_sha256": payload_sha256(artifact_manifest),
    }

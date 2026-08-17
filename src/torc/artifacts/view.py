"""Fail-closed derived read view for the accepted current snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from torc.errors import IntegrityError

from .storage import ArtifactStore
from .validation import validate_acceptance_receipt, validate_project_snapshot


def build_current_snapshot_view(
    store: ArtifactStore, schema_dir: Path | str
) -> dict[str, Any]:
    """Revalidate the current artifact and its immutable supporting records."""

    artifact = store.current_artifact()
    bundle_ref = artifact.get("evidence_bundle")
    bundle_id = bundle_ref.get("bundle_id") if isinstance(bundle_ref, dict) else None
    if not isinstance(bundle_id, str):
        raise IntegrityError("Project Snapshot has no Evidence Bundle identity")

    evidence_bundle = store.evidence_bundle(bundle_id)
    receipt = store.receipt_for_artifact(str(artifact["artifact_id"]))
    snapshot_result = validate_project_snapshot(artifact, evidence_bundle, schema_dir)
    if not snapshot_result.valid:
        raise IntegrityError(
            "Project Snapshot failed read validation: " + "; ".join(snapshot_result.errors)
        )
    receipt_result = validate_acceptance_receipt(receipt, schema_dir)
    if not receipt_result.valid:
        raise IntegrityError(
            "Acceptance Receipt failed read validation: " + "; ".join(receipt_result.errors)
        )
    if receipt.get("artifact_id") != artifact.get("artifact_id"):
        raise IntegrityError("Acceptance Receipt does not reference the current artifact")
    if receipt.get("evidence_bundle_id") != bundle_id:
        raise IntegrityError("Acceptance Receipt does not reference the current Evidence Bundle")
    if receipt.get("status") != "accepted" or receipt.get("errors"):
        raise IntegrityError("Acceptance Receipt does not record an accepted artifact")
    if any(check.get("status") != "passed" for check in receipt.get("checks", [])):
        raise IntegrityError("Acceptance Receipt contains a failed acceptance check")

    return {
        "report_kind": "project_snapshot_view",
        "derived": True,
        "canonical": False,
        "trusted": True,
        "artifact": artifact,
        "evidence_bundle": evidence_bundle,
        "receipt": receipt,
    }

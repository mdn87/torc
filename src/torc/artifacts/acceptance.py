"""Fail-closed validation receipts and accepted-pointer advancement."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from torc import __version__
from torc.canonical import utc_now
from torc.errors import IntegrityError

from .identity import content_id, content_id_is_valid, seal_content_id
from .storage import ArtifactStore
from .validation import validate_acceptance_receipt, validate_project_snapshot

Clock = Callable[[], str]


def accept_project_snapshot(
    snapshot: dict[str, Any],
    evidence_bundle: dict[str, Any],
    store: ArtifactStore,
    schema_dir: Path | str,
    *,
    clock: Clock = utc_now,
) -> dict[str, Any]:
    """Record validation and publish only after the accepted receipt is durable."""

    result = validate_project_snapshot(snapshot, evidence_bundle, schema_dir)
    artifact_id = content_id(snapshot, "artifact_id")
    bundle_id = content_id(evidence_bundle, "bundle_id")
    receipt = seal_content_id(
        {
            "schema": "urn:lugos:artifact:acceptance-receipt:v1alpha1",
            "receipt_id": "",
            "artifact_id": artifact_id,
            "evidence_bundle_id": bundle_id,
            "validated_at": clock(),
            "validator": {"name": "torc", "version": __version__},
            "status": "accepted" if result.valid else "rejected",
            "checks": result.checks,
            "warnings": result.warnings,
            "errors": result.errors,
        },
        "receipt_id",
    )
    if content_id_is_valid(evidence_bundle, "bundle_id"):
        store.write_evidence(evidence_bundle)
    if content_id_is_valid(snapshot, "artifact_id"):
        store.write_candidate(snapshot)
    receipt_validation = validate_acceptance_receipt(receipt, schema_dir)
    if not receipt_validation.valid:
        raise IntegrityError(
            "generated Acceptance Receipt is invalid: "
            + "; ".join(receipt_validation.errors)
        )
    store.write_receipt(receipt)
    if receipt["status"] == "accepted":
        store.publish_accepted(snapshot, receipt)
    return receipt

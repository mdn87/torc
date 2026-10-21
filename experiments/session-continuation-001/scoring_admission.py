"""Pure admission of externally pinned execution-owner evidence for scoring.

The caller must obtain both expected digests from trusted owner storage. A
digest supplied beside its record detects later mutation but does not
authenticate the execution owner. This module never executes candidate code.
"""

from __future__ import annotations

from collections.abc import Mapping

from torc.canonical import payload_sha256

from workloads import prepare_score, tree_sha256

PACKET_FIELDS = {"trial_id", "candidate_sha256", "scoring_refs"}
RECEIPT_FIELDS = {
    "trial_id",
    "attempt_id",
    "candidate_sha256",
    "packet_sha256",
    "owner_receipt_ref",
    "status",
    "capture_complete",
    "process_tree_absent",
}
TERMINAL_STATUSES = {"completed", "failed"}


def _pinned_hash(record, expected, label):
    if not isinstance(record, Mapping):
        raise ValueError(f"{label} must be a record")
    observed = payload_sha256(record)
    if observed != expected:
        raise ValueError(f"{label} external pin mismatch")
    return observed


def freeze_candidate(
    workload_id,
    candidate,
    destination,
    *,
    trial_id,
    owner_receipt,
    expected_receipt_sha256,
    packet,
    expected_packet_sha256,
):
    """Validate owner evidence, then create an arm-blind scoring copy.

    This consumes supplied evidence only. It does not authenticate the supplied
    pins, invoke a general verifier, or execute candidate code or a scorer.
    """
    packet_hash = _pinned_hash(packet, expected_packet_sha256, "packet")
    receipt_hash = _pinned_hash(
        owner_receipt, expected_receipt_sha256, "owner receipt"
    )

    if set(packet) != PACKET_FIELDS:
        raise ValueError("packet shape mismatch")
    if not isinstance(trial_id, str) or not trial_id.strip():
        raise ValueError("trial ID is empty")
    if packet["trial_id"] != trial_id:
        raise ValueError("packet trial mismatch")
    if not isinstance(packet["scoring_refs"], list) or not packet["scoring_refs"]:
        raise ValueError("packet scoring refs are missing")

    candidate_hash = tree_sha256(candidate)
    if packet["candidate_sha256"] != candidate_hash:
        raise ValueError("packet candidate mismatch")

    missing = sorted(RECEIPT_FIELDS - set(owner_receipt))
    if missing:
        raise ValueError("owner receipt missing fields: " + ", ".join(missing))
    if owner_receipt["status"] not in TERMINAL_STATUSES:
        raise ValueError("owner receipt is not terminal")
    if owner_receipt["capture_complete"] is not True:
        raise ValueError("owner receipt capture is incomplete")
    if owner_receipt["process_tree_absent"] is not True:
        raise ValueError("owner receipt process tree is not absent")
    if not isinstance(owner_receipt["attempt_id"], str) or not owner_receipt[
        "attempt_id"
    ].strip():
        raise ValueError("owner receipt attempt ID is empty")
    if not isinstance(owner_receipt["owner_receipt_ref"], str) or not owner_receipt[
        "owner_receipt_ref"
    ].strip():
        raise ValueError("owner receipt ref is empty")
    if owner_receipt["trial_id"] != trial_id:
        raise ValueError("owner receipt trial mismatch")
    if owner_receipt["candidate_sha256"] != candidate_hash:
        raise ValueError("owner receipt candidate mismatch")
    if owner_receipt["packet_sha256"] != packet_hash:
        raise ValueError("owner receipt packet mismatch")

    job = prepare_score(workload_id, candidate, destination)
    if tree_sha256(candidate) != candidate_hash:
        raise ValueError("candidate changed after scoring freeze")
    if job.get("candidate_sha256") != candidate_hash:
        raise ValueError("scoring job candidate mismatch")
    if job.get("requires_qualified_isolated_execution") is not True:
        raise ValueError("scoring job does not require qualified isolated execution")
    return {
        "job": job,
        "owner_receipt_sha256": receipt_hash,
        "packet_sha256": packet_hash,
        "requires_qualified_isolated_execution": True,
    }

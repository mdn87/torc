"""TORC-owned thread lineage bindings and checkpoint acceptance decisions."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from .canonical import canonical_json, seal_record, utc_now
from .errors import CheckpointConflictError, LeaseConflictError, ThreadCheckpointError
from .ids import new_id, valid_id
from .store import Store

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def link_thread_to_lineage(
    store: Store,
    *,
    thread_id: str,
    lineage_id: str,
    activation_id: str,
    expected_lineage_head_revision_id: str,
    evidence_refs: list[str],
    link_id: str | None = None,
    linked_at: str | None = None,
) -> dict[str, Any]:
    """Create the sole active primary lineage binding for one LIR thread."""

    identifiers = (
        thread_id,
        lineage_id,
        activation_id,
        expected_lineage_head_revision_id,
    )
    if any(not valid_id(value) for value in identifiers):
        raise ThreadCheckpointError("thread binding identifiers must satisfy the TORC ID contract")
    if not _valid_refs(evidence_refs):
        raise ThreadCheckpointError("thread binding requires unique evidence references")
    link_id = link_id or new_id("thread-link")
    if not valid_id(link_id):
        raise ThreadCheckpointError("thread link identifier must satisfy the TORC ID contract")
    linked_at = linked_at or utc_now()
    _validate_timestamp(linked_at, "thread binding time")

    with store.transaction(immediate=True):
        existing_row = store.connection.execute(
            "SELECT payload_json FROM thread_lineage_bindings WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if existing_row is not None:
            existing = json.loads(existing_row["payload_json"])
            if existing["lineage_id"] != lineage_id:
                raise ThreadCheckpointError("thread already has a primary lineage")
            if existing["link_id"] != link_id:
                raise ThreadCheckpointError("thread binding already exists under a different link")
            return existing

        try:
            authority = store.current_authority(lineage_id)
        except LeaseConflictError as exc:
            raise ThreadCheckpointError("thread binding requires active lineage authority") from exc
        if (
            authority["activation_id"] != activation_id
            or authority["lineage_head_revision_id"] != expected_lineage_head_revision_id
        ):
            raise ThreadCheckpointError(
                "thread binding requires active lineage authority at the expected head"
            )

        record = seal_record(
            {
                "schema_version": 1,
                "link_id": link_id,
                "thread_id": thread_id,
                "lineage_id": lineage_id,
                "relationship": "thread_carried_by_lineage",
                "authority": {
                    "activation_id": authority["activation_id"],
                    "lease_id": authority["lease_id"],
                    "lineage_head_revision_id": authority["lineage_head_revision_id"],
                },
                "evidence_refs": list(evidence_refs),
                "linked_at": linked_at,
            }
        )
        store.connection.execute(
            """INSERT INTO thread_lineage_bindings
               (link_id, thread_id, lineage_id, relationship, payload_json)
               VALUES (?, ?, ?, 'thread_carried_by_lineage', ?)""",
            (link_id, thread_id, lineage_id, canonical_json(record)),
        )
        store.connection.execute(
            """INSERT INTO thread_accepted_heads
               (thread_id, lineage_id, decision_id, checkpoint_ref,
                checkpoint_sha256, updated_at)
               VALUES (?, ?, NULL, NULL, NULL, NULL)""",
            (thread_id, lineage_id),
        )
    return record


def record_checkpoint_decision(
    store: Store,
    *,
    thread_id: str,
    checkpoint_ref: str,
    checkpoint_sha256: str,
    disposition: str,
    activation_id: str,
    expected_accepted_checkpoint_ref: str | None,
    policy_version: str,
    reason_codes: list[str],
    evidence_refs: list[str],
    decision_id: str | None = None,
    decided_at: str | None = None,
) -> dict[str, Any]:
    """Append a decision and atomically advance the accepted head when accepted."""

    identifiers = (thread_id, checkpoint_ref, activation_id, policy_version)
    if any(not valid_id(value) for value in identifiers):
        raise ThreadCheckpointError(
            "checkpoint decision identifiers must satisfy the TORC ID contract"
        )
    if expected_accepted_checkpoint_ref is not None and not valid_id(
        expected_accepted_checkpoint_ref
    ):
        raise ThreadCheckpointError(
            "expected checkpoint reference must satisfy the TORC ID contract"
        )
    if not isinstance(checkpoint_sha256, str) or _SHA256_PATTERN.fullmatch(
        checkpoint_sha256
    ) is None:
        raise ThreadCheckpointError(
            "checkpoint SHA-256 must be 64 lowercase hexadecimal characters"
        )
    if disposition not in {"accepted", "rejected"}:
        raise ThreadCheckpointError("checkpoint disposition must be accepted or rejected")
    if not _valid_refs(reason_codes):
        raise ThreadCheckpointError("checkpoint decision requires unique reason codes")
    if not _valid_refs(evidence_refs):
        raise ThreadCheckpointError("checkpoint decision requires unique evidence references")
    decision_id = decision_id or new_id("checkpoint-decision")
    if not valid_id(decision_id):
        raise ThreadCheckpointError(
            "checkpoint decision identifier must satisfy the TORC ID contract"
        )
    if decided_at is not None:
        _validate_timestamp(decided_at, "checkpoint decision time")

    with store.transaction(immediate=True):
        existing_row = store.connection.execute(
            "SELECT payload_json FROM thread_checkpoint_decisions WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if existing_row is not None:
            existing = json.loads(existing_row["payload_json"])
            if _matches_replay(
                existing,
                thread_id=thread_id,
                checkpoint_ref=checkpoint_ref,
                checkpoint_sha256=checkpoint_sha256,
                disposition=disposition,
                activation_id=activation_id,
                expected_accepted_checkpoint_ref=expected_accepted_checkpoint_ref,
                policy_version=policy_version,
                reason_codes=reason_codes,
                evidence_refs=evidence_refs,
            ):
                return existing
            raise ThreadCheckpointError(
                "checkpoint decision ID already exists with different content"
            )

        binding = get_thread_binding(store, thread_id)
        lineage_id = binding["lineage_id"]
        try:
            authority = store.current_authority(lineage_id)
        except LeaseConflictError as exc:
            raise ThreadCheckpointError(
                "checkpoint decision requires active lineage authority"
            ) from exc
        if authority["activation_id"] != activation_id:
            raise ThreadCheckpointError("checkpoint decision requires active lineage authority")

        head = store.connection.execute(
            "SELECT * FROM thread_accepted_heads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        if head is None:
            raise ThreadCheckpointError("thread accepted-head record is missing")
        if head["checkpoint_ref"] != expected_accepted_checkpoint_ref:
            raise CheckpointConflictError(
                "accepted checkpoint head differs from the expected accepted checkpoint head"
            )

        effective_decided_at = decided_at or utc_now()
        record = seal_record(
            {
                "schema_version": 1,
                "decision_id": decision_id,
                "thread_id": thread_id,
                "lineage_id": lineage_id,
                "checkpoint_ref": checkpoint_ref,
                "checkpoint_sha256": checkpoint_sha256,
                "disposition": disposition,
                "expected_accepted_checkpoint_ref": expected_accepted_checkpoint_ref,
                "authority": {
                    "activation_id": authority["activation_id"],
                    "lease_id": authority["lease_id"],
                    "lineage_head_revision_id": authority["lineage_head_revision_id"],
                },
                "policy_version": policy_version,
                "reason_codes": list(reason_codes),
                "evidence_refs": list(evidence_refs),
                "decided_at": effective_decided_at,
            }
        )
        store.connection.execute(
            """INSERT INTO thread_checkpoint_decisions
               (decision_id, thread_id, lineage_id, checkpoint_ref,
                checkpoint_sha256, disposition, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                decision_id,
                thread_id,
                lineage_id,
                checkpoint_ref,
                checkpoint_sha256,
                disposition,
                canonical_json(record),
            ),
        )
        if disposition == "accepted":
            cursor = store.connection.execute(
                """UPDATE thread_accepted_heads
                   SET decision_id = ?, checkpoint_ref = ?, checkpoint_sha256 = ?, updated_at = ?
                   WHERE thread_id = ? AND (
                     (checkpoint_ref IS NULL AND ? IS NULL) OR checkpoint_ref = ?
                   )""",
                (
                    decision_id,
                    checkpoint_ref,
                    checkpoint_sha256,
                    effective_decided_at,
                    thread_id,
                    expected_accepted_checkpoint_ref,
                    expected_accepted_checkpoint_ref,
                ),
            )
            if cursor.rowcount != 1:
                raise CheckpointConflictError("accepted checkpoint head changed before commit")
    return record


def get_thread_binding(store: Store, thread_id: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT payload_json FROM thread_lineage_bindings WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if row is None:
        raise ThreadCheckpointError(f"thread has no primary lineage binding: {thread_id}")
    return json.loads(row["payload_json"])


def get_checkpoint_decision(store: Store, decision_id: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT payload_json FROM thread_checkpoint_decisions WHERE decision_id = ?",
        (decision_id,),
    ).fetchone()
    if row is None:
        raise ThreadCheckpointError(f"checkpoint decision not found: {decision_id}")
    return json.loads(row["payload_json"])


def accepted_thread_checkpoint(store: Store, thread_id: str) -> dict[str, Any] | None:
    row = store.connection.execute(
        "SELECT decision_id FROM thread_accepted_heads WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if row is None:
        raise ThreadCheckpointError(f"thread has no primary lineage binding: {thread_id}")
    if row["decision_id"] is None:
        return None
    return get_checkpoint_decision(store, row["decision_id"])


def _matches_replay(existing: dict[str, Any], **expected: Any) -> bool:
    return (
        existing.get("thread_id") == expected["thread_id"]
        and existing.get("checkpoint_ref") == expected["checkpoint_ref"]
        and existing.get("checkpoint_sha256") == expected["checkpoint_sha256"]
        and existing.get("disposition") == expected["disposition"]
        and existing.get("authority", {}).get("activation_id") == expected["activation_id"]
        and existing.get("expected_accepted_checkpoint_ref")
        == expected["expected_accepted_checkpoint_ref"]
        and existing.get("policy_version") == expected["policy_version"]
        and existing.get("reason_codes") == expected["reason_codes"]
        and existing.get("evidence_refs") == expected["evidence_refs"]
    )


def _valid_refs(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(valid_id(item) for item in value)
        and len(value) == len(set(value))
    )


def _validate_timestamp(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ThreadCheckpointError(f"{label} must be UTC RFC 3339")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThreadCheckpointError(f"{label} must be UTC RFC 3339") from exc

"""TORC-owned close intents for race-safe LIR thread closure."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from .canonical import canonical_json, record_hash_is_valid, seal_record, utc_now
from .errors import LeaseConflictError, ThreadCheckpointError
from .ids import new_id, valid_id
from .store import Store

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_CLOSE_SECONDS = 60.0


def prepare_thread_close_intent(
    store: Store,
    *,
    thread_id: str,
    expected_manifest_id: str,
    activation_id: str,
    evidence_refs: list[str],
    close_intent_id: str | None = None,
    issued_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Issue one short-lived intent that blocks thread authority changes."""

    if any(
        not valid_id(value)
        for value in (thread_id, expected_manifest_id, activation_id)
    ):
        raise ThreadCheckpointError(
            "close intent identifiers must satisfy the TORC ID contract"
        )
    if not _valid_refs(evidence_refs):
        raise ThreadCheckpointError("close intent requires unique evidence references")
    close_intent_id = close_intent_id or new_id("thread-close-intent")
    if not valid_id(close_intent_id):
        raise ThreadCheckpointError("close intent ID must satisfy the TORC ID contract")

    effective_issued_at = issued_at or utc_now()
    issued = _timestamp(effective_issued_at, "close intent issue time")
    if expires_at is None:
        expires = issued.timestamp() + _MAX_CLOSE_SECONDS
        effective_expires_at = datetime.fromtimestamp(expires, UTC).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
    else:
        effective_expires_at = expires_at
    expires = _timestamp(effective_expires_at, "close intent expiry")
    duration = (expires - issued).total_seconds()
    if not 0 < duration <= _MAX_CLOSE_SECONDS:
        raise ThreadCheckpointError(
            "close intent expiry must be after issue time and no more than 60 seconds"
        )

    with store.transaction(immediate=True):
        existing_row = store.connection.execute(
            "SELECT payload_json FROM thread_close_intents WHERE close_intent_id = ?",
            (close_intent_id,),
        ).fetchone()
        if existing_row is not None:
            existing = json.loads(existing_row["payload_json"])
            if (
                existing.get("thread_id") == thread_id
                and existing.get("expected_manifest_id") == expected_manifest_id
                and existing.get("authority", {}).get("activation_id") == activation_id
                and existing.get("evidence_refs") == evidence_refs
                and existing.get("issued_at") == effective_issued_at
                and existing.get("expires_at") == effective_expires_at
            ):
                return existing
            raise ThreadCheckpointError(
                "close intent ID already exists with different content"
            )

        _require_thread_open_for_write(
            store,
            thread_id,
            at=effective_issued_at,
        )
        binding = _thread_binding(store, thread_id)
        try:
            authority = store.current_authority(binding["lineage_id"])
        except LeaseConflictError as exc:
            raise ThreadCheckpointError(
                "close intent requires active lineage authority"
            ) from exc
        if authority["activation_id"] != activation_id:
            raise ThreadCheckpointError("close intent requires active lineage authority")
        _require_no_pending_handoff(store, binding["lineage_id"])

        record = seal_record(
            {
                "schema_version": 1,
                "close_intent_id": close_intent_id,
                "thread_id": thread_id,
                "lineage_id": binding["lineage_id"],
                "expected_manifest_id": expected_manifest_id,
                "authority": {
                    "activation_id": authority["activation_id"],
                    "lease_id": authority["lease_id"],
                    "lineage_head_revision_id": authority[
                        "lineage_head_revision_id"
                    ],
                },
                "evidence_refs": list(evidence_refs),
                "issued_at": effective_issued_at,
                "expires_at": effective_expires_at,
            }
        )
        store.connection.execute(
            """INSERT INTO thread_close_intents
               (close_intent_id, thread_id, lineage_id, expected_manifest_id,
                activation_id, lease_id, lineage_head_revision_id,
                issued_at, expires_at, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                close_intent_id,
                thread_id,
                binding["lineage_id"],
                expected_manifest_id,
                authority["activation_id"],
                authority["lease_id"],
                authority["lineage_head_revision_id"],
                effective_issued_at,
                effective_expires_at,
                canonical_json(record),
            ),
        )
    return record


def complete_thread_close_intent(
    store: Store,
    *,
    close_intent_id: str,
    manifest_ref: str,
    manifest_sha256: str,
    owner_receipt_ref: str,
    owner_receipt_sha256: str,
    close_result_id: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    """Consume a live intent only after receiving OGMI's closure proof."""

    if any(
        not valid_id(value)
        for value in (close_intent_id, manifest_ref, owner_receipt_ref)
    ):
        raise ThreadCheckpointError(
            "close result identifiers must satisfy the TORC ID contract"
        )
    for label, digest in (
        ("manifest_sha256", manifest_sha256),
        ("owner_receipt_sha256", owner_receipt_sha256),
    ):
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise ThreadCheckpointError(
                f"{label} must be 64 lowercase hexadecimal characters"
            )
    close_result_id = close_result_id or new_id("thread-close-result")
    if not valid_id(close_result_id):
        raise ThreadCheckpointError("close result ID must satisfy the TORC ID contract")
    effective_completed_at = completed_at or utc_now()
    completed = _timestamp(effective_completed_at, "close result completion time")

    with store.transaction(immediate=True):
        existing_row = store.connection.execute(
            """SELECT payload_json FROM thread_close_results
               WHERE close_intent_id = ? OR close_result_id = ?""",
            (close_intent_id, close_result_id),
        ).fetchone()
        if existing_row is not None:
            existing = json.loads(existing_row["payload_json"])
            if (
                existing.get("close_result_id") == close_result_id
                and existing.get("close_intent_id") == close_intent_id
                and existing.get("manifest_ref") == manifest_ref
                and existing.get("manifest_sha256") == manifest_sha256
                and existing.get("owner_receipt_ref") == owner_receipt_ref
                and existing.get("owner_receipt_sha256") == owner_receipt_sha256
                and existing.get("completed_at") == effective_completed_at
            ):
                return existing
            raise ThreadCheckpointError(
                "close intent is already resolved with different content"
            )

        intent = get_thread_close_intent(store, close_intent_id)
        if not record_hash_is_valid(intent):
            raise ThreadCheckpointError("close intent integrity is invalid")
        issued = _timestamp(str(intent["issued_at"]), "close intent issue time")
        expires = _timestamp(str(intent["expires_at"]), "close intent expiry")
        if completed < issued or completed > expires:
            raise ThreadCheckpointError("close intent expired before completion")
        binding = _thread_binding(store, str(intent["thread_id"]))
        if binding["lineage_id"] != intent["lineage_id"]:
            raise ThreadCheckpointError("close intent lineage binding changed")
        try:
            authority = store.current_authority(binding["lineage_id"])
        except LeaseConflictError as exc:
            raise ThreadCheckpointError(
                "close intent authority changed before completion"
            ) from exc
        recorded = intent.get("authority", {})
        if any(
            authority.get(field) != recorded.get(field)
            for field in ("activation_id", "lease_id", "lineage_head_revision_id")
        ):
            raise ThreadCheckpointError(
                "close intent authority changed before completion"
            )
        _require_no_pending_handoff(store, binding["lineage_id"])

        record = seal_record(
            {
                "schema_version": 1,
                "close_result_id": close_result_id,
                "close_intent_id": close_intent_id,
                "thread_id": intent["thread_id"],
                "lineage_id": intent["lineage_id"],
                "manifest_ref": manifest_ref,
                "manifest_sha256": manifest_sha256,
                "owner_receipt_ref": owner_receipt_ref,
                "owner_receipt_sha256": owner_receipt_sha256,
                "completed_at": effective_completed_at,
            }
        )
        store.connection.execute(
            """INSERT INTO thread_close_results
               (close_result_id, close_intent_id, thread_id, lineage_id,
                manifest_ref, manifest_sha256, owner_receipt_ref,
                owner_receipt_sha256, completed_at, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                close_result_id,
                close_intent_id,
                intent["thread_id"],
                intent["lineage_id"],
                manifest_ref,
                manifest_sha256,
                owner_receipt_ref,
                owner_receipt_sha256,
                effective_completed_at,
                canonical_json(record),
            ),
        )
    return record


def get_thread_close_intent(store: Store, close_intent_id: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT payload_json FROM thread_close_intents WHERE close_intent_id = ?",
        (close_intent_id,),
    ).fetchone()
    if row is None:
        raise ThreadCheckpointError(f"close intent not found: {close_intent_id}")
    return json.loads(row["payload_json"])


def find_thread_close_intent(
    store: Store,
    *,
    thread_id: str,
    expected_manifest_id: str,
    effective_at: str,
) -> dict[str, Any] | None:
    """Find the exact intent that covered an OGMI manifest closure time."""

    moment = _timestamp(effective_at, "close intent lookup time")
    rows = store.connection.execute(
        """SELECT payload_json FROM thread_close_intents
           WHERE thread_id = ? AND expected_manifest_id = ?
           ORDER BY issued_at DESC, close_intent_id DESC""",
        (thread_id, expected_manifest_id),
    ).fetchall()
    for row in rows:
        intent = json.loads(row["payload_json"])
        if not record_hash_is_valid(intent):
            raise ThreadCheckpointError("close intent integrity is invalid")
        issued = _timestamp(str(intent["issued_at"]), "close intent issue time")
        expires = _timestamp(str(intent["expires_at"]), "close intent expiry")
        if issued <= moment <= expires:
            return intent
    return None


def get_thread_close_result(store: Store, close_intent_id: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT payload_json FROM thread_close_results WHERE close_intent_id = ?",
        (close_intent_id,),
    ).fetchone()
    if row is None:
        raise ThreadCheckpointError(f"close result not found: {close_intent_id}")
    return json.loads(row["payload_json"])


def _require_thread_open_for_write(
    store: Store,
    thread_id: str,
    *,
    at: str | None = None,
) -> None:
    """Fail any TORC write or grant validation while closing or after close."""

    result = store.connection.execute(
        "SELECT 1 FROM thread_close_results WHERE thread_id = ? LIMIT 1",
        (thread_id,),
    ).fetchone()
    if result is not None:
        raise ThreadCheckpointError("missing_gate:thread_closed")
    effective_at = _timestamp(at or utc_now(), "close-state check time")
    row = store.connection.execute(
        """SELECT expires_at FROM thread_close_intents i
           WHERE i.thread_id = ?
             AND NOT EXISTS (
               SELECT 1 FROM thread_close_results r
               WHERE r.close_intent_id = i.close_intent_id
             )
           ORDER BY i.issued_at DESC, i.close_intent_id DESC
           LIMIT 1""",
        (thread_id,),
    ).fetchone()
    if row is not None and effective_at <= _timestamp(
        str(row["expires_at"]), "close intent expiry"
    ):
        raise ThreadCheckpointError("missing_gate:thread_close_intent")


def _require_grant_not_preceding_close_intent(
    store: Store,
    *,
    thread_id: str,
    granted_at: str,
) -> None:
    """Keep a pre-close grant invalid after its close-intent lease expires."""

    grant_time = _timestamp(granted_at, "continuation grant time")
    rows = store.connection.execute(
        """SELECT payload_json FROM thread_close_intents
           WHERE thread_id = ?
           ORDER BY issued_at DESC, close_intent_id DESC""",
        (thread_id,),
    ).fetchall()
    for row in rows:
        intent = json.loads(row["payload_json"])
        if not record_hash_is_valid(intent):
            raise ThreadCheckpointError("close intent integrity is invalid")
        issued = _timestamp(str(intent["issued_at"]), "close intent issue time")
        if issued >= grant_time:
            raise ThreadCheckpointError(
                "missing_gate:thread_close_intent_history"
            )


def _thread_binding(store: Store, thread_id: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT payload_json FROM thread_lineage_bindings WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    if row is None:
        raise ThreadCheckpointError(f"thread has no primary lineage binding: {thread_id}")
    return json.loads(row["payload_json"])


def _require_no_pending_handoff(store: Store, lineage_id: str) -> None:
    row = store.connection.execute(
        """SELECT h.handoff_id FROM handoffs h
           LEFT JOIN handoff_results r ON r.handoff_id = h.handoff_id
           WHERE h.lineage_id = ? AND r.handoff_result_id IS NULL
           LIMIT 1""",
        (lineage_id,),
    ).fetchone()
    if row is not None:
        raise ThreadCheckpointError(
            f"close intent conflicts with pending handoff: {row['handoff_id']}"
        )


def _valid_refs(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(valid_id(item) for item in value)
        and len(value) == len(set(value))
    )


def _timestamp(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ThreadCheckpointError(f"{label} must be UTC RFC 3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThreadCheckpointError(f"{label} must be UTC RFC 3339") from exc
    if parsed.utcoffset() is None:
        raise ThreadCheckpointError(f"{label} must be UTC RFC 3339")
    return parsed.astimezone(UTC)

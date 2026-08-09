"""Append-only restoration of an earlier canonical lineage state."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .canonical import seal_record, utc_now
from .errors import LeaseConflictError, RollbackError
from .ids import new_id, valid_id
from .store import Store

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def apply_rollback(
    store: Store,
    *,
    lineage_id: str,
    activation_id: str,
    expected_head_revision_id: str,
    target_revision_id: str,
    operator_ref: str,
    rationale: str,
    evidence_refs: list[str],
    revision_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Append a new head restoring one strict ancestor's canonical state."""

    identifiers = (
        lineage_id,
        activation_id,
        expected_head_revision_id,
        target_revision_id,
        operator_ref,
    )
    if any(not valid_id(item) for item in identifiers):
        raise RollbackError("rollback identifiers must satisfy the TORC ID contract")
    if not isinstance(rationale, str) or not rationale.strip():
        raise RollbackError("rollback rationale is required")
    if not _valid_evidence_refs(evidence_refs):
        raise RollbackError("rollback requires unique evidence references")
    recorded_evidence = [target_revision_id, operator_ref, *evidence_refs]
    if len(recorded_evidence) != len(set(recorded_evidence)):
        raise RollbackError("rollback evidence references must be distinct")

    authority = store.current_authority(lineage_id)
    if authority["activation_id"] != activation_id:
        raise LeaseConflictError("activation does not hold lineage authority")
    if authority["lineage_head_revision_id"] != expected_head_revision_id:
        raise LeaseConflictError("lineage head differs from the operator's expected head")

    revisions = store.lineage_revisions(lineage_id)
    revision_ids = [item["revision_id"] for item in revisions]
    if target_revision_id not in revision_ids:
        raise RollbackError("rollback target is not a revision in this lineage")
    head_index = revision_ids.index(expected_head_revision_id)
    target_index = revision_ids.index(target_revision_id)
    if target_index >= head_index:
        raise RollbackError(
            "rollback target must be a strict ancestor of the expected head"
        )

    target = revisions[target_index]
    activation = store.get_activation(activation_id)
    rollback_context = {
        "target_revision_id": target_revision_id,
        "target_revision_sha256": target["integrity"]["canonical_payload_sha256"],
        "rationale": rationale,
        "initiated_by": {"kind": "operator", "ref": operator_ref},
        "evidence_refs": evidence_refs,
        "source_authority": {
            "lineage_head_revision_id": expected_head_revision_id,
            "activation_id": activation_id,
            "lease_id": authority["lease_id"],
        },
    }
    validate_rollback_context(rollback_context)
    current_head = revisions[head_index]
    record = seal_record(
        {
            "schema_version": 1,
            "lineage_id": lineage_id,
            "revision_id": revision_id or new_id("revision"),
            "parent_revision_ids": [expected_head_revision_id],
            "created_at": created_at or utc_now(),
            "event_type": "rollback_applied",
            "actor": {
                "kind": "activation",
                "activation_id": activation_id,
                "substrate_id": activation["substrate_id"],
            },
            "canonical_state": deepcopy(target["canonical_state"]),
            "evidence_refs": recorded_evidence,
            "rollback_context": rollback_context,
        },
        previous_revision_sha256=current_head["integrity"][
            "canonical_payload_sha256"
        ],
    )

    with store.transaction(immediate=True):
        current = store.current_authority(lineage_id)
        if current != authority:
            raise LeaseConflictError("lineage authority changed before rollback append")
        store._insert_revision(record)
        store.connection.execute(
            "UPDATE lineages SET head_revision_id = ? WHERE lineage_id = ?",
            (record["revision_id"], lineage_id),
        )
        store.connection.execute(
            "UPDATE leases SET head_revision_id = ? WHERE lease_id = ?",
            (record["revision_id"], authority["lease_id"]),
        )
        store.connection.execute(
            "UPDATE activations SET revision_id = ? WHERE activation_id = ?",
            (record["revision_id"], activation_id),
        )
    return record


def validate_rollback_context(context: Any) -> None:
    """Validate the structured provenance required by a rollback revision."""

    if not isinstance(context, dict) or set(context) != {
        "target_revision_id",
        "target_revision_sha256",
        "rationale",
        "initiated_by",
        "evidence_refs",
        "source_authority",
    }:
        raise RollbackError("rollback requires structured provenance context")
    if not valid_id(context["target_revision_id"]):
        raise RollbackError("rollback target revision identifier is invalid")
    if not isinstance(context["target_revision_sha256"], str) or not (
        _SHA256_PATTERN.fullmatch(context["target_revision_sha256"])
    ):
        raise RollbackError("rollback target revision hash is invalid")
    if not isinstance(context["rationale"], str) or not context["rationale"].strip():
        raise RollbackError("rollback rationale is required")
    initiated_by = context["initiated_by"]
    if (
        not isinstance(initiated_by, dict)
        or set(initiated_by) != {"kind", "ref"}
        or initiated_by["kind"] != "operator"
        or not valid_id(initiated_by["ref"])
    ):
        raise RollbackError("rollback requires a valid operator reference")
    if not _valid_evidence_refs(context["evidence_refs"]):
        raise RollbackError("rollback requires unique evidence references")
    source_authority = context["source_authority"]
    if (
        not isinstance(source_authority, dict)
        or set(source_authority)
        != {"lineage_head_revision_id", "activation_id", "lease_id"}
        or any(not valid_id(value) for value in source_authority.values())
    ):
        raise RollbackError("rollback source authority context is invalid")


def _valid_evidence_refs(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(valid_id(item) for item in value)
        and len(value) == len(set(value))
    )

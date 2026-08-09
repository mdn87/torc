"""Atomic creation of a new lineage from an authoritative source head."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any

from .canonical import canonical_json, seal_record, utc_now
from .errors import BranchError, LeaseConflictError, NotFoundError
from .ids import new_id, valid_id
from .store import Store

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def create_lineage_branch(
    store: Store,
    *,
    source_lineage_id: str,
    source_activation_id: str,
    expected_source_revision_id: str,
    child_lineage_id: str,
    child_activation_id: str,
    child_substrate: dict[str, Any],
    operator_ref: str,
    target_assignment_ref: str,
    rationale: str,
    evidence_refs: list[str],
    child_revision_id: str | None = None,
    child_lease_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create one independently authoritative child lineage from the source head."""

    substrate_id = child_substrate.get("substrate_id")
    identifiers = (
        source_lineage_id,
        source_activation_id,
        expected_source_revision_id,
        child_lineage_id,
        child_activation_id,
        substrate_id,
        operator_ref,
        target_assignment_ref,
    )
    if any(not valid_id(item) for item in identifiers):
        raise BranchError("branch identifiers must satisfy the TORC ID contract")
    if source_lineage_id == child_lineage_id:
        raise BranchError("child lineage identity must differ from its source")
    if source_activation_id == child_activation_id:
        raise BranchError("child activation identity must differ from its source")
    if not isinstance(rationale, str) or not rationale.strip():
        raise BranchError("branch rationale is required")
    if not _valid_evidence_refs(evidence_refs):
        raise BranchError("branch requires unique evidence references")
    recorded_evidence = [
        expected_source_revision_id,
        operator_ref,
        target_assignment_ref,
        *evidence_refs,
    ]
    if len(recorded_evidence) != len(set(recorded_evidence)):
        raise BranchError("branch evidence references must be distinct")

    child_revision_id = child_revision_id or new_id("revision")
    child_lease_id = child_lease_id or new_id("lease")
    created_at = created_at or utc_now()
    if not valid_id(child_revision_id) or not valid_id(child_lease_id):
        raise BranchError("generated child authority identifiers are invalid")

    with store.transaction(immediate=True):
        source_authority = store.current_authority(source_lineage_id)
        if source_authority["activation_id"] != source_activation_id:
            raise LeaseConflictError("source activation does not hold lineage authority")
        if source_authority["lineage_head_revision_id"] != expected_source_revision_id:
            raise LeaseConflictError("source lineage head differs from the expected head")
        if _row_exists(store, "lineages", "lineage_id", child_lineage_id):
            raise BranchError("child lineage already exists")
        if _row_exists(store, "activations", "activation_id", child_activation_id):
            raise BranchError("child activation already exists")

        source_revision = store.get_revision(expected_source_revision_id)
        source_activation = store.get_activation(source_activation_id)
        if not created_at.endswith("Z"):
            raise BranchError("branch creation time must be UTC RFC 3339")
        try:
            branch_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            source_time = datetime.fromisoformat(
                source_revision["created_at"].replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise BranchError("branch creation time must be RFC 3339") from exc
        if source_time > branch_time:
            raise BranchError("branch cannot predate its source revision")
        _register_substrate_in_transaction(store, child_substrate)
        branch_origin = {
            "source_lineage_id": source_lineage_id,
            "source_revision_id": expected_source_revision_id,
            "source_revision_sha256": source_revision["integrity"][
                "canonical_payload_sha256"
            ],
            "source_activation_id": source_activation_id,
            "source_lease_id": source_authority["lease_id"],
            "rationale": rationale,
            "initiated_by": {"kind": "operator", "ref": operator_ref},
            "target_assignment_ref": target_assignment_ref,
            "evidence_refs": evidence_refs,
            "child_authority": {
                "activation_id": child_activation_id,
                "lease_id": child_lease_id,
                "substrate_id": substrate_id,
            },
        }
        validate_branch_origin(branch_origin)
        revision = seal_record(
            {
                "schema_version": 1,
                "lineage_id": child_lineage_id,
                "revision_id": child_revision_id,
                "parent_revision_ids": [],
                "created_at": created_at,
                "event_type": "branch_created",
                "actor": {
                    "kind": "activation",
                    "activation_id": source_activation_id,
                    "substrate_id": source_activation["substrate_id"],
                },
                "canonical_state": deepcopy(source_revision["canonical_state"]),
                "evidence_refs": recorded_evidence,
                "branch_origin": branch_origin,
            },
            previous_revision_sha256=None,
        )
        store.connection.execute(
            "INSERT INTO lineages VALUES (?, ?, 'active', ?)",
            (child_lineage_id, created_at, child_revision_id),
        )
        store._insert_revision(revision)
        store.connection.execute(
            "INSERT INTO activations VALUES (?, ?, ?, ?, 'active', ?, NULL)",
            (
                child_activation_id,
                child_lineage_id,
                child_revision_id,
                substrate_id,
                created_at,
            ),
        )
        store.connection.execute(
            "INSERT INTO leases VALUES (?, ?, ?, ?, 'active', ?, NULL)",
            (
                child_lease_id,
                child_lineage_id,
                child_revision_id,
                child_activation_id,
                created_at,
            ),
        )
        store.connection.execute(
            """INSERT INTO authority_transitions
               VALUES (?, ?, NULL, ?, NULL, ?, NULL, NULL, ?, ?)""",
            (
                new_id("transition"),
                child_lineage_id,
                child_activation_id,
                child_lease_id,
                child_revision_id,
                created_at,
            ),
        )
    return revision


def validate_branch_origin(origin: Any) -> None:
    """Validate immutable provenance carried by a branch root revision."""

    if not isinstance(origin, dict) or set(origin) != {
        "source_lineage_id",
        "source_revision_id",
        "source_revision_sha256",
        "source_activation_id",
        "source_lease_id",
        "rationale",
        "initiated_by",
        "target_assignment_ref",
        "evidence_refs",
        "child_authority",
    }:
        raise BranchError("branch creation requires structured origin provenance")
    id_fields = (
        "source_lineage_id",
        "source_revision_id",
        "source_activation_id",
        "source_lease_id",
        "target_assignment_ref",
    )
    if any(not valid_id(origin[field]) for field in id_fields):
        raise BranchError("branch origin identifiers are invalid")
    if not isinstance(origin["source_revision_sha256"], str) or not (
        _SHA256_PATTERN.fullmatch(origin["source_revision_sha256"])
    ):
        raise BranchError("branch source revision hash is invalid")
    if not isinstance(origin["rationale"], str) or not origin["rationale"].strip():
        raise BranchError("branch rationale is required")
    initiated_by = origin["initiated_by"]
    if (
        not isinstance(initiated_by, dict)
        or set(initiated_by) != {"kind", "ref"}
        or initiated_by["kind"] != "operator"
        or not valid_id(initiated_by["ref"])
    ):
        raise BranchError("branch requires a valid operator reference")
    if not _valid_evidence_refs(origin["evidence_refs"]):
        raise BranchError("branch requires unique evidence references")
    combined_evidence = [
        origin["source_revision_id"],
        origin["initiated_by"]["ref"],
        origin["target_assignment_ref"],
        *origin["evidence_refs"],
    ]
    if len(combined_evidence) != len(set(combined_evidence)):
        raise BranchError("branch evidence references must be distinct")
    child = origin["child_authority"]
    if (
        not isinstance(child, dict)
        or set(child) != {"activation_id", "lease_id", "substrate_id"}
        or any(not valid_id(value) for value in child.values())
    ):
        raise BranchError("branch child authority context is invalid")


def _register_substrate_in_transaction(
    store: Store, descriptor: dict[str, Any]
) -> None:
    substrate_id = descriptor["substrate_id"]
    try:
        existing = store.get_substrate(substrate_id)
    except NotFoundError:
        store.connection.execute(
            "INSERT INTO substrates VALUES (?, ?)",
            (substrate_id, canonical_json(descriptor)),
        )
        return
    if canonical_json(existing) != canonical_json(descriptor):
        raise BranchError("child substrate already exists with different content")


def _row_exists(store: Store, table: str, column: str, value: str) -> bool:
    return (
        store.connection.execute(
            f"SELECT 1 FROM {table} WHERE {column} = ?", (value,)
        ).fetchone()
        is not None
    )


def _valid_evidence_refs(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(valid_id(item) for item in value)
        and len(value) == len(set(value))
    )

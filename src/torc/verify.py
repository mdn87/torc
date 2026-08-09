"""Provenance, link, authority, and exported-artifact verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical import record_hash_is_valid
from .errors import HandoffError, NotFoundError
from .handoffs import validate_recovery_context
from .store import Store


def verify_store(store: Store, lineage_id: str | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if lineage_id is None:
        lineage_ids = [
            row["lineage_id"]
            for row in store.connection.execute(
                "SELECT lineage_id FROM lineages ORDER BY lineage_id"
            )
        ]
    else:
        lineage_ids = [lineage_id]

    for current_lineage_id in lineage_ids:
        try:
            _verify_lineage(store, current_lineage_id, errors)
        except Exception as exc:  # verification returns structured failures
            _error(errors, "verification_exception", current_lineage_id, str(exc))

    artifact_query = "SELECT * FROM artifacts ORDER BY artifact_id"
    for row in store.connection.execute(artifact_query):
        path = store.state_dir / row["relative_path"]
        if not path.is_file():
            _error(errors, "artifact_missing", row["artifact_id"], str(path))
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != row["content_sha256"]:
            _error(
                errors,
                "artifact_hash_mismatch",
                row["artifact_id"],
                f"expected {row['content_sha256']}, found {actual}",
            )

    return {
        "valid": not errors,
        "schema_version": int(
            store.connection.execute("PRAGMA user_version").fetchone()[0]
        ),
        "lineages_checked": lineage_ids,
        "artifacts_checked": store.connection.execute(
            "SELECT COUNT(*) FROM artifacts"
        ).fetchone()[0],
        "errors": errors,
    }


def _verify_lineage(
    store: Store, lineage_id: str, errors: list[dict[str, str]]
) -> None:
    lineage = store.get_lineage(lineage_id)
    revisions = store.lineage_revisions(lineage_id)
    by_id = {revision["revision_id"]: revision for revision in revisions}
    for index, revision in enumerate(revisions):
        record_id = revision["revision_id"]
        if not record_hash_is_valid(revision):
            _error(errors, "revision_hash_mismatch", record_id, "content hash is invalid")
        parents = revision.get("parent_revision_ids", [])
        expected_parent = None if index == 0 else revisions[index - 1]["revision_id"]
        if parents != ([] if expected_parent is None else [expected_parent]):
            _error(
                errors,
                "revision_parent_mismatch",
                record_id,
                f"expected parent {expected_parent}",
            )
        expected_previous_hash = (
            None
            if expected_parent is None
            else by_id[expected_parent]["integrity"]["canonical_payload_sha256"]
        )
        if (
            revision.get("integrity", {}).get("previous_revision_sha256")
            != expected_previous_hash
        ):
            _error(
                errors,
                "revision_chain_hash_mismatch",
                record_id,
                "previous revision hash does not match parent",
            )
    if not revisions or lineage["head_revision_id"] != revisions[-1]["revision_id"]:
        _error(
            errors,
            "lineage_head_mismatch",
            lineage_id,
            "lineage head is not the final append-only revision",
        )

    _verify_immutable_records(store, lineage_id, errors)
    active_leases = [
        dict(row)
        for row in store.connection.execute(
            "SELECT * FROM leases WHERE lineage_id = ? AND status = 'active'",
            (lineage_id,),
        )
    ]
    if len(active_leases) != 1:
        _error(
            errors,
            "active_lease_count",
            lineage_id,
            f"expected one active lease, found {len(active_leases)}",
        )
    else:
        lease = active_leases[0]
        activation = store.get_activation(lease["activation_id"])
        if lease["head_revision_id"] != lineage["head_revision_id"]:
            _error(
                errors,
                "lease_head_mismatch",
                lease["lease_id"],
                "active lease does not reference the lineage head",
            )
        if activation["state"] != "active" or activation["revision_id"] != lineage[
            "head_revision_id"
        ]:
            _error(
                errors,
                "activation_authority_mismatch",
                activation["activation_id"],
                "authoritative activation is not active at the lineage head",
            )


def _verify_immutable_records(
    store: Store, lineage_id: str, errors: list[dict[str, str]]
) -> None:
    for table, id_column in (
        ("fit_decisions", "fit_decision_id"),
        ("projections", "projection_id"),
        ("handoffs", "handoff_id"),
        ("handoff_results", "handoff_result_id"),
    ):
        rows = store.connection.execute(
            f"SELECT {id_column}, payload_json FROM {table} WHERE lineage_id = ?",
            (lineage_id,),
        )
        for row in rows:
            record = json.loads(row["payload_json"])
            if not record_hash_is_valid(record):
                _error(
                    errors,
                    f"{table.removesuffix('s')}_hash_mismatch",
                    row[id_column],
                    "content hash is invalid",
                )

    revision_ids = {
        row["revision_id"]
        for row in store.connection.execute(
            "SELECT revision_id FROM revisions WHERE lineage_id = ?", (lineage_id,)
        )
    }
    fit_ids = {
        row["fit_decision_id"]
        for row in store.connection.execute(
            "SELECT fit_decision_id FROM fit_decisions WHERE lineage_id = ?",
            (lineage_id,),
        )
    }
    projection_ids = {
        row["projection_id"]
        for row in store.connection.execute(
            "SELECT projection_id FROM projections WHERE lineage_id = ?", (lineage_id,)
        )
    }

    projections = store.list_hashed_records("projections", lineage_id)
    for projection in projections:
        if projection["source_revision_id"] not in revision_ids:
            _error(
                errors,
                "projection_source_missing",
                projection["projection_id"],
                projection["source_revision_id"],
            )
        source_prefix = f"{projection['source_revision_id']}:"
        for section in (
            projection["included_sections"] + projection["omitted_sections"]
        ):
            if not section["source_ref"].startswith(source_prefix):
                _error(
                    errors,
                    "projection_source_ref_invalid",
                    projection["projection_id"],
                    section["source_ref"],
                )

    handoffs = store.list_hashed_records("handoffs", lineage_id)
    handoff_by_id = {record["handoff_id"]: record for record in handoffs}
    for snapshot in handoffs:
        if snapshot["source_revision_id"] not in revision_ids:
            _error(
                errors,
                "handoff_revision_missing",
                snapshot["handoff_id"],
                snapshot["source_revision_id"],
            )
        if snapshot["fit_decision_id"] not in fit_ids:
            _error(
                errors,
                "handoff_fit_missing",
                snapshot["handoff_id"],
                snapshot["fit_decision_id"],
            )
        if snapshot["projection_id"] not in projection_ids:
            _error(
                errors,
                "handoff_projection_missing",
                snapshot["handoff_id"],
                snapshot["projection_id"],
            )
        if snapshot["reason_code"] == "failure_recovery":
            try:
                validate_recovery_context(snapshot.get("recovery_context"))
            except HandoffError as exc:
                _error(
                    errors,
                    "recovery_context_invalid",
                    snapshot["handoff_id"],
                    str(exc),
                )

    results = store.list_hashed_records("handoff_results", lineage_id)
    for result in results:
        snapshot = handoff_by_id.get(result["handoff_id"])
        if snapshot is None:
            _error(
                errors,
                "result_snapshot_missing",
                result["handoff_result_id"],
                result["handoff_id"],
            )
            continue
        if result["lineage_id"] != snapshot["lineage_id"]:
            _error(
                errors,
                "result_snapshot_mismatch",
                result["handoff_result_id"],
                "lineage differs from snapshot",
            )
        if result["disposition"] == "accepted":
            authority = result.get("resulting_authority")
            if not authority:
                _error(
                    errors,
                    "accepted_result_missing_authority",
                    result["handoff_result_id"],
                    "accepted result has no authority record",
                )
                continue
            transition = store.connection.execute(
                """SELECT 1 FROM authority_transitions
                   WHERE handoff_id = ? AND handoff_result_id = ?
                     AND to_activation_id = ? AND to_lease_id = ?
                     AND resulting_revision_id = ?""",
                (
                    result["handoff_id"],
                    result["handoff_result_id"],
                    authority["activation_id"],
                    authority["lease_id"],
                    authority["lineage_head_revision_id"],
                ),
            ).fetchone()
            if transition is None:
                _error(
                    errors,
                    "authority_transition_missing",
                    result["handoff_result_id"],
                    "accepted result has no matching transition",
                )
            if snapshot["reason_code"] == "failure_recovery":
                source_lease = store.connection.execute(
                    "SELECT status, closed_at FROM leases WHERE lease_id = ?",
                    (snapshot["source_lease_id"],),
                ).fetchone()
                if (
                    source_lease is None
                    or source_lease["status"] != "closed"
                    or source_lease["closed_at"] is None
                ):
                    _error(
                        errors,
                        "recovery_source_lease_not_closed",
                        result["handoff_result_id"],
                        snapshot["source_lease_id"],
                    )
                try:
                    source_activation = store.get_activation(
                        snapshot["source_activation_id"]
                    )
                except NotFoundError:
                    source_activation = None
                if (
                    source_activation is None
                    or source_activation["state"] != "failed"
                    or source_activation["ended_at"] is None
                ):
                    _error(
                        errors,
                        "recovery_source_activation_not_failed",
                        result["handoff_result_id"],
                        snapshot["source_activation_id"],
                    )
        elif result.get("resulting_authority") is not None:
            _error(
                errors,
                "rejected_result_has_authority",
                result["handoff_result_id"],
                "rejected result cannot transfer authority",
            )


def _error(
    errors: list[dict[str, str]], code: str, record_id: str, detail: str
) -> None:
    errors.append({"code": code, "record_id": record_id, "detail": detail})


def artifact_metadata(
    store: Store,
    *,
    artifact_id: str,
    record_kind: str,
    record_id: str,
    relative_path: str,
    created_at: str,
) -> dict[str, Any]:
    path = store.state_dir / Path(relative_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with store.connection:
        store.connection.execute(
            "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
            (artifact_id, record_kind, record_id, relative_path, digest, created_at),
        )
    return {
        "artifact_id": artifact_id,
        "record_kind": record_kind,
        "record_id": record_id,
        "relative_path": relative_path,
        "content_sha256": digest,
        "created_at": created_at,
    }

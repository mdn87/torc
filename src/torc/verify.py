"""Provenance, link, authority, and exported-artifact verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .branches import validate_branch_origin
from .canonical import canonical_json, record_hash_is_valid
from .errors import BranchError, HandoffError, NotFoundError, TorcError
from .handoffs import validate_recovery_context
from .rollbacks import validate_rollback_context
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
        # Verification is its own stable output contract; SQLite migrations do
        # not change the meaning or shape of this report.
        "schema_version": 1,
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
        if revision["event_type"] == "rollback_applied":
            _verify_rollback_revision(
                store, lineage_id, revision, index, revisions, by_id, errors
            )
        elif revision.get("rollback_context") is not None:
            _error(
                errors,
                "unexpected_rollback_context",
                record_id,
                "only rollback_applied revisions may carry rollback context",
            )
        if revision["event_type"] == "branch_created":
            _verify_branch_revision(store, lineage_id, revision, index, errors)
        elif revision.get("branch_origin") is not None:
            _error(
                errors,
                "unexpected_branch_origin",
                record_id,
                "only branch_created revisions may carry branch origin",
            )
    if not revisions or lineage["head_revision_id"] != revisions[-1]["revision_id"]:
        _error(
            errors,
            "lineage_head_mismatch",
            lineage_id,
            "lineage head is not the final append-only revision",
        )

    _verify_immutable_records(store, lineage_id, errors)
    _verify_authority_ledger(store, lineage_id, revisions, errors)
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


def _verify_authority_ledger(
    store: Store,
    lineage_id: str,
    revisions: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    """Require the transition ledger to exactly explain acquisition and succession."""

    transitions = [
        dict(row)
        for row in store.connection.execute(
            """SELECT rowid AS sequence, * FROM authority_transitions
               WHERE lineage_id = ? ORDER BY rowid""",
            (lineage_id,),
        )
    ]
    if not transitions:
        _error(errors, "authority_ledger_empty", lineage_id, "no initial transition")
        return

    root = revisions[0]
    initial = transitions[0]
    if (
        initial["from_activation_id"] is not None
        or initial["from_lease_id"] is not None
        or initial["handoff_id"] is not None
        or initial["handoff_result_id"] is not None
        or initial["resulting_revision_id"] != root["revision_id"]
        or root["event_type"] not in {"lineage_created", "branch_created"}
    ):
        _error(
            errors,
            "authority_initial_transition_invalid",
            initial["transition_id"],
            "first transition does not establish root authority",
        )
    initial_lease = store.connection.execute(
        "SELECT * FROM leases WHERE lease_id = ?", (initial["to_lease_id"],)
    ).fetchone()
    if (
        initial_lease is None
        or initial_lease["lineage_id"] != lineage_id
        or initial_lease["activation_id"] != initial["to_activation_id"]
        or initial_lease["issued_at"] != initial["occurred_at"]
    ):
        _error(
            errors,
            "authority_initial_lease_mismatch",
            initial["transition_id"],
            initial["to_lease_id"],
        )
    initial_time = datetime.fromisoformat(
        initial["occurred_at"].replace("Z", "+00:00")
    )
    root_time = datetime.fromisoformat(root["created_at"].replace("Z", "+00:00"))
    try:
        initial_activation = store.get_activation(initial["to_activation_id"])
    except NotFoundError:
        initial_activation = None
    if initial_time < root_time or not _activation_matches_at(
        initial_activation,
        lineage_id,
        initial_activation["substrate_id"] if initial_activation else "",
        initial_time,
    ):
        _error(
            errors,
            "authority_initial_chronology_invalid",
            initial["transition_id"],
            "root or activation occurs after initial authority acquisition",
        )

    accepted_results = {
        row["handoff_result_id"]: json.loads(row["payload_json"])
        for row in store.connection.execute(
            """SELECT handoff_result_id, payload_json FROM handoff_results
               WHERE lineage_id = ? AND disposition = 'accepted'""",
            (lineage_id,),
        )
    }
    snapshots = {
        row["handoff_id"]: json.loads(row["payload_json"])
        for row in store.connection.execute(
            "SELECT handoff_id, payload_json FROM handoffs WHERE lineage_id = ?",
            (lineage_id,),
        )
    }
    explained_results: set[str] = set()
    previous = initial
    previous_time = initial_time
    revision_by_id = {item["revision_id"]: item for item in revisions}
    revision_positions = {
        item["revision_id"]: index for index, item in enumerate(revisions)
    }
    for transition in transitions[1:]:
        result = accepted_results.get(transition["handoff_result_id"])
        snapshot = snapshots.get(transition["handoff_id"])
        if result is None or snapshot is None:
            _error(
                errors,
                "authority_transition_unexplained",
                transition["transition_id"],
                "transition is not backed by an accepted handoff result",
            )
            previous = transition
            continue
        authority = result.get("resulting_authority") or {}
        occurred_at = datetime.fromisoformat(
            transition["occurred_at"].replace("Z", "+00:00")
        )
        prepared_at = datetime.fromisoformat(
            snapshot["prepared_at"].replace("Z", "+00:00")
        )
        resulting_revision = revision_by_id.get(transition["resulting_revision_id"])
        exact = (
            result["handoff_id"] == transition["handoff_id"]
            and result["handoff_result_id"] == transition["handoff_result_id"]
            and snapshot["source_activation_id"] == transition["from_activation_id"]
            and snapshot["source_lease_id"] == transition["from_lease_id"]
            and result["target_activation_id"] == transition["to_activation_id"]
            and authority.get("activation_id") == transition["to_activation_id"]
            and authority.get("lease_id") == transition["to_lease_id"]
            and authority.get("lineage_head_revision_id")
            == transition["resulting_revision_id"]
            and result["resolved_at"] == transition["occurred_at"]
            and resulting_revision is not None
            and resulting_revision["created_at"] == transition["occurred_at"]
        )
        if not exact:
            _error(
                errors,
                "authority_transition_shape_mismatch",
                transition["transition_id"],
                result["handoff_result_id"],
            )
        if (
            occurred_at < previous_time
            or prepared_at > occurred_at
            or revision_positions.get(transition["resulting_revision_id"], -1)
            <= revision_positions.get(previous["resulting_revision_id"], -1)
        ):
            _error(
                errors,
                "authority_transition_chronology_invalid",
                transition["transition_id"],
                "authority transfer is out of append-only chronological order",
            )
        if (
            transition["from_activation_id"] != previous["to_activation_id"]
            or transition["from_lease_id"] != previous["to_lease_id"]
        ):
            _error(
                errors,
                "authority_transition_chain_gap",
                transition["transition_id"],
                "source authority does not match the previous bearer",
            )
        target_lease = store.connection.execute(
            "SELECT * FROM leases WHERE lease_id = ?", (transition["to_lease_id"],)
        ).fetchone()
        source_lease = store.connection.execute(
            "SELECT * FROM leases WHERE lease_id = ?", (transition["from_lease_id"],)
        ).fetchone()
        try:
            source_activation = store.get_activation(transition["from_activation_id"])
            target_activation = store.get_activation(transition["to_activation_id"])
        except NotFoundError:
            source_activation = target_activation = None
        if (
            target_lease is None
            or target_lease["lineage_id"] != lineage_id
            or target_lease["activation_id"] != transition["to_activation_id"]
            or target_lease["issued_at"] != transition["occurred_at"]
        ):
            _error(
                errors,
                "authority_transition_lease_mismatch",
                transition["transition_id"],
                transition["to_lease_id"],
            )
        if (
            not _lease_matches_at(
                source_lease,
                lineage_id,
                transition["from_activation_id"],
                occurred_at,
            )
            or not _activation_matches_at(
                source_activation,
                lineage_id,
                source_activation["substrate_id"] if source_activation else "",
                occurred_at,
            )
            or not _activation_matches_at(
                target_activation,
                lineage_id,
                target_activation["substrate_id"] if target_activation else "",
                occurred_at,
            )
        ):
            _error(
                errors,
                "authority_transition_lifetime_mismatch",
                transition["transition_id"],
                "source or target authority was not live at transfer time",
            )
        explained_results.add(result["handoff_result_id"])
        previous = transition
        previous_time = occurred_at

    missing_results = sorted(set(accepted_results) - explained_results)
    for result_id in missing_results:
        _error(
            errors,
            "accepted_result_unexplained",
            result_id,
            "accepted result has no unique authority transition",
        )
    if len(transitions) != 1 + len(accepted_results):
        _error(
            errors,
            "authority_transition_count_mismatch",
            lineage_id,
            f"expected {1 + len(accepted_results)}, found {len(transitions)}",
        )
    current = store.connection.execute(
        """SELECT l.head_revision_id AS lineage_head_revision_id,
                  a.activation_id, a.substrate_id, x.lease_id
           FROM lineages l
           JOIN leases x ON x.lineage_id = l.lineage_id AND x.status = 'active'
           JOIN activations a ON a.activation_id = x.activation_id
           WHERE l.lineage_id = ?""",
        (lineage_id,),
    ).fetchone()
    if current is None:
        return
    if (
        previous["to_activation_id"] != current["activation_id"]
        or previous["to_lease_id"] != current["lease_id"]
    ):
        _error(
            errors,
            "authority_ledger_current_mismatch",
            lineage_id,
            "final transition target is not the current bearer",
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


def _verify_rollback_revision(
    store: Store,
    lineage_id: str,
    revision: dict[str, Any],
    index: int,
    revisions: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    record_id = revision["revision_id"]
    try:
        validate_rollback_context(revision.get("rollback_context"))
    except TorcError as exc:
        _error(errors, "rollback_context_invalid", record_id, str(exc))
        return
    context = revision["rollback_context"]
    parent_id = revision["parent_revision_ids"][0] if index else None
    if context["source_authority"]["lineage_head_revision_id"] != parent_id:
        _error(errors, "rollback_source_head_mismatch", record_id, str(parent_id))
    target_id = context["target_revision_id"]
    target = by_id.get(target_id)
    if target is None:
        _error(errors, "rollback_target_missing", record_id, target_id)
        return
    target_index = next(
        item_index
        for item_index, item in enumerate(revisions)
        if item["revision_id"] == target_id
    )
    if target_index >= index - 1:
        _error(errors, "rollback_target_not_strict_ancestor", record_id, target_id)
    if (
        context["target_revision_sha256"]
        != target["integrity"]["canonical_payload_sha256"]
    ):
        _error(errors, "rollback_target_hash_mismatch", record_id, target_id)
    if canonical_json(revision["canonical_state"]) != canonical_json(
        target["canonical_state"]
    ):
        _error(errors, "rollback_state_mismatch", record_id, target_id)
    expected_evidence = [
        target_id,
        context["initiated_by"]["ref"],
        *context["evidence_refs"],
    ]
    if revision["evidence_refs"] != expected_evidence:
        _error(errors, "rollback_evidence_mismatch", record_id, "context differs")
    source_authority = context["source_authority"]
    if (
        revision["actor"]["kind"] != "activation"
        or revision["actor"]["activation_id"] != source_authority["activation_id"]
    ):
        _error(errors, "rollback_actor_mismatch", record_id, source_authority["activation_id"])
    try:
        activation = store.get_activation(source_authority["activation_id"])
    except NotFoundError:
        activation = None
    if (
        activation is None
        or activation["lineage_id"] != lineage_id
        or activation["substrate_id"] != revision["actor"]["substrate_id"]
    ):
        _error(
            errors,
            "rollback_activation_mismatch",
            record_id,
            source_authority["activation_id"],
        )
    lease = store.connection.execute(
        """SELECT lineage_id, activation_id, issued_at, closed_at
           FROM leases WHERE lease_id = ?""",
        (source_authority["lease_id"],),
    ).fetchone()
    created_at = datetime.fromisoformat(revision["created_at"].replace("Z", "+00:00"))
    if (
        lease is None
        or lease["lineage_id"] != lineage_id
        or lease["activation_id"] != source_authority["activation_id"]
        or datetime.fromisoformat(lease["issued_at"].replace("Z", "+00:00"))
        > created_at
        or (
            lease["closed_at"] is not None
            and datetime.fromisoformat(lease["closed_at"].replace("Z", "+00:00"))
            < created_at
        )
    ):
        _error(
            errors, "rollback_lease_mismatch", record_id, source_authority["lease_id"]
        )
    transition = store.connection.execute(
        "SELECT 1 FROM authority_transitions WHERE resulting_revision_id = ?",
        (record_id,),
    ).fetchone()
    if transition is not None:
        _error(errors, "rollback_has_authority_transition", record_id, "unexpected")


def _verify_branch_revision(
    store: Store,
    lineage_id: str,
    revision: dict[str, Any],
    index: int,
    errors: list[dict[str, str]],
) -> None:
    record_id = revision["revision_id"]
    try:
        validate_branch_origin(revision.get("branch_origin"))
    except BranchError as exc:
        _error(errors, "branch_origin_invalid", record_id, str(exc))
        return
    origin = revision["branch_origin"]
    created_at = datetime.fromisoformat(revision["created_at"].replace("Z", "+00:00"))
    if index != 0 or revision["parent_revision_ids"]:
        _error(errors, "branch_not_lineage_root", record_id, str(index))
    if origin["source_lineage_id"] == lineage_id:
        _error(errors, "branch_source_identity_reused", record_id, lineage_id)
    try:
        source_revision = store.get_revision(origin["source_revision_id"])
    except NotFoundError:
        source_revision = None
    if source_revision is None or source_revision["lineage_id"] != origin[
        "source_lineage_id"
    ]:
        _error(
            errors, "branch_source_revision_missing", record_id, origin["source_revision_id"]
        )
        return
    if not record_hash_is_valid(source_revision):
        _error(errors, "branch_source_integrity_invalid", record_id, origin["source_revision_id"])
    source_revisions = store.lineage_revisions(origin["source_lineage_id"])
    source_index = next(
        item_index
        for item_index, item in enumerate(source_revisions)
        if item["revision_id"] == origin["source_revision_id"]
    )
    source_created_at = datetime.fromisoformat(
        source_revision["created_at"].replace("Z", "+00:00")
    )
    later_before_branch = any(
        datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        <= created_at
        for item in source_revisions[source_index + 1 :]
    )
    if source_created_at > created_at or later_before_branch:
        _error(
            errors,
            "branch_source_not_head_at_creation",
            record_id,
            origin["source_revision_id"],
        )
    if origin["source_revision_sha256"] != source_revision["integrity"][
        "canonical_payload_sha256"
    ]:
        _error(errors, "branch_source_hash_mismatch", record_id, origin["source_revision_id"])
    if canonical_json(revision["canonical_state"]) != canonical_json(
        source_revision["canonical_state"]
    ):
        _error(errors, "branch_state_mismatch", record_id, origin["source_revision_id"])
    expected_evidence = [
        origin["source_revision_id"],
        origin["initiated_by"]["ref"],
        origin["target_assignment_ref"],
        *origin["evidence_refs"],
    ]
    if revision["evidence_refs"] != expected_evidence:
        _error(errors, "branch_evidence_mismatch", record_id, "context differs")
    try:
        source_activation = store.get_activation(origin["source_activation_id"])
    except NotFoundError:
        source_activation = None
    actor = revision["actor"]
    if (
        not _activation_matches_at(
            source_activation,
            origin["source_lineage_id"],
            actor["substrate_id"],
            created_at,
        )
        or actor["kind"] != "activation"
        or actor["activation_id"] != origin["source_activation_id"]
    ):
        _error(errors, "branch_source_activation_mismatch", record_id, actor["kind"])
    source_lease = store.connection.execute(
        "SELECT * FROM leases WHERE lease_id = ?", (origin["source_lease_id"],)
    ).fetchone()
    if not _lease_matches_at(
        source_lease,
        origin["source_lineage_id"],
        origin["source_activation_id"],
        created_at,
    ):
        _error(errors, "branch_source_lease_mismatch", record_id, origin["source_lease_id"])
    child = origin["child_authority"]
    try:
        child_activation = store.get_activation(child["activation_id"])
    except NotFoundError:
        child_activation = None
    child_lease = store.connection.execute(
        "SELECT * FROM leases WHERE lease_id = ?", (child["lease_id"],)
    ).fetchone()
    if (
        not _activation_matches_at(
            child_activation, lineage_id, child["substrate_id"], created_at
        )
        or not _lease_matches_at(
            child_lease, lineage_id, child["activation_id"], created_at
        )
    ):
        _error(errors, "branch_child_authority_mismatch", record_id, child["activation_id"])
    transition_count = store.connection.execute(
        """SELECT COUNT(*) FROM authority_transitions
           WHERE lineage_id = ? AND from_activation_id IS NULL
             AND from_lease_id IS NULL AND to_activation_id = ?
             AND to_lease_id = ? AND resulting_revision_id = ?
             AND handoff_id IS NULL AND handoff_result_id IS NULL
             AND occurred_at = ?""",
        (
            lineage_id,
            child["activation_id"],
            child["lease_id"],
            record_id,
            revision["created_at"],
        ),
    ).fetchone()[0]
    if transition_count != 1:
        _error(errors, "branch_initial_transition_missing", record_id, child["lease_id"])


def _activation_matches_at(
    activation: Any, lineage_id: str, substrate_id: str, occurred_at: datetime
) -> bool:
    if activation is None:
        return False
    started_at = datetime.fromisoformat(activation["started_at"].replace("Z", "+00:00"))
    ended_at = (
        datetime.fromisoformat(activation["ended_at"].replace("Z", "+00:00"))
        if activation["ended_at"] is not None
        else None
    )
    return (
        activation["lineage_id"] == lineage_id
        and activation["substrate_id"] == substrate_id
        and started_at <= occurred_at
        and (ended_at is None or ended_at >= occurred_at)
    )


def _lease_matches_at(
    lease: Any, lineage_id: str, activation_id: str, occurred_at: datetime
) -> bool:
    if lease is None:
        return False
    issued_at = datetime.fromisoformat(lease["issued_at"].replace("Z", "+00:00"))
    closed_at = (
        datetime.fromisoformat(lease["closed_at"].replace("Z", "+00:00"))
        if lease["closed_at"] is not None
        else None
    )
    return (
        lease["lineage_id"] == lineage_id
        and lease["activation_id"] == activation_id
        and issued_at <= occurred_at
        and (closed_at is None or closed_at >= occurred_at)
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

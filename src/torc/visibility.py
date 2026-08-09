"""Read-only operator explanations derived from verified TORC provenance."""

from __future__ import annotations

import json
from typing import Any

from .errors import NotFoundError
from .store import Store
from .verify import verify_store


def build_lineage_explanation(store: Store, lineage_id: str) -> dict[str, Any]:
    """Explain one lineage from a single consistent, non-mutating snapshot."""

    with store.read_transaction():
        verification = _verify_explanation_scope(store, lineage_id)
        lineage = store.get_lineage(lineage_id)
        head = _head_summary(store, lineage, trusted=verification["valid"])
        base: dict[str, Any] = {
            "schema_version": 1,
            "report_kind": "lineage_explanation",
            "derived": True,
            "canonical": False,
            "trusted": verification["valid"],
            "lineage": {
                "lineage_id": lineage_id,
                "status": lineage["status"],
                "head": {
                    "revision_id": head["revision_id"],
                    "event_type": head["event_type"],
                    "created_at": head["created_at"],
                },
            },
            "current_authority": None,
            "authority_changes": [],
            "handoffs": [],
            "fit_decisions": [],
            "continuity_events": [],
            "relationships": {"branch_origin": None, "child_lineages": []},
            "verification": verification,
            "explanation_complete": verification["valid"],
            "warnings": [],
        }
        if not verification["valid"]:
            base["warnings"] = [
                "Stored provenance is invalid; no authority explanation is asserted."
            ]
            return base

        revisions = store.lineage_revisions(lineage_id)
        activations = {
            item["activation_id"]: item for item in store.list_activations(lineage_id)
        }
        leases = {
            row["lease_id"]: dict(row)
            for row in store.connection.execute(
                "SELECT * FROM leases WHERE lineage_id = ? ORDER BY rowid",
                (lineage_id,),
            )
        }
        substrates = {
            item["substrate_id"]: item for item in store.list_substrates()
        }
        snapshots = store.list_hashed_records("handoffs", lineage_id)
        results = store.list_hashed_records("handoff_results", lineage_id)
        fits = store.list_hashed_records("fit_decisions", lineage_id)
        snapshot_by_id = {item["handoff_id"]: item for item in snapshots}
        result_by_handoff = {item["handoff_id"]: item for item in results}
        fit_by_id = {item["fit_decision_id"]: item for item in fits}
        transitions = [
            dict(row)
            for row in store.connection.execute(
                """SELECT rowid AS sequence, * FROM authority_transitions
                   WHERE lineage_id = ? ORDER BY rowid""",
                (lineage_id,),
            )
        ]

        authority_changes = [
            _authority_change(
                transition,
                revisions=revisions,
                activations=activations,
                leases=leases,
                substrates=substrates,
                snapshots=snapshot_by_id,
                results=result_by_handoff,
                fits=fit_by_id,
            )
            for transition in transitions
        ]
        base["authority_changes"] = authority_changes
        base["handoffs"] = [
            _handoff_summary(
                snapshot,
                result=result_by_handoff.get(snapshot["handoff_id"]),
                fit=fit_by_id[snapshot["fit_decision_id"]],
                current=store.current_authority(lineage_id),
                activations=activations,
            )
            for snapshot in snapshots
        ]
        base["fit_decisions"] = [_fit_summary(fit) for fit in fits]
        base["continuity_events"] = [
            _continuity_event(revision) for revision in revisions
        ]
        base["relationships"] = _relationships(store, lineage_id, revisions)

        current = store.current_authority(lineage_id)
        activation = activations[current["activation_id"]]
        substrate = substrates[activation["substrate_id"]]
        lease = leases[current["lease_id"]]
        acquisition = authority_changes[-1]
        base["current_authority"] = {
            "activation_id": activation["activation_id"],
            "activation_state": activation["state"],
            "substrate_id": substrate["substrate_id"],
            "substrate_label": substrate["label"],
            "adapter": substrate["adapter"],
            "lease_id": lease["lease_id"],
            "lease_status": lease["status"],
            "lease_issued_at": lease["issued_at"],
            "head_revision_id": current["lineage_head_revision_id"],
            "acquired_by_transition_id": acquisition["transition_id"],
            "explanation": acquisition["summary"],
        }
        return base


def _verify_explanation_scope(store: Store, lineage_id: str) -> dict[str, Any]:
    """Verify the requested lineage and every child relationship it would assert."""

    verification = verify_store(store, lineage_id)
    child_ids: set[str] = set()
    for row in store.connection.execute(
        "SELECT lineage_id, payload_json FROM revisions ORDER BY rowid"
    ):
        try:
            revision = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        origin = revision.get("branch_origin")
        if origin and origin.get("source_lineage_id") == lineage_id:
            child_ids.add(row["lineage_id"])
    for child_id in sorted(child_ids):
        child_verification = verify_store(store, child_id)
        verification["lineages_checked"].extend(
            item
            for item in child_verification["lineages_checked"]
            if item not in verification["lineages_checked"]
        )
        verification["errors"].extend(child_verification["errors"])
    verification["valid"] = not verification["errors"]
    return verification


def _head_summary(
    store: Store, lineage: dict[str, Any], *, trusted: bool
) -> dict[str, str]:
    """Return a schema-stable head label even when the stored payload is invalid."""

    stored_head_id = lineage.get("head_revision_id")
    report_head_id = stored_head_id or f"unverified-head-{lineage['lineage_id']}"
    if trusted:
        revision = store.get_revision(stored_head_id)
        return {
            "revision_id": revision["revision_id"],
            "event_type": revision["event_type"],
            "created_at": revision["created_at"],
        }
    try:
        revision = store.get_revision(stored_head_id)
        event_type = str(revision.get("event_type") or "unverified")
        created_at = str(revision.get("created_at") or lineage["created_at"])
    except (KeyError, NotFoundError, TypeError, ValueError):
        event_type = "unverified"
        created_at = lineage["created_at"]
    return {
        "revision_id": report_head_id,
        "event_type": event_type,
        "created_at": created_at,
    }


def render_lineage_explanation(report: dict[str, Any]) -> str:
    """Render the stable report as concise operator-oriented text."""

    lineage = report["lineage"]
    validity = "VALID" if report["trusted"] else "UNTRUSTED"
    lines = [
        f"TORC lineage {lineage['lineage_id']} — {validity}",
        (
            f"Head: {lineage['head']['revision_id']} "
            f"({lineage['head']['event_type']})"
        ),
    ]
    if not report["trusted"]:
        lines.append("Authority: not asserted because provenance verification failed")
        lines.extend(f"Warning: {item}" for item in report["warnings"])
        return "\n".join(lines)

    current = report["current_authority"]
    lines.extend(
        [
            (
                f"Authority: {current['activation_id']} on {current['substrate_id']} "
                f"via {current['lease_id']}"
            ),
            f"Why: {current['explanation']}",
            "",
            "Authority history",
        ]
    )
    for index, change in enumerate(report["authority_changes"], start=1):
        lines.append(f"{index}. {change['summary']}")

    lines.extend(["", "Handoffs"])
    if report["handoffs"]:
        for handoff in report["handoffs"]:
            lines.append(
                f"- {handoff['handoff_id']} {handoff['state'].upper()} — "
                f"{handoff['reason_code']}; {handoff['authority_effect']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "Continuity events"])
    for event in report["continuity_events"]:
        lines.append(
            f"- {event['revision_id']} {event['event_type']} — {event['summary']}"
        )
    return "\n".join(lines)


def _authority_change(
    transition: dict[str, Any],
    *,
    revisions: list[dict[str, Any]],
    activations: dict[str, dict[str, Any]],
    leases: dict[str, dict[str, Any]],
    substrates: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
    fits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    revision = next(
        item
        for item in revisions
        if item["revision_id"] == transition["resulting_revision_id"]
    )
    target = _authority_party(
        transition["to_activation_id"],
        transition["to_lease_id"],
        activations,
        leases,
        substrates,
    )
    source = (
        _authority_party(
            transition["from_activation_id"],
            transition["from_lease_id"],
            activations,
            leases,
            substrates,
        )
        if transition["from_activation_id"] is not None
        else None
    )
    detail: dict[str, Any] | None = None
    if transition["handoff_id"] is None:
        kind = revision["event_type"]
        if kind == "branch_created":
            origin = revision["branch_origin"]
            summary = (
                f"Branch authority began with {target['activation_id']} from "
                f"{origin['source_lineage_id']}:{origin['source_revision_id']}."
            )
            detail = {
                "branch_origin": origin,
                "external_assignment_grants_authority": False,
            }
        else:
            summary = (
                f"Initial authority was acquired by {target['activation_id']} "
                f"on {target['substrate_id']}."
            )
    else:
        snapshot = snapshots[transition["handoff_id"]]
        result = results[transition["handoff_id"]]
        fit = fits[snapshot["fit_decision_id"]]
        kind = (
            "failure_recovery"
            if snapshot["reason_code"] == "failure_recovery"
            else "handoff"
        )
        passed = sum(1 for check in result["checks"] if check["passed"])
        summary = (
            f"Accepted {snapshot['reason_code']} transferred authority from "
            f"{source['activation_id']} to {target['activation_id']} "
            f"after continuity passed {passed}/{len(result['checks'])}."
        )
        detail = {
            "handoff_id": snapshot["handoff_id"],
            "handoff_result_id": result["handoff_result_id"],
            "reason_code": snapshot["reason_code"],
            "rationale": snapshot["rationale"],
            "fit": _fit_summary(fit),
            "acceptance": _acceptance_summary(result),
            "recovery_context": snapshot.get("recovery_context"),
            "fit_selection_grants_authority": False,
        }
    return {
        "sequence": transition["sequence"],
        "transition_id": transition["transition_id"],
        "occurred_at": transition["occurred_at"],
        "kind": kind,
        "from_authority": source,
        "to_authority": target,
        "resulting_revision_id": transition["resulting_revision_id"],
        "summary": summary,
        "detail": detail,
        "record_refs": {
            "handoff_id": transition["handoff_id"],
            "handoff_result_id": transition["handoff_result_id"],
            "resulting_revision_sha256": revision["integrity"][
                "canonical_payload_sha256"
            ],
        },
    }


def _authority_party(
    activation_id: str,
    lease_id: str,
    activations: dict[str, dict[str, Any]],
    leases: dict[str, dict[str, Any]],
    substrates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    activation = activations[activation_id]
    lease = leases[lease_id]
    substrate = substrates[activation["substrate_id"]]
    return {
        "activation_id": activation_id,
        "activation_current_state": activation["state"],
        "substrate_id": substrate["substrate_id"],
        "substrate_label": substrate["label"],
        "lease_id": lease_id,
        "lease_current_status": lease["status"],
    }


def _fit_summary(fit: dict[str, Any]) -> dict[str, Any]:
    selected = next(
        (
            candidate
            for candidate in fit["candidates"]
            if candidate["substrate_id"] == fit["selected_substrate_id"]
        ),
        None,
    )
    return {
        "fit_decision_id": fit["fit_decision_id"],
        "task_phase": fit["task_phase"],
        "requirements": fit["requirements"],
        "selected_substrate_id": fit["selected_substrate_id"],
        "selected_candidate": selected,
        "candidates": fit["candidates"],
        "policy_version": fit["policy_version"],
        "decided_at": fit["decided_at"],
        "selection_grants_execution_authority": False,
    }


def _acceptance_summary(result: dict[str, Any]) -> dict[str, Any]:
    passed = sum(1 for check in result["checks"] if check["passed"])
    return {
        "disposition": result["disposition"],
        "passed_requirements": passed,
        "total_requirements": len(result["checks"]),
        "failed_requirements": [
            check["requirement"] for check in result["checks"] if not check["passed"]
        ],
        "checks": result["checks"],
    }


def _handoff_summary(
    snapshot: dict[str, Any],
    *,
    result: dict[str, Any] | None,
    fit: dict[str, Any],
    current: dict[str, Any],
    activations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    frozen = snapshot["source_authority"]
    mismatches = [
        label
        for label, current_key in (
            ("source head changed", "lineage_head_revision_id"),
            ("source activation changed", "activation_id"),
            ("source lease changed", "lease_id"),
        )
        if frozen[current_key] != current[current_key]
    ]
    if result is None:
        target_id = snapshot.get("target_activation_id")
        candidates = (
            [activations[target_id]]
            if target_id is not None and target_id in activations
            else list(activations.values()) if target_id is None else []
        )
        matching_target = next(
            (
                activation
                for activation in candidates
                if activation["lineage_id"] == snapshot["lineage_id"]
                and activation["revision_id"] == snapshot["source_revision_id"]
                and activation["substrate_id"] == snapshot["target_substrate_id"]
                and activation["state"] == "pending"
            ),
            None,
        )
        if matching_target is None:
            mismatches.append("matching pending target activation unavailable")
        state = "stale" if mismatches else "pending"
        authority_effect = "unchanged; cannot resolve" if mismatches else "not transferred"
        acceptance = None
    else:
        state = result["disposition"]
        authority_effect = (
            "transferred" if result["disposition"] == "accepted" else "unchanged"
        )
        acceptance = _acceptance_summary(result)
        mismatches = []
    return {
        "handoff_id": snapshot["handoff_id"],
        "state": state,
        "can_resolve": result is None and not mismatches,
        "stale_reasons": mismatches,
        "reason_code": snapshot["reason_code"],
        "rationale": snapshot["rationale"],
        "prepared_at": snapshot["prepared_at"],
        "source_authority": frozen,
        "target_activation_id": snapshot.get("target_activation_id"),
        "target_substrate_id": snapshot["target_substrate_id"],
        "fit": _fit_summary(fit),
        "acceptance": acceptance,
        "authority_effect": authority_effect,
        "external_assignment_grants_authority": False,
    }


def _continuity_event(revision: dict[str, Any]) -> dict[str, Any]:
    event_type = revision["event_type"]
    if event_type == "rollback_applied":
        context = revision["rollback_context"]
        summary = (
            f"Canonical state restored from {context['target_revision_id']}; "
            "bearer unchanged."
        )
        related_revision_id = context["target_revision_id"]
        authority_changed = False
    elif event_type == "branch_created":
        origin = revision["branch_origin"]
        summary = (
            f"Independent lineage created from {origin['source_lineage_id']}:"
            f"{origin['source_revision_id']}."
        )
        related_revision_id = origin["source_revision_id"]
        authority_changed = True
    elif event_type == "handoff_accepted":
        summary = "Accepted handoff advanced the head and transferred authority."
        related_revision_id = None
        authority_changed = True
    elif event_type == "lineage_created":
        summary = "Lineage root created; initial authority was established separately."
        related_revision_id = None
        authority_changed = True
    else:
        summary = "Authoritative bearer advanced canonical history without transfer."
        related_revision_id = None
        authority_changed = False
    return {
        "revision_id": revision["revision_id"],
        "created_at": revision["created_at"],
        "event_type": event_type,
        "authority_changed": authority_changed,
        "related_revision_id": related_revision_id,
        "summary": summary,
        "evidence_refs": revision["evidence_refs"],
    }


def _relationships(
    store: Store, lineage_id: str, revisions: list[dict[str, Any]]
) -> dict[str, Any]:
    root = revisions[0]
    origin = root.get("branch_origin")
    children: list[dict[str, Any]] = []
    rows = store.connection.execute(
        "SELECT lineage_id, payload_json FROM revisions ORDER BY rowid"
    ).fetchall()
    for row in rows:
        revision = json.loads(row["payload_json"])
        branch_origin = revision.get("branch_origin")
        if branch_origin and branch_origin["source_lineage_id"] == lineage_id:
            children.append(
                {
                    "lineage_id": row["lineage_id"],
                    "root_revision_id": revision["revision_id"],
                    "source_revision_id": branch_origin["source_revision_id"],
                }
            )
    return {
        "branch_origin": origin,
        "child_lineages": sorted(children, key=lambda item: item["lineage_id"]),
    }

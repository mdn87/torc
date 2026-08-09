"""Thin operator workflow over TORC's existing lineage and handoff domain APIs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .branches import create_lineage_branch
from .canonical import canonical_json, utc_now
from .errors import HandoffError, IntegrityError, NotFoundError
from .fit import evaluate_fit
from .handoffs import expected_reconstruction, prepare_handoff, resolve_handoff
from .ids import new_id, valid_id
from .projections import compile_projection
from .rollbacks import apply_rollback
from .store import Store
from .verify import artifact_metadata, verify_store


def load_json_object(path: Path | str) -> dict[str, Any]:
    """Load one JSON object, rejecting arrays and scalar values."""

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def create_operator_lineage(
    store: Store,
    *,
    lineage_id: str,
    canonical_state: dict[str, Any],
    substrate: dict[str, Any],
    activation_id: str | None = None,
) -> dict[str, Any]:
    """Create a lineage and immediately establish its first authority."""

    _register_substrate_once(store, substrate)
    revision = store.create_lineage(lineage_id, canonical_state)
    activation = store.create_activation(
        lineage_id,
        revision["revision_id"],
        substrate["substrate_id"],
        activation_id=activation_id,
    )
    lease = store.acquire_lease(lineage_id, activation["activation_id"])
    return {
        "ok": True,
        "lineage_id": lineage_id,
        "revision_id": revision["revision_id"],
        "activation_id": activation["activation_id"],
        "lease_id": lease["lease_id"],
        "substrate_id": substrate["substrate_id"],
    }


def checkpoint_operator_lineage(
    store: Store,
    *,
    lineage_id: str,
    activation_id: str,
    canonical_state: dict[str, Any],
    event_type: str = "checkpoint",
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Append a full canonical state through the current authority."""

    _require_integrity(store, lineage_id)
    revision = store.append_revision(
        lineage_id,
        canonical_state,
        event_type=event_type,
        activation_id=activation_id,
        evidence_refs=evidence_refs,
    )
    return {
        "ok": True,
        "lineage_id": lineage_id,
        "revision_id": revision["revision_id"],
        "activation_id": activation_id,
        "event_type": event_type,
    }


def rollback_operator_lineage(
    store: Store,
    *,
    lineage_id: str,
    activation_id: str,
    expected_head_revision_id: str,
    target_revision_id: str,
    operator_ref: str,
    rationale: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    """Append an operator-authorized restoration of a strict ancestor state."""

    _require_integrity(store, lineage_id)
    authority_before = store.current_authority(lineage_id)
    transition_count_before = store.connection.execute(
        "SELECT COUNT(*) FROM authority_transitions WHERE lineage_id = ?",
        (lineage_id,),
    ).fetchone()[0]
    revision = apply_rollback(
        store,
        lineage_id=lineage_id,
        activation_id=activation_id,
        expected_head_revision_id=expected_head_revision_id,
        target_revision_id=target_revision_id,
        operator_ref=operator_ref,
        rationale=rationale,
        evidence_refs=evidence_refs,
    )
    authority_after = store.current_authority(lineage_id)
    transition_count_after = store.connection.execute(
        "SELECT COUNT(*) FROM authority_transitions WHERE lineage_id = ?",
        (lineage_id,),
    ).fetchone()[0]
    verification = verify_store(store, lineage_id)
    return {
        "ok": verification["valid"],
        "lineage_id": lineage_id,
        "from_revision_id": expected_head_revision_id,
        "target_revision_id": target_revision_id,
        "revision_id": revision["revision_id"],
        "activation_id": authority_after["activation_id"],
        "lease_id": authority_after["lease_id"],
        "authority_transferred": (
            authority_before["activation_id"] != authority_after["activation_id"]
            or authority_before["lease_id"] != authority_after["lease_id"]
        ),
        "authority_transition_added": transition_count_after != transition_count_before,
        "verification": verification,
    }


def branch_operator_lineage(
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
) -> dict[str, Any]:
    """Create and verify an independently authoritative child lineage."""

    _require_integrity(store, source_lineage_id)
    source_before = store.current_authority(source_lineage_id)
    revision = create_lineage_branch(
        store,
        source_lineage_id=source_lineage_id,
        source_activation_id=source_activation_id,
        expected_source_revision_id=expected_source_revision_id,
        child_lineage_id=child_lineage_id,
        child_activation_id=child_activation_id,
        child_substrate=child_substrate,
        operator_ref=operator_ref,
        target_assignment_ref=target_assignment_ref,
        rationale=rationale,
        evidence_refs=evidence_refs,
    )
    source_after = store.current_authority(source_lineage_id)
    child_authority = store.current_authority(child_lineage_id)
    source_verification = verify_store(store, source_lineage_id)
    child_verification = verify_store(store, child_lineage_id)
    return {
        "ok": source_verification["valid"] and child_verification["valid"],
        "source_lineage_id": source_lineage_id,
        "source_revision_id": expected_source_revision_id,
        "source_authority_unchanged": source_before == source_after,
        "child_lineage_id": child_lineage_id,
        "child_revision_id": revision["revision_id"],
        "child_activation_id": child_authority["activation_id"],
        "child_lease_id": child_authority["lease_id"],
        "source_verification": source_verification,
        "child_verification": child_verification,
    }


def operator_lineage_status(store: Store, lineage_id: str) -> dict[str, Any]:
    """Return the current authority and active continuity state."""

    lineage = store.get_lineage(lineage_id)
    head = store.get_revision(lineage["head_revision_id"])
    pending = store.connection.execute(
        """SELECT h.handoff_id
           FROM handoffs h
           LEFT JOIN handoff_results r ON r.handoff_id = h.handoff_id
           WHERE h.lineage_id = ? AND r.handoff_result_id IS NULL
           ORDER BY h.rowid""",
        (lineage_id,),
    ).fetchall()
    return {
        "ok": True,
        "lineage_id": lineage_id,
        "head_revision_id": head["revision_id"],
        "head_event_type": head["event_type"],
        "current_authority": store.current_authority(lineage_id),
        "goals": head["canonical_state"]["goals"],
        "commitments": head["canonical_state"]["commitments"],
        "constraints": head["canonical_state"]["constraints"],
        "open_work": head["canonical_state"]["open_work"],
        "pending_handoff_ids": [row["handoff_id"] for row in pending],
        "revision_count": len(store.lineage_revisions(lineage_id)),
    }


def prepare_operator_handoff(
    store: Store,
    *,
    lineage_id: str,
    source_activation_id: str,
    plan: dict[str, Any],
    recovery_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare a bound handoff and export its derived operator artifacts."""

    _require_integrity(store, lineage_id)
    authority = store.current_authority(lineage_id)
    if authority["activation_id"] != source_activation_id:
        raise HandoffError("source activation does not hold lineage authority")
    reason_code = str(plan["reason_code"])
    if reason_code == "failure_recovery" and recovery_context is None:
        raise HandoffError("use the recovery workflow for failure_recovery handoffs")
    if reason_code != "failure_recovery" and recovery_context is not None:
        raise HandoffError("recovery context requires the failure_recovery reason")
    target_activation_id = plan.get("target_activation_id")
    if target_activation_id is not None:
        if not valid_id(target_activation_id):
            raise HandoffError("target activation identifier is invalid")
        if target_activation_id == source_activation_id:
            raise HandoffError("target activation must differ from the source")
        try:
            store.get_activation(target_activation_id)
        except NotFoundError:
            pass
        else:
            raise HandoffError("target activation already exists")

    target_substrate = _required_object(plan, "target_substrate")
    requirements = _required_object(plan, "requirements")
    _register_substrate_once(store, target_substrate)
    fit = evaluate_fit(
        store,
        lineage_id=lineage_id,
        source_revision_id=authority["lineage_head_revision_id"],
        source_substrate_id=authority["substrate_id"],
        task_phase=str(plan["task_phase"]),
        requirements=requirements,
    )
    requested_target = target_substrate["substrate_id"]
    if fit["selected_substrate_id"] != requested_target:
        raise HandoffError(
            "fit evaluation selected "
            f"{fit['selected_substrate_id']!r}, not requested target {requested_target!r}"
        )

    projection = compile_projection(
        store,
        lineage_id=lineage_id,
        source_revision_id=authority["lineage_head_revision_id"],
        target_substrate_id=requested_target,
        budget_limit=int(plan["budget_limit"]),
        handoff_reason=reason_code,
        target_responsibility=str(plan["target_responsibility"]),
    )
    target = store.create_activation(
        lineage_id,
        authority["lineage_head_revision_id"],
        requested_target,
        activation_id=target_activation_id,
    )
    snapshot = prepare_handoff(
        store,
        lineage_id=lineage_id,
        source_activation_id=source_activation_id,
        target_activation_id=target["activation_id"],
        fit_decision_id=fit["fit_decision_id"],
        projection_id=projection["projection_id"],
        reason_code=reason_code,
        rationale=str(plan["rationale"]),
        recovery_context=recovery_context,
        continuity_requirements=plan.get("continuity_requirements"),
    )
    reconstruction = expected_reconstruction(store, snapshot)
    brief_path = _export_text_artifact(
        store,
        record_kind="handoff_brief",
        record_id=snapshot["handoff_id"],
        filename=f"handoff-{_filename_component(snapshot['handoff_id'])}.md",
        content=render_handoff_brief(snapshot, projection, reconstruction),
        created_at=snapshot["prepared_at"],
    )
    reconstruction_path = _export_text_artifact(
        store,
        record_kind="handoff_reconstruction_template",
        record_id=snapshot["handoff_id"],
        filename=f"reconstruction-{_filename_component(snapshot['handoff_id'])}.json",
        content=json.dumps(reconstruction, indent=2, sort_keys=True) + "\n",
        created_at=snapshot["prepared_at"],
    )
    return {
        "ok": True,
        "lineage_id": lineage_id,
        "handoff_id": snapshot["handoff_id"],
        "source_activation_id": source_activation_id,
        "target_activation_id": target["activation_id"],
        "target_substrate_id": requested_target,
        "fit_decision_id": fit["fit_decision_id"],
        "projection_id": projection["projection_id"],
        "authority_transferred": False,
        "brief_path": brief_path,
        "reconstruction_template_path": reconstruction_path,
    }


def prepare_operator_recovery(
    store: Store,
    *,
    lineage_id: str,
    failed_activation_id: str,
    plan: dict[str, Any],
    evidence_refs: list[str],
) -> dict[str, Any]:
    """Prepare an operator-declared recovery without prematurely moving authority."""

    _require_integrity(store, lineage_id)
    if plan.get("reason_code") != "failure_recovery":
        raise HandoffError("recovery plans must use the failure_recovery reason")
    evidence_refs = _nonempty_unique_strings(evidence_refs, "failure evidence")
    operator_ref = _nonempty_string(plan.get("operator_ref"), "operator_ref")
    target_assignment_ref = _nonempty_string(
        plan.get("target_assignment_ref"), "target_assignment_ref"
    )
    authority = store.current_authority(lineage_id)
    if authority["activation_id"] != failed_activation_id:
        raise HandoffError("failed activation does not hold lineage authority")
    recovery_context = {
        "initiator": {"kind": "operator", "ref": operator_ref},
        "failure_kind": "activation_unavailable",
        "observed_at": utc_now(),
        "evidence_refs": evidence_refs,
        "target_assignment_ref": target_assignment_ref,
    }
    payload = prepare_operator_handoff(
        store,
        lineage_id=lineage_id,
        source_activation_id=failed_activation_id,
        plan=plan,
        recovery_context=recovery_context,
    )
    payload["recovery_context"] = recovery_context
    return payload


def resolve_operator_handoff(
    store: Store,
    *,
    handoff_id: str,
    target_activation_id: str,
    reconstruction: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one prepared handoff through its bound target activation."""

    snapshot = store.get_hashed_record("handoffs", "handoff_id", handoff_id)
    _require_integrity(store, snapshot["lineage_id"])
    result = resolve_handoff(
        store,
        handoff_id=handoff_id,
        target_activation_id=target_activation_id,
        reconstruction=reconstruction,
    )
    verification = verify_store(store, snapshot["lineage_id"])
    return {
        "ok": result["disposition"] == "accepted" and verification["valid"],
        "lineage_id": snapshot["lineage_id"],
        "handoff_id": handoff_id,
        "handoff_result_id": result["handoff_result_id"],
        "disposition": result["disposition"],
        "failed_requirements": [
            check["requirement"] for check in result["checks"] if not check["passed"]
        ],
        "current_authority": store.current_authority(snapshot["lineage_id"]),
        "verification": verification,
    }


def resolve_operator_recovery(
    store: Store,
    *,
    handoff_id: str,
    target_activation_id: str,
    reconstruction: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one prepared failure recovery through the normal acceptance gate."""

    snapshot = store.get_hashed_record("handoffs", "handoff_id", handoff_id)
    if snapshot["reason_code"] != "failure_recovery":
        raise HandoffError("handoff is not a failure recovery")
    return resolve_operator_handoff(
        store,
        handoff_id=handoff_id,
        target_activation_id=target_activation_id,
        reconstruction=reconstruction,
    )


def render_handoff_brief(
    snapshot: dict[str, Any],
    projection: dict[str, Any],
    reconstruction: dict[str, Any],
) -> str:
    """Render a human-facing, explicitly non-canonical handoff brief."""

    lines = [
        f"# TORC Handoff {snapshot['handoff_id']}",
        "",
        (
            "> Derived execution artifact. The TORC store and immutable records "
            "are canonical; this file is not."
        ),
        "",
        "## Transfer",
        "",
        f"- Lineage: `{snapshot['lineage_id']}`",
        f"- Source revision: `{snapshot['source_revision_id']}`",
        f"- Source activation: `{snapshot['source_activation_id']}`",
        f"- Intended target activation: `{snapshot.get('target_activation_id')}`",
        f"- Target substrate: `{snapshot['target_substrate_id']}`",
        f"- Reason: `{snapshot['reason_code']}`",
        f"- Rationale: {snapshot['rationale']}",
        "",
        "## Target responsibility",
        "",
        str(reconstruction["current_responsibility"]),
        "",
        "## Required reconstruction",
        "",
        (
            "Copy the supplied reconstruction template, preserve every required field "
            "exactly, and put new conclusions only in `new_inferences`."
        ),
        "",
    ]
    for field in snapshot["continuity_requirements"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Projected continuity", ""])
    for section in projection["included_sections"]:
        lines.extend(
            [
                f"### {section['section_id']}",
                "",
                "```json",
                json.dumps(section["content"], indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    if projection["omitted_sections"]:
        lines.extend(["## Omitted from this projection", ""])
        for section in projection["omitted_sections"]:
            lines.append(f"- `{section['section_id']}`: {section['reason']}")
        lines.append("")
    recovery = snapshot.get("recovery_context")
    if recovery is not None:
        lines.extend(
            [
                "## Recovery declaration",
                "",
                f"- Failure: `{recovery['failure_kind']}`",
                f"- Observed: `{recovery['observed_at']}`",
                f"- Operator reference: `{recovery['initiator']['ref']}`",
                f"- Target assignment: `{recovery['target_assignment_ref']}`",
                "- Evidence: " + ", ".join(
                    f"`{item}`" for item in recovery["evidence_refs"]
                ),
                "",
            ]
        )
    return "\n".join(lines)


def _register_substrate_once(store: Store, substrate: dict[str, Any]) -> None:
    substrate_id = str(substrate["substrate_id"])
    try:
        existing = store.get_substrate(substrate_id)
    except NotFoundError:
        store.register_substrate(substrate)
        return
    if canonical_json(existing) != canonical_json(substrate):
        raise ValueError(f"substrate already exists with different content: {substrate_id}")


def _required_object(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value[key]
    if not isinstance(item, dict):
        raise ValueError(f"handoff plan field must be an object: {key}")
    return item


def _nonempty_string(value: Any, field: str) -> str:
    if not valid_id(value):
        raise HandoffError(f"recovery plan requires a valid {field}")
    return value


def _nonempty_unique_strings(values: Any, field: str) -> list[str]:
    if (
        not isinstance(values, list)
        or not values
        or any(not valid_id(item) for item in values)
        or len(values) != len(set(values))
    ):
        raise HandoffError(f"recovery requires unique {field} references")
    return values


def _require_integrity(store: Store, lineage_id: str) -> None:
    verification = verify_store(store, lineage_id)
    if not verification["valid"]:
        first = verification["errors"][0]
        raise IntegrityError(
            f"lineage integrity failed: {first['code']} ({first['record_id']})"
        )


def _filename_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def _export_text_artifact(
    store: Store,
    *,
    record_kind: str,
    record_id: str,
    filename: str,
    content: str,
    created_at: str,
) -> str:
    relative_path = str(Path("artifacts") / filename).replace("\\", "/")
    path = store.state_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    artifact_metadata(
        store,
        artifact_id=new_id("artifact"),
        record_kind=record_kind,
        record_id=record_id,
        relative_path=relative_path,
        created_at=created_at,
    )
    return relative_path

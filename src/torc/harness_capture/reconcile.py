"""Read-only reconciliation against independent, explicitly bound fixture facts."""

from __future__ import annotations

from copy import deepcopy

from torc.canonical import payload_sha256


def reconcile(manifest: dict, workspace_evidence: dict, *, current_bindings: dict) -> dict:
    """Report holds and stale observations; never infer non-execution or grant retry.

    ``verified_operations`` are independent operation-specific fixture evidence,
    not current-file equality or model prose. An evidence reference identifies
    the assertion's owner; it is not authentication or automatic verification.
    """
    body = {key: value for key, value in manifest.items() if key != "capture_id"}
    if manifest.get("capture_id") != "sha256:" + payload_sha256(body):
        raise ValueError("capture digest mismatch")
    if manifest.get("schema_version") != "torc.harness_capture.v0":
        raise ValueError("unsupported capture schema")
    base = manifest["bindings"]
    stale = base != current_bindings or workspace_evidence.get("base_bindings") != base
    verified = {}
    operation_ids = {op["operation_id"] for op in manifest["tool_operations"]}
    for item in workspace_evidence.get("verified_operations", []):
        if not isinstance(item, dict) or not isinstance(item.get("evidence_ref"), str) \
                or not item["evidence_ref"].strip():
            raise ValueError("independent evidence_ref required")
        operation_id = item.get("operation_id")
        if operation_id not in operation_ids or operation_id in verified:
            raise ValueError("unknown or duplicate evidence operation")
        verified[operation_id] = item["evidence_ref"]
    operations = deepcopy(manifest["tool_operations"])
    holds = []
    for operation in operations:
        operation_id = operation["operation_id"]
        if not stale and operation_id in verified and operation["observation"] != "not_observable":
            operation.update(observation="verified_effect", evidence_ref=verified[operation_id])
        unsafe = (operation["idempotency"] != "idempotent"
                  or operation["target"]["type"] == "unknown")
        if unsafe and operation["observation"] != "verified_effect":
            holds.append(operation_id)
    scope_holds = []
    if manifest["coverage"]["status"] != "complete":
        scope_holds.append("coverage_incomplete")
    if stale:
        scope_holds.append("bindings_stale")
    status = "stale" if stale else "held" if holds or scope_holds else "observations_complete"
    return {
        "schema_version": "torc.harness_reconciliation.v0",
        "capture_id": manifest["capture_id"], "base_bindings": deepcopy(base),
        "coverage": deepcopy(manifest["coverage"]), "quiescence": "unknown",
        "status": status, "hold_list": holds, "scope_holds": scope_holds,
        "operations": operations, "retry_authorized": False,
        "next_action": ("Gather fresh bound evidence; inspect uncertain effects before any retry."
                        if status != "observations_complete" else
                        "Observations complete for the fixture only; use normal assignment and "
                        "authority checks. This report grants no tool or retry permission."),
    }

"""Faithful, read-only composition of a stored P5 carry into a v1 claim capsule.

The expected ID and record hash must come from the carry's caller. Neither
freshness nor writer authentication follows from a matching hash. This module
renders selected content; it never selects more content or transfers authority.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .canonical import payload_sha256, record_hash_is_valid
from .errors import InvalidInputError
from .execution_capsules import capsule_binding_is_valid, compile_claim_capsule
from .store import Store
from .verify import verify_store

COMPOSITION_FORMAT = "torc-p5-capsule-composition-v1"
CLAIM_PREFIXES = {
    "constraints": "x",
    "commitments": "c",
    "open-work": "w",
    "goals": "g",
    "settled-decisions": "d",
    "uncertainties": "u",
    "methods": "m",
    "artifact-refs": "a",
    "memory-refs": "r",
}


class CapsuleCompositionError(InvalidInputError):
    """A stored projection or supplied composition failed a named contract gate."""

    def __init__(self, code: str, detail: str = "", *, errors: list | None = None):
        self.code = code
        self.errors = errors or []
        super().__init__(f"{code}: {detail}" if detail else code)


def derive(
    store: Store,
    projection_id: str,
    record_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return a capsule, v1 control and off-model composition record in one snapshot."""
    with store.read_transaction():
        projection = _lookup(store, projection_id, record_sha256)
        result = _render(projection)
        _verify_render(projection, *result)
        return result


def verify(
    store: Store,
    projection_id: str,
    record_sha256: str,
    capsule: dict[str, Any],
    control: dict[str, Any],
    record: dict[str, Any],
) -> None:
    """Reject unless all three objects equal the rendering of the expected carry."""
    with store.read_transaction():
        projection = _lookup(store, projection_id, record_sha256)
        _verify_render(projection, capsule, control, record)


def _lookup(store: Store, projection_id: str, record_sha256: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT * FROM projections WHERE projection_id = ?",
        (projection_id,),
    ).fetchone()
    if row is None:
        raise CapsuleCompositionError("projection_unknown")
    try:
        projection = json.loads(row["payload_json"])
    except (ValueError, TypeError) as exc:
        raise CapsuleCompositionError("projection_hash_invalid") from exc
    if not isinstance(projection, dict) or any(
        row[key] != projection.get(key)
        for key in ("projection_id", "lineage_id", "source_revision_id", "target_substrate_id")
    ):
        raise CapsuleCompositionError("projection_row_mismatch")
    if not isinstance(projection.get("integrity"), dict) or not record_hash_is_valid(projection):
        raise CapsuleCompositionError("projection_hash_invalid")
    if projection["integrity"]["canonical_payload_sha256"] != record_sha256:
        raise CapsuleCompositionError("projection_hash_unexpected")
    versions = (projection.get("compiler_version"), projection.get("policy_version"))
    if versions not in (("p5-1", "p5-1"), ("p5-2", "p5-2")):
        raise CapsuleCompositionError("projection_compiler_unsupported")
    verification = verify_store(store, projection["lineage_id"])
    if not verification["valid"]:
        raise CapsuleCompositionError(
            "lineage_integrity_invalid",
            errors=verification["errors"],
        )
    return projection


def _letters(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(97 + remainder) + result
    return result


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise CapsuleCompositionError(code)
    return value


def _render(projection: dict[str, Any]) -> tuple[dict, dict, dict]:
    """Render the fixed section classification; preserve all remaining content."""
    sections: list[dict[str, Any]] = []
    paths: dict[str, dict[str, str]] = {}
    recorded: dict[str, Any] = {}
    inventory: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    history_index = 0
    seen: set[str] = set()

    def add(section, section_id, prefix, values, field_paths):
        if not isinstance(values, list):
            raise CapsuleCompositionError("claim_section_invalid", section_id)
        for value in values:
            _text(value, "claim_item_invalid")
        if not values:
            return
        sections.append(
            {
                "section_id": section_id,
                "claim_prefix": prefix,
                "values": values,
                "source_refs": [section["source_ref"]] * len(values),
            }
        )
        for index, path in enumerate(field_paths, 1):
            paths[f"{prefix}{index}"] = {
                "projection_section_id": section["section_id"],
                "field_path": path,
            }

    try:
        for section in projection["included_sections"]:
            section_id, content = section["section_id"], section["content"]
            if section_id in seen:
                raise CapsuleCompositionError("section_unclassified", "duplicate section")
            seen.add(section_id)
            before = len(paths)
            if section_id in CLAIM_PREFIXES:
                if not isinstance(content, list):
                    raise CapsuleCompositionError("claim_section_invalid", section_id)
                add(
                    section,
                    section_id,
                    CLAIM_PREFIXES[section_id],
                    content,
                    [f"[{i}]" for i in range(len(content))],
                )
            elif section_id == "identity-role":
                identity = content.get("identity") if isinstance(content, dict) else None
                if not isinstance(identity, dict):
                    raise CapsuleCompositionError("header_missing", "identity.label")
                headers["lineage_identity"] = _text(identity.get("label"), "header_missing")
                headers["current_responsibility"] = _text(content.get("role"), "header_missing")
                remainder = deepcopy(content)
                remainder.pop("role")
                remainder["identity"].pop("label")
                recorded[section_id] = remainder
            elif section_id in {"session-purpose", "handoff-purpose"}:
                if "handoff_reason" in headers or not isinstance(content, dict):
                    raise CapsuleCompositionError("header_missing", "purpose")
                key = "purpose" if section_id == "session-purpose" else "reason_code"
                headers["handoff_reason"] = _text(content.get(key), "header_missing")
                recorded[section_id] = {k: deepcopy(v) for k, v in content.items() if k != key}
            elif section_id in {"receiver-fit", "self-model-provenance"}:
                recorded[section_id] = deepcopy(content)
            elif section_id.startswith("unaccounted-"):
                history_index += 1
                add(section, section_id, "z" + _letters(history_index), [content["item"]], ["item"])
                recorded[section_id] = {k: deepcopy(v) for k, v in content.items() if k != "item"}
            elif section_id == "changes-since-receiver":
                remainder = deepcopy(content)
                for name, items in content["removed"].items():
                    if not isinstance(items, list):
                        raise CapsuleCompositionError("claim_section_invalid", section_id)
                    # Keep item order within each disposition; paths retain original positions.
                    groups: dict[str, list[tuple[int, dict]]] = {}
                    for i, item in enumerate(items):
                        disposition = _text(item["disposition"], "claim_item_invalid")
                        groups.setdefault(disposition, []).append((i, item))
                    for disposition, entries in groups.items():
                        history_index += 1
                        add(
                            section,
                            f"{section_id}.removed.{name}.{disposition}",
                            "z" + _letters(history_index),
                            [item["item"] for _, item in entries],
                            [f"removed.{name}[{i}].item" for i, _ in entries],
                        )
                    remainder["removed"][name] = [
                        {k: v for k, v in item.items() if k not in {"item", "disposition"}}
                        for item in items
                    ]
                recorded[section_id] = remainder
            else:
                raise CapsuleCompositionError("section_unclassified", str(section_id))
            inventory.append({"section_id": section_id, "claim_count": len(paths) - before})
        if set(headers) != {"lineage_identity", "current_responsibility", "handoff_reason"}:
            raise CapsuleCompositionError("header_missing")
        if not paths:
            raise CapsuleCompositionError("claims_empty")
        capsule, control = compile_claim_capsule(
            projection_id=projection["projection_id"],
            source_revision_id=projection["source_revision_id"],
            target_substrate=projection["target_substrate_id"],
            sections=sections,
            **headers,
        )
        count = sum(len(section["values"]) for section in sections)
        if len(control["claim_sources"]) != count:
            raise CapsuleCompositionError("claim_handle_collision")
        record = {
            "schema_version": 1,
            "format": COMPOSITION_FORMAT,
            "projection_id": projection["projection_id"],
            "projection_record_sha256": projection["integrity"]["canonical_payload_sha256"],
            "lineage_id": projection["lineage_id"],
            "source_revision_id": projection["source_revision_id"],
            "target_substrate_id": projection["target_substrate_id"],
            "compiler_version": projection["compiler_version"],
            "policy_version": projection["policy_version"],
            "budget": deepcopy(projection["budget"]),
            "included_sections": inventory,
            "omitted_sections": deepcopy(projection["omitted_sections"]),
            "redactions": deepcopy(projection["redactions"]),
            "recorded_fields": recorded,
            "claim_paths": paths,
            "authority_transferred": False,
            "capsule_sha256": payload_sha256(capsule),
            "control_sha256": payload_sha256(control),
        }
    except (KeyError, TypeError, AttributeError) as exc:
        raise CapsuleCompositionError("projection_shape_invalid") from exc
    return capsule, control, record


def _verify_render(projection, capsule, control, record):
    expected_capsule, expected_control, expected_record = _render(projection)
    if not all(isinstance(value, dict) for value in (capsule, control, record)):
        raise CapsuleCompositionError("composition_unbound")
    if (
        not capsule_binding_is_valid(capsule, control)
        or record.get("projection_id") != projection["projection_id"]
        or record.get("projection_record_sha256") != expected_record["projection_record_sha256"]
        or record.get("capsule_sha256") != payload_sha256(capsule)
        or record.get("control_sha256") != payload_sha256(control)
    ):
        raise CapsuleCompositionError("composition_unbound")
    for actual, expected, keys in (
        (
            capsule,
            expected_capsule,
            ("lineage_identity", "current_responsibility", "handoff_reason", "source_revision_id"),
        ),
        (control, expected_control, ("projection_id", "source_revision_id", "target_substrate")),
    ):
        if any(actual.get(key) != expected[key] for key in keys):
            raise CapsuleCompositionError("header_mismatch")
    claims = capsule.get("claims")
    if not isinstance(claims, dict) or not all(isinstance(v, dict) for v in claims.values()):
        raise CapsuleCompositionError("claim_set_mismatch")
    handles = [key for values in claims.values() for key in values]
    if set(handles) != set(expected_control["claim_sources"]) or len(handles) != len(set(handles)):
        raise CapsuleCompositionError("claim_set_mismatch")
    if claims != expected_capsule["claims"]:
        raise CapsuleCompositionError("claim_text_mismatch")
    if (
        control.get("claim_sources") != expected_control["claim_sources"]
        or record.get("claim_paths") != expected_record["claim_paths"]
    ):
        raise CapsuleCompositionError("claim_source_mismatch")
    hashes = {"capsule_sha256", "control_sha256"}
    if {k: v for k, v in record.items() if k not in hashes} != {
        k: v for k, v in expected_record.items() if k not in hashes
    }:
        raise CapsuleCompositionError("control_evidence_mismatch")
    if any(
        payload_sha256(actual) != payload_sha256(expected)
        for actual, expected in (
            (capsule, expected_capsule),
            (control, expected_control),
            (record, expected_record),
        )
    ):
        raise CapsuleCompositionError("composition_shape_mismatch")

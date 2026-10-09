"""Compact model-facing views derived from canonical continuity state."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from .canonical import payload_sha256

CAPSULE_FORMAT = "torc-claim-capsule-v1"
CONTROL_FORMAT = "torc-claim-control-v1"


def compile_claim_capsule(
    *,
    projection_id: str,
    lineage_identity: str,
    current_responsibility: str,
    source_revision_id: str,
    handoff_reason: str,
    target_substrate: str,
    sections: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a lean execution capsule and its control-side provenance map.

    The capsule contains short claim handles and the text a target needs to do
    work. Full source references remain in the control envelope, where TORC can
    resolve target citations without repeating those references in model input.
    """

    metadata = {
        "projection_id": projection_id,
        "lineage_identity": lineage_identity,
        "current_responsibility": current_responsibility,
        "source_revision_id": source_revision_id,
        "handoff_reason": handoff_reason,
        "target_substrate": target_substrate,
    }
    for name, value in metadata.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"capsule {name} must be a non-empty string")

    claims: dict[str, dict[str, str]] = {}
    claim_sources: dict[str, dict[str, Any]] = {}
    seen_sections: set[str] = set()
    seen_prefixes: set[str] = set()

    for section in sections:
        section_id = _required_text(section, "section_id")
        prefix = _required_text(section, "claim_prefix")
        if section_id in seen_sections:
            raise ValueError(f"duplicate capsule section: {section_id}")
        if prefix in seen_prefixes:
            raise ValueError(f"duplicate claim prefix: {prefix}")
        if not re.fullmatch(r"[a-z][a-z0-9]*", prefix):
            raise ValueError(f"invalid claim prefix: {prefix}")
        seen_sections.add(section_id)
        seen_prefixes.add(prefix)

        values = section.get("values")
        source_refs = section.get("source_refs")
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item for item in values
        ):
            raise ValueError(f"capsule section values must be non-empty strings: {section_id}")
        if not isinstance(source_refs, list) or not all(
            isinstance(item, str) and item for item in source_refs
        ):
            raise ValueError(
                f"capsule section source refs must be non-empty strings: {section_id}"
            )
        if len(values) != len(source_refs):
            raise ValueError(f"capsule section value/source count differs: {section_id}")

        section_claims: dict[str, str] = {}
        for index, (value, source_ref) in enumerate(
            zip(values, source_refs, strict=True), start=1
        ):
            claim_id = f"{prefix}{index}"
            if claim_id in claim_sources:
                # Prefixes such as "c" and "c1" both generate "c11"; a silent
                # overwrite would misattribute a source reference.
                raise ValueError(f"claim id collision: {claim_id}")
            section_claims[claim_id] = value
            claim_sources[claim_id] = {
                "section_id": section_id,
                "position": index - 1,
                "source_ref": source_ref,
            }
        claims[section_id] = section_claims

    if not claim_sources:
        raise ValueError("capsule must contain at least one claim")

    capsule = {
        "schema_version": 1,
        "format": CAPSULE_FORMAT,
        "lineage_identity": lineage_identity,
        "current_responsibility": current_responsibility,
        "source_revision_id": source_revision_id,
        "handoff_reason": handoff_reason,
        "claims": claims,
    }
    control = {
        "schema_version": 1,
        "format": CONTROL_FORMAT,
        "projection_id": projection_id,
        "source_revision_id": source_revision_id,
        "target_substrate": target_substrate,
        "capsule_sha256": payload_sha256(capsule),
        "claim_sources": claim_sources,
    }
    return capsule, control


def capsule_binding_is_valid(capsule: dict[str, Any], control: dict[str, Any]) -> bool:
    """Return whether a control envelope is bound to the supplied capsule."""

    return (
        capsule.get("format") == CAPSULE_FORMAT
        and control.get("format") == CONTROL_FORMAT
        and control.get("source_revision_id") == capsule.get("source_revision_id")
        and control.get("capsule_sha256") == payload_sha256(capsule)
    )


def resolve_claim_sources(
    control: dict[str, Any], claim_ids: Sequence[str]
) -> dict[str, str]:
    """Resolve target-supplied claim handles or fail on an unknown handle."""

    known = control.get("claim_sources")
    if not isinstance(known, dict):
        raise ValueError("control envelope has no claim source map")
    resolved: dict[str, str] = {}
    for claim_id in claim_ids:
        entry = known.get(claim_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("source_ref"), str):
            raise ValueError(f"unknown claim id: {claim_id}")
        resolved[claim_id] = entry["source_ref"]
    return resolved


def _required_text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"capsule section {key} must be a non-empty string")
    return result

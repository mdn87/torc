from __future__ import annotations

import json
from pathlib import Path

import pytest

from torc.canonical import canonical_json, payload_sha256
from torc.execution_capsules import (
    capsule_binding_is_valid,
    compile_claim_capsule,
    resolve_claim_sources,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "sol-continuity-001"

SECTION_PREFIXES = {
    "settled_decisions": "d",
    "active_commitments": "c",
    "hard_constraints": "x",
    "unresolved_work": "w",
    "uncertainties": "u",
    "superseded_directions": "s",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_capsule() -> tuple[dict, dict]:
    source = _read(EXPERIMENT / "payloads" / "compiled-handoff-v2.json")
    continuity = source["continuity"]
    sections = [
        {
            "section_id": section_id,
            "claim_prefix": prefix,
            "values": continuity[section_id],
            "source_refs": source["source_refs"][section_id],
        }
        for section_id, prefix in SECTION_PREFIXES.items()
    ]
    return compile_claim_capsule(
        projection_id="sol-pilot-projection-0002",
        lineage_identity=continuity["lineage_identity"],
        current_responsibility=continuity["current_responsibility"],
        source_revision_id=continuity["source_revision_id"],
        handoff_reason=continuity["handoff_reason"],
        target_substrate="gpt-6-sol-independent-review",
        sections=sections,
    )


def test_claim_capsule_separates_model_input_from_control_metadata() -> None:
    capsule, control = _fixture_capsule()

    rendered = canonical_json(capsule)
    assert "source_ref" not in rendered
    assert "source_activation" not in rendered
    assert "projection_id" not in rendered
    assert control["capsule_sha256"] == payload_sha256(capsule)
    assert capsule_binding_is_valid(capsule, control) is True
    assert resolve_claim_sources(control, ["d1", "c2", "x1"]) == {
        "d1": "ADR-014",
        "c2": "POLICY-RET-7Y",
        "x1": "canonical-state.json#hard_constraints/0",
    }

    tampered = dict(capsule)
    tampered["current_responsibility"] = "Perform a different task"
    assert capsule_binding_is_valid(tampered, control) is False


def test_claim_capsule_is_smaller_than_both_calibration_payloads() -> None:
    capsule, _ = _fixture_capsule()
    compiled = _read(EXPERIMENT / "payloads" / "compiled-handoff-v2.json")
    torc = _read(EXPERIMENT / "payloads" / "torc-projection.json")

    capsule_bytes = len(canonical_json(capsule).encode("utf-8"))
    compiled_bytes = len(canonical_json(compiled).encode("utf-8"))
    torc_bytes = len(canonical_json(torc).encode("utf-8"))

    assert capsule_bytes == 2243
    assert capsule_bytes < compiled_bytes
    assert capsule_bytes < torc_bytes


def test_claim_capsule_rejects_ambiguous_or_unknown_claims() -> None:
    section = {
        "section_id": "commitments",
        "claim_prefix": "c",
        "values": ["Preserve evidence"],
        "source_refs": [],
    }
    with pytest.raises(ValueError, match="value/source count differs"):
        compile_claim_capsule(
            projection_id="projection-1",
            lineage_identity="lineage-1",
            current_responsibility="Review",
            source_revision_id="revision-1",
            handoff_reason="independent_challenge",
            target_substrate="claude-review",
            sections=[section],
        )

    _, control = _fixture_capsule()
    with pytest.raises(ValueError, match="unknown claim id"):
        resolve_claim_sources(control, ["missing1"])

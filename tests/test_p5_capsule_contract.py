"""Contract between the P5 receiver-fitted carry and the claim capsule (ADR 0004 and 0005).

The projection compiler sizes the carry for the receiver first. A capsule is a
model-facing rendering of that already-fitted carry: every claim resolves to a
source reference the projection recorded, and nothing the projection omitted for
budget can reappear in the capsule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from torc.execution_capsules import (
    capsule_binding_is_valid,
    compile_claim_capsule,
    resolve_claim_sources,
)
from torc.operator import (
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
)
from torc.store import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "p5-dropped-work"
LINEAGE = "p5-dropped-work"
ACTIVATION = "activation-implementer"

# Projection sections whose list content a capsule may carry as claims.
CLAIM_SECTIONS = {
    "constraints": "x",
    "commitments": "c",
    "open-work": "w",
    "settled-decisions": "d",
    "uncertainties": "u",
}


def _load(name: str) -> Any:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def _build(store: Store) -> None:
    create_operator_lineage(
        store,
        lineage_id=LINEAGE,
        canonical_state=_load("state-1-created.json"),
        substrate=_load("source-substrate.json"),
        activation_id=ACTIVATION,
    )
    for name, resolutions in (
        ("state-2-work-added.json", None),
        ("state-3-item-completed.json", _load("resolutions-3.json")),
        ("state-4-last-summary.json", None),
    ):
        checkpoint_operator_lineage(
            store,
            lineage_id=LINEAGE,
            activation_id=ACTIVATION,
            canonical_state=_load(name),
            resolutions=resolutions,
        )


def _capsule_from(projection: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Render a capsule from the sections the projection included, and nothing else."""

    sections = []
    for item in projection["included_sections"]:
        prefix = CLAIM_SECTIONS.get(item["section_id"])
        if prefix is None or not item["content"]:
            continue
        sections.append(
            {
                "section_id": item["section_id"],
                "claim_prefix": prefix,
                "values": list(item["content"]),
                "source_refs": [item["source_ref"]] * len(item["content"]),
            }
        )
    identity = next(
        item["content"]
        for item in projection["included_sections"]
        if item["section_id"] == "identity-role"
    )
    return compile_claim_capsule(
        projection_id=projection["projection_id"],
        lineage_identity=identity["identity"]["label"],
        current_responsibility=identity["role"],
        source_revision_id=projection["source_revision_id"],
        handoff_reason="independent_challenge",
        target_substrate=projection["target_substrate_id"],
        sections=sections,
    )


def test_capsule_is_rendered_from_the_fitted_carry_and_cannot_outgrow_it(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        _build(store)
        small = carry_operator_lineage(
            store, lineage_id=LINEAGE, substrate=_load("receiver-small.json")
        )["projection"]
        large = carry_operator_lineage(
            store, lineage_id=LINEAGE, substrate=_load("receiver-large.json")
        )["projection"]

    small_capsule, small_control = _capsule_from(small)
    large_capsule, large_control = _capsule_from(large)
    omitted_small = {item["section_id"] for item in small["omitted_sections"]}
    included_small = {item["section_id"] for item in small["included_sections"]}

    # Sizing happened in the projection: the small receiver lost its uncertainties
    # to budget, so its capsule has no claims for them, while the large receiver's
    # capsule does.
    assert "uncertainties" in omitted_small
    assert "uncertainties" not in small_capsule["claims"]
    assert "uncertainties" in large_capsule["claims"]
    assert set(small_capsule["claims"]) <= included_small

    # Every claim handle resolves to a source reference the projection recorded,
    # so a target citation can still be checked against canonical history.
    for control, projection in ((small_control, small), (large_control, large)):
        recorded = {item["source_ref"] for item in projection["included_sections"]}
        resolved = resolve_claim_sources(control, list(control["claim_sources"]))
        assert resolved
        assert set(resolved.values()) <= recorded
        assert control["projection_id"] == projection["projection_id"]
    assert capsule_binding_is_valid(small_capsule, small_control)
    assert capsule_binding_is_valid(large_capsule, large_control)

    # The capsule is a rendering, not a second compiler: it carries no history
    # bookkeeping of its own, and the omission ledger stays with the projection.
    assert "omitted_sections" not in small_capsule
    assert "receiver-fit" not in small_capsule["claims"]

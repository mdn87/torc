"""Reproduce the round-2 attack findings against version 2 of the assessment.

R2-01: a checkpoint labeled rollback_applied through the Python API poisons the lineage.
R2-02: the handoff reconstruction template delivers optional head state the projection omitted.

Run from the torc checkout: PYTHONPATH=src python3 <this file> <scratch-state-root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import ACTIVATION, LINEAGE, build_quiet, head_state, load  # noqa: E402

from torc.errors import TorcError  # noqa: E402
from torc.operator import (  # noqa: E402
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    prepare_operator_handoff,
)
from torc.store import Store  # noqa: E402
from torc.verify import verify_store  # noqa: E402


def main(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    print("== R2-01: after a mislabeled rollback_applied checkpoint, later operations are refused ==")
    with Store(root / "r201") as store:
        build_quiet(store)
        s = head_state(store)
        s["open_work"] = []
        checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id=ACTIVATION, canonical_state=s,
            event_type="rollback_applied",
        )
        verification = verify_store(store, LINEAGE)
        print("  verify:", verification["valid"], [e["code"] for e in verification["errors"]])
        attempts = (
            ("ordinary checkpoint", lambda: checkpoint_operator_lineage(
                store, lineage_id=LINEAGE, activation_id=ACTIVATION, canonical_state=head_state(store))),
            ("carry", lambda: carry_operator_lineage(
                store, lineage_id=LINEAGE, substrate=load("receiver-large.json"))),
        )
        for label, attempt in attempts:
            try:
                attempt()
                print(f"  {label}: succeeded (unexpected)")
            except TorcError as error:
                print(f"  {label}: refused -> {type(error).__name__}: {str(error)[:80]}")

    print("\n== R2-02: the reconstruction template carries optional content the projection omitted ==")
    with Store(root / "r202") as store:
        state = load("state-1-created.json")
        state["self_model"]["settled_decisions"] = [
            f"Settled decision number {i} about the export format and its versioning rules"
            for i in range(60)
        ]
        create_operator_lineage(
            store, lineage_id=LINEAGE, canonical_state=state,
            substrate=load("source-substrate.json"), activation_id=ACTIVATION,
        )
        target = load("receiver-large.json") | {
            "context_budget": {"unit": "words", "limit": 4000, "carry_limit": 120}
        }
        plan = {
            "target_substrate": target,
            "target_activation_id": "activation-successor",
            "task_phase": "implementation",
            "requirements": {
                "capabilities": ["repository_read", "repository_write"],
                "policy_labels": ["local-workspace"],
                "minimum_context_units": 1000,
            },
            "target_responsibility": "Finish the lineage export command",
            "reason_code": "model_succession",
            "rationale": "oversized optional head state",
        }
        prepared = prepare_operator_handoff(
            store, lineage_id=LINEAGE, source_activation_id=ACTIVATION, plan=plan
        )
        projection = store.get_hashed_record("projections", "projection_id", prepared["projection_id"])
        omitted = {o["section_id"]: o["reason"] for o in projection["omitted_sections"]}
        template = json.loads((store.state_dir / prepared["reconstruction_template_path"]).read_text())
        brief = (store.state_dir / prepared["brief_path"]).read_text()
        print("  projection budget:", projection["budget"], "| omitted:", omitted)
        print("  template settled_decisions:", len(template.get("settled_decisions", [])))
        print("  brief lists settled_decisions as a continuity requirement:", "settled_decisions" in brief)
        print("  brief tells the recipient to copy the template:", "copy" in brief.lower())
        print("  template bytes:", len(json.dumps(template).encode()), "| brief bytes:", len(brief.encode()))


if __name__ == "__main__":
    main(Path(sys.argv[1]))

"""Reproduce three Codex cross-review findings against the P5 carry (CR-001, CR-002, CR-003).

Run from the torc checkout: PYTHONPATH=src python3 <this file> <scratch-state-root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import LINEAGE, build_quiet, do_handoff, handoff_plan, head_state, load  # noqa: E402

from torc.history import revision_chain, unaccounted_drops  # noqa: E402
from torc.operator import carry_operator_lineage, checkpoint_operator_lineage  # noqa: E402
from torc.store import Store  # noqa: E402
from torc.verify import verify_store  # noqa: E402

DROPPED_WORK = "Handle exports larger than memory"


def main(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    print("== CR-001: successor adds an item and completes it before the implementer returns ==")
    with Store(root / "cr001") as store:
        build_quiet(store)
        do_handoff(store, "activation-implementer", handoff_plan())
        s = head_state(store)
        s["open_work"] = s["open_work"] + ["Transient task"]
        checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-successor", canonical_state=s
        )
        s = head_state(store)
        s["open_work"] = [i for i in s["open_work"] if i != "Transient task"]
        checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-successor", canonical_state=s,
            resolutions=[{"section": "open_work", "item": "Transient task", "disposition": "completed"}],
        )
        carry = carry_operator_lineage(
            store, lineage_id=LINEAGE, substrate=load("source-substrate.json")
        )["projection"]
        sections = {x["section_id"]: x for x in carry["included_sections"]}
        content = sections.get("changes-since-receiver", {}).get("content")
        print("  changes-since-receiver:", content)
        print("  -> transient add+complete visible to the returning bearer:", "Transient task" in json.dumps(content))

    print("\n== CR-003: directly appended, correctly sealed revision with a fabricated resolution ==")
    with Store(root / "cr003") as store:
        build_quiet(store)
        s = head_state(store)
        rev = store.append_revision(
            LINEAGE, s, event_type="checkpoint", activation_id="activation-implementer",
            resolutions=[{"section": "open_work", "item": DROPPED_WORK, "disposition": "completed", "note": "fabricated"}],
        )
        v = verify_store(store, LINEAGE)
        drops = unaccounted_drops(revision_chain(store, rev["revision_id"]))
        print("  verify valid:", v["valid"], "errors:", v["errors"])
        print("  unaccounted after the fabricated 'completed' resolution:", [(d["section"], d["item"]) for d in drops])
        print("  -> fabricated resolution silenced the real drop:", not any(d["item"] == DROPPED_WORK for d in drops))
        rev2 = store.append_revision(
            LINEAGE, s, event_type="checkpoint", activation_id="activation-implementer",
            resolutions=[{"bogus": True}],
        )
        try:
            unaccounted_drops(revision_chain(store, rev2["revision_id"]))
            print("  malformed resolution: history read succeeded (unexpected)")
        except Exception as error:  # noqa: BLE001
            print("  malformed resolution accepted by the store; history read raises:", type(error).__name__, error)

    print("\n== CR-002: the Python API accepts event_type='rollback_applied' on a plain checkpoint ==")
    with Store(root / "cr002") as store:
        build_quiet(store)
        s = head_state(store)
        s["open_work"] = []
        r = checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-implementer", canonical_state=s,
            event_type="rollback_applied",
        )
        print("  accepted; boundary.unaccounted:", [(d["section"], d["item"]) for d in r["boundary"]["unaccounted"]])
        print("  (the removal made by this mislabeled revision is exempted; earlier drops still show)")
        v = verify_store(store, LINEAGE)
        print("  verify afterwards valid:", v["valid"], [e["code"] for e in v["errors"]])


if __name__ == "__main__":
    main(Path(sys.argv[1]))

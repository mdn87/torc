"""Budget derivation and the item-level fitting loop, including the characters unit."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import sections, show, state, substrate  # noqa: E402
from torc.errors import ProjectionBudgetError  # noqa: E402
from torc.operator import carry_operator_lineage, create_operator_lineage  # noqa: E402
from torc.projections import estimate_units, receiver_budget  # noqa: E402
from torc.store import Store  # noqa: E402

print("budget derivations:")
for ctx in (
    {"unit": "words", "limit": 4000},        # share 200 == floor
    {"unit": "words", "limit": 3999},        # share 199 -> floor 200
    {"unit": "words", "limit": 120},         # floor exceeds limit -> 120
    {"unit": "characters", "limit": 9000},   # share 450 -> floor 1200
    {"unit": "characters", "limit": 1000},   # floor exceeds limit -> 1000
    {"unit": "characters", "limit": 100000}, # share 5000
):
    print("  ", ctx, "->", receiver_budget({"context_budget": ctx}))
print("  cap above derived:", receiver_budget({"context_budget": {"unit": "words", "limit": 4000}}, 999))
print("  cap below declared carry_limit:", receiver_budget({"context_budget": {"limit": 4000, "carry_limit": 100}}, 50))
print("  empty list costs (words, characters):", estimate_units([], "words"), estimate_units([], "characters"))
print()

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    goals = [f"goal number {i} with several words in it" for i in range(12)]
    create_operator_lineage(
        store, lineage_id="lin",
        canonical_state=state(goals=goals, uncertainties=["u1", "u2"], open_work=["w1"]),
        substrate=substrate("s1"), activation_id="a1",
    )
    for unit, limit in (("words", 150), ("characters", 1250)):
        reader = substrate(f"reader-{unit}", unit=unit, limit=100000, carry_limit=limit)
        try:
            carry = carry_operator_lineage(store, lineage_id="lin", substrate=reader)["projection"]
        except ProjectionBudgetError as exc:
            print(unit, "->", exc)
            continue
        got = sections(carry)
        total = sum(s["estimated_units"] for s in carry["included_sections"])
        print(f"{unit}: limit={carry['budget']['limit']} used={carry['budget']['estimated_used']} "
              f"sum(sections)={total} within={carry['budget']['estimated_used'] <= carry['budget']['limit']}")
        print("   goals kept:", len(got["goals"]["content"]) if "goals" in got else None, "of", len(goals))
        print("   omitted:", {o["section_id"]: o["reason"] for o in carry["omitted_sections"]})
        # Check: is the kept prefix maximal (would one more item have fit)?
        if "goals" in got and len(got["goals"]["content"]) < len(goals):
            kept = got["goals"]["content"]
            used_before = carry["budget"]["estimated_used"] - got["goals"]["estimated_units"]
            one_more = used_before + estimate_units(kept + [goals[len(kept)]], unit)
            print("   one more goal would need", one_more, "> limit?", one_more > carry["budget"]["limit"])
        show("   receiver-fit", got["receiver-fit"]["content"])

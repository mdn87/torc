"""Item-level fitting under tight words and characters budgets."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import sections, state, substrate  # noqa: E402
from torc.errors import ProjectionBudgetError  # noqa: E402
from torc.operator import carry_operator_lineage, create_operator_lineage  # noqa: E402
from torc.projections import estimate_units  # noqa: E402
from torc.store import Store  # noqa: E402

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    goals = [f"goal number {i} with several words in it" for i in range(12)]
    sm = {"role": "Implement", "methods": ["alpha beta", "gamma delta"], "settled_decisions": ["one", "two", "three"]}
    create_operator_lineage(
        store, lineage_id="lin",
        canonical_state=state(goals=goals, uncertainties=["u1", "u2"], open_work=["w1"], self_model=sm),
        substrate=substrate("s1"), activation_id="a1",
    )
    for unit, limits in (("words", (60, 70, 80, 95)), ("characters", (700, 800, 900, 1000))):
        for limit in limits:
            reader = substrate(f"r-{unit}-{limit}", unit=unit, limit=100000, carry_limit=limit)
            try:
                carry = carry_operator_lineage(store, lineage_id="lin", substrate=reader)["projection"]
            except ProjectionBudgetError as exc:
                print(f"{unit}@{limit}: {exc}")
                continue
            got = sections(carry)
            used, lim = carry["budget"]["estimated_used"], carry["budget"]["limit"]
            total = sum(s["estimated_units"] for s in carry["included_sections"])
            kept = len(got["goals"]["content"]) if "goals" in got else 0
            omitted = {o["section_id"]: o["reason"] for o in carry["omitted_sections"]}
            line = f"{unit}@{limit}: used={used} sum={total} within={used <= lim} goals_kept={kept}/12 omitted={omitted}"
            if 0 < kept < 12:
                before = used - got["goals"]["estimated_units"]
                one_more = before + estimate_units(got["goals"]["content"] + [goals[kept]], unit)
                line += f" | prefix maximal={one_more > lim}"
            print(line)
            ids = [s["section_id"] for s in carry["included_sections"]]
            assert len(ids) == len(set(ids)), ids

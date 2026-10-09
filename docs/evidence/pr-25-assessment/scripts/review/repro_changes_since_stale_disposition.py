"""changes_since_substrate reports a stale resolution instead of the current removal.

Scenario A: item X is in the receiver's last-authored revision; the next bearer
resolves X as completed, re-adds X, then silently drops X again. The carry's own
unaccounted-* section says X is an unaccounted drop, but changes-since-receiver
says X was "completed".

Scenario B: same, but the final removal is a rollback_applied; the report still
says "completed" instead of "rolled_back".
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import handoff, head_state, sections, show, state, substrate  # noqa: E402
from torc.operator import (  # noqa: E402
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    rollback_operator_lineage,
)
from torc.store import Store  # noqa: E402

LINEAGE = "lin"
X = "Handle exports larger than memory"


def scenario(final: str) -> None:
    with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
        s1, s2 = substrate("s1"), substrate("s2")
        create_operator_lineage(
            store,
            lineage_id=LINEAGE,
            canonical_state=state(open_work=[X, "Y"]),
            substrate=s1,
            activation_id="a1",
        )
        # s1 authors one revision so it has a "last authored" base that holds X.
        base = checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="a1", canonical_state=state(open_work=[X, "Y"])
        )["revision_id"]
        handoff(store, LINEAGE, "a1", s2, "a2")

        def cp(st, **kw):
            return checkpoint_operator_lineage(
                store, lineage_id=LINEAGE, activation_id="a2", canonical_state=st, **kw
            )

        # s2 resolves X as completed, then re-adds it.
        cp(state(open_work=["Y"], self_model=head_state(store, LINEAGE)["self_model"]),
           resolutions=[{"section": "open_work", "item": X, "disposition": "completed"}])
        readded = cp(state(open_work=["Y", X], self_model=head_state(store, LINEAGE)["self_model"]))
        if final == "unaccounted":
            # ... then silently drops it again: an unaccounted drop by the spec's rules.
            last = cp(state(open_work=["Y"], self_model=head_state(store, LINEAGE)["self_model"]))
            show("boundary.unaccounted after the second drop", last["boundary"]["unaccounted"])
        else:
            # ... then an operator rollback to the revision before the re-add removes X.
            target = store.get_revision(readded["revision_id"])["parent_revision_ids"][0]
            rollback_operator_lineage(
                store,
                lineage_id=LINEAGE,
                activation_id="a2",
                expected_head_revision_id=readded["revision_id"],
                target_revision_id=target,
                operator_ref="operator-review",
                rationale="undo the re-add",
                evidence_refs=["evidence-review"],
            )
        carry = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=s1)["projection"]
        got = sections(carry)
        show("changes-since-receiver.removed", got["changes-since-receiver"]["content"]["removed"])
        show("since_revision_id == s1's base", got["changes-since-receiver"]["content"]["since_revision_id"] == base)
        unaccounted = [k for k in got if k.startswith("unaccounted-")]
        show("unaccounted-* sections in the SAME carry", {k: got[k]["content"]["item"] for k in unaccounted})
        expected = "unaccounted" if final == "unaccounted" else "rolled_back"
        actual = got["changes-since-receiver"]["content"]["removed"]["open_work"][0]["disposition"]
        print(f"EXPECTED disposition for {X!r}: {expected!r}; ACTUAL: {actual!r}")
        print()


if __name__ == "__main__":
    print("=== Scenario A: resolved -> re-added -> dropped without resolution")
    scenario("unaccounted")
    print("=== Scenario B: resolved -> re-added -> removed by rollback")
    scenario("rollback")

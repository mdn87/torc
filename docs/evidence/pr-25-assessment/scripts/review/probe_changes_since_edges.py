"""changes-since-receiver edges: a bearer that never authored, and the acceptance role copy."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import handoff, head_state, sections, show, state, substrate  # noqa: E402
from torc.operator import carry_operator_lineage, checkpoint_operator_lineage, create_operator_lineage  # noqa: E402
from torc.store import Store  # noqa: E402

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1, s2 = substrate("s1"), substrate("s2")
    create_operator_lineage(store, lineage_id="lin", canonical_state=state(open_work=["X"]), substrate=s1, activation_id="a1")
    # E1: s1 bore the lineage from creation but never checkpointed; s2 takes over and drops X.
    handoff(store, "lin", "a1", s2, "a2", responsibility="Finish")
    checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a2",
                                canonical_state=state(self_model=head_state(store, "lin")["self_model"]))
    carry = carry_operator_lineage(store, lineage_id="lin", substrate=s1)["projection"]
    show("E1 carry for s1 (bore but never authored): changes-since-receiver present?",
         "changes-since-receiver" in sections(carry))
    show("E1 unaccounted sections", [k for k in sections(carry) if k.startswith("unaccounted-")])

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1, s2 = substrate("s1"), substrate("s2")
    create_operator_lineage(store, lineage_id="lin", canonical_state=state(), substrate=s1, activation_id="a1")
    checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a1", canonical_state=state())
    # E2: handoff changes only the role (TORC bookkeeping); s2 does nothing else.
    handoff(store, "lin", "a1", s2, "a2", responsibility="A different responsibility")
    carry = carry_operator_lineage(store, lineage_id="lin", substrate=s1)["projection"]
    show("E2 changes-since-receiver after a role-copy-only acceptance",
         sections(carry)["changes-since-receiver"]["content"])

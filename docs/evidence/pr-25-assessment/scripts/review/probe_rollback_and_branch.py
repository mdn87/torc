"""Probes that turned out to match the spec's letter (recorded so they are not re-run).

P1. Rollback to a revision that itself silently dropped X silences the ask:
    rev1 {X} -> rev2 {} (unaccounted) -> rev3 {X} (restored) -> rev4 rollback->rev2.
    Head state equals rev2's, but boundary.unaccounted is [] (path dependent).
P2. Branch root is attributed to the source activation's substrate, so the child
    bearer is asked to restate an operator-authored self-model.
P3. The branch source substrate counts as having "authored" the child root.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import sections, show, state, substrate  # noqa: E402
from torc.operator import (  # noqa: E402
    branch_operator_lineage,
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
    rollback_operator_lineage,
)
from torc.store import Store  # noqa: E402

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1 = substrate("s1")
    created = create_operator_lineage(
        store, lineage_id="lin", canonical_state=state(open_work=["X"]), substrate=s1, activation_id="a1"
    )

    def cp(st):
        return checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a1", canonical_state=st)

    r2 = cp(state(open_work=[]))
    show("P1 ask after the silent drop", r2["boundary"]["unaccounted"])
    r3 = cp(state(open_work=["X"]))
    rollback_operator_lineage(
        store, lineage_id="lin", activation_id="a1", expected_head_revision_id=r3["revision_id"],
        target_revision_id=r2["revision_id"], operator_ref="operator-review", rationale="undo",
        evidence_refs=["evidence-review"],
    )
    status = operator_lineage_status(store, "lin")
    show("P1 head open_work after rollback to rev2", status["open_work"])
    show("P1 ask after rollback to the dropping revision", status["boundary"]["unaccounted"])

    # P2/P3: branch from the (operator-authored) root state.
    s2 = substrate("s2")
    branch_operator_lineage(
        store, source_lineage_id="lin", source_activation_id="a1",
        expected_source_revision_id=store.get_lineage("lin")["head_revision_id"],
        child_lineage_id="child", child_activation_id="a-child", child_substrate=s2,
        operator_ref="operator-review", target_assignment_ref="assignment-review",
        rationale="branch", evidence_refs=["evidence-branch"],
    )
    child = operator_lineage_status(store, "child")
    show("P2 child boundary.self_model", child["boundary"]["self_model"])
    carry = carry_operator_lineage(store, lineage_id="child", substrate=s1)["projection"]
    show("P3 carry for the source substrate on the child: changes-since-receiver present?",
         "changes-since-receiver" in sections(carry))
    show("P3 receiver-fit.history_revisions_read", sections(carry)["receiver-fit"]["content"]["history_revisions_read"])

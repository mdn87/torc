"""Self-model provenance across handoff_accepted / rollback_applied, and the observer flag."""

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
    operator_lineage_status,
    rollback_operator_lineage,
)
from torc.store import Store  # noqa: E402

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1, s2, observer = substrate("s1"), substrate("s2"), substrate("observer")
    create_operator_lineage(store, lineage_id="lin", canonical_state=state(), substrate=s1, activation_id="a1")
    sm = {"role": "Implement", "methods": ["s1"], "settled_decisions": []}
    authored = checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a1",
                                           canonical_state=state(self_model=sm), event_type="self_model_revised")
    handoff(store, "lin", "a1", s2, "a2", responsibility="Finish")  # role becomes "Finish" (bookkeeping)
    show("H1 after acceptance (bearer s2)", operator_lineage_status(store, "lin")["boundary"]["self_model"])
    # s2 checkpoints the inherited state unchanged: still due.
    r = checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a2", canonical_state=head_state(store, "lin"))
    show("H2 s2 checkpoint, unchanged self-model", r["boundary"]["self_model"])
    # s2 restates: author s2.
    restated = head_state(store, "lin")
    restated["self_model"]["methods"] = ["s2"]
    r2 = checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a2", canonical_state=restated,
                                     event_type="self_model_revised")
    show("H3 s2 self_model_revised", r2["boundary"]["self_model"])
    # rollback to the handoff_accepted revision: authorship restored to s1.
    accepted_rev = store.get_revision(r["revision_id"])["parent_revision_ids"][0]
    rollback_operator_lineage(store, lineage_id="lin", activation_id="a2",
                              expected_head_revision_id=r2["revision_id"], target_revision_id=accepted_rev,
                              operator_ref="operator-review", rationale="undo", evidence_refs=["evidence-review"])
    show("H4 after rollback to the accepted revision", operator_lineage_status(store, "lin")["boundary"]["self_model"])
    # observer carry: restatement_due is relative to the receiver, not the bearer.
    carry = carry_operator_lineage(store, lineage_id="lin", substrate=observer)["projection"]
    show("H5 observer carry self-model-provenance", sections(carry)["self-model-provenance"]["content"])
    show("H5 observer carry session-purpose", sections(carry)["session-purpose"]["content"])

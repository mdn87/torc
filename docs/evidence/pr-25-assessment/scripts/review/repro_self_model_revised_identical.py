"""Self-model authorship is keyed on a content diff, not on the self_model_revised event.

1. A new bearer issues event_type=self_model_revised with the self-model it
   received (an explicit affirmation). restatement_due stays True.
2. The same bearer issues a plain `checkpoint` that merely edits `methods`.
   restatement_due flips to False although no self_model_revised event exists.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import handoff, head_state, show, state, substrate  # noqa: E402
from torc.operator import checkpoint_operator_lineage, create_operator_lineage  # noqa: E402
from torc.store import Store  # noqa: E402

LINEAGE = "lin"

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1, s2 = substrate("s1"), substrate("s2")
    create_operator_lineage(
        store, lineage_id=LINEAGE, canonical_state=state(), substrate=s1, activation_id="a1"
    )
    # s1 authors the self-model (operator-authored ones are never "due").
    authored = state(self_model={"role": "Implement", "methods": ["s1 method"], "settled_decisions": []})
    checkpoint_operator_lineage(
        store, lineage_id=LINEAGE, activation_id="a1", canonical_state=authored,
        event_type="self_model_revised",
    )
    handoff(store, LINEAGE, "a1", s2, "a2", responsibility="Implement")  # role copy is a no-op here

    # (1) s2 explicitly restates the self-model verbatim through self_model_revised.
    restated = checkpoint_operator_lineage(
        store, lineage_id=LINEAGE, activation_id="a2",
        canonical_state=head_state(store, LINEAGE), event_type="self_model_revised",
    )
    show("after s2 self_model_revised (identical content) -> boundary.self_model",
         restated["boundary"]["self_model"])
    print("EXPECTED restatement_due: False (spec: 'restates the self-model through a "
          "self_model_revised checkpoint'); ACTUAL:", restated["boundary"]["self_model"]["restatement_due"])
    print()

    # (2) s2 edits one method inside a plain checkpoint.
    edited = head_state(store, LINEAGE)
    edited["self_model"]["methods"] = ["s2 method"]
    plain = checkpoint_operator_lineage(
        store, lineage_id=LINEAGE, activation_id="a2", canonical_state=edited, event_type="checkpoint",
    )
    show("after s2 plain checkpoint that edits methods -> boundary.self_model", plain["boundary"]["self_model"])
    print("Authorship moved to s2 with no self_model_revised event; restatement_due:",
          plain["boundary"]["self_model"]["restatement_due"])

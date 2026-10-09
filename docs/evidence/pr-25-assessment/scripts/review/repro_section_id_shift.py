"""unaccounted-* section ids are positions in the open-drop list, so they shift
when an older drop is resolved. The id `unaccounted-open_work-1` names item A in
one carry and item B in the next, from the same lineage, with no new drops.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import head_state, sections, state, substrate  # noqa: E402
from torc.operator import carry_operator_lineage, checkpoint_operator_lineage, create_operator_lineage  # noqa: E402
from torc.store import Store  # noqa: E402

LINEAGE = "lin"

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1, reader = substrate("s1"), substrate("reader")
    create_operator_lineage(
        store, lineage_id=LINEAGE, canonical_state=state(open_work=["A", "B", "C"]), substrate=s1, activation_id="a1"
    )

    def cp(st, **kw):
        return checkpoint_operator_lineage(store, lineage_id=LINEAGE, activation_id="a1", canonical_state=st, **kw)

    cp(state(open_work=["B", "C"]))  # drops A (unaccounted)
    cp(state(open_work=["C"]))       # drops B (unaccounted)

    def ids():
        carry = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=reader)["projection"]
        return {k: v["content"]["item"] for k, v in sections(carry).items() if k.startswith("unaccounted-")}

    print("carry 1:", ids())
    cp(head_state(store, LINEAGE), resolutions=[{"section": "open_work", "item": "A", "disposition": "withdrawn"}])
    print("carry 2 (after resolving A, no new drops):", ids())
    print("`unaccounted-open_work-1` named A, now names B.")

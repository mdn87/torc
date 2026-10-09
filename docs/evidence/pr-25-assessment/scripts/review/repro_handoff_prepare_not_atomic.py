"""A handoff carry that cannot fit leaves a fit decision and a registered descriptor behind.

Spec (Sizing): "If they cannot, compilation fails with ProjectionBudgetError and
nothing is stored." The carry command is wrapped in one transaction; handoff
prepare is not. The P0 path had the same shape; P5 restates the guarantee in prose.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import plan, state, substrate  # noqa: E402
from torc.errors import ProjectionBudgetError  # noqa: E402
from torc.operator import create_operator_lineage, prepare_operator_handoff  # noqa: E402
from torc.store import Store  # noqa: E402
from torc.verify import verify_store  # noqa: E402

LINEAGE = "lin"

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1 = substrate("s1")
    tiny = substrate("tiny", limit=4000, carry_limit=10)  # required sections cannot fit in 10 words
    create_operator_lineage(
        store, lineage_id=LINEAGE, canonical_state=state(open_work=["x"]), substrate=s1, activation_id="a1"
    )

    def counts():
        return {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("fit_decisions", "projections", "activations", "handoffs", "substrates")
        }

    print("before:", counts())
    try:
        prepare_operator_handoff(store, lineage_id=LINEAGE, source_activation_id="a1", plan=plan(tiny, "a2"))
    except ProjectionBudgetError as exc:
        print("raised:", exc)
    print("after: ", counts())
    print("verify still valid:", verify_store(store, LINEAGE)["valid"])
    print("EXPECTED (spec): fit_decisions unchanged (0), nothing stored; ACTUAL fit_decisions =",
          counts()["fit_decisions"], "and 'tiny' stays registered")

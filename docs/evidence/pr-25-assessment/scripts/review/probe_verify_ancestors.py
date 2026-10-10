"""verify's p5 ancestor allowance: can a p5-1 projection cite a revision it should not?

Forge re-sealed p5-1 projections whose one section cites (a) an ancestor,
(b) a LATER revision of the same lineage, (c) the branch parent's revision from
the child lineage, (d) a p0-1 projection citing an ancestor.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import state, substrate  # noqa: E402
from torc.canonical import seal_record  # noqa: E402
from torc.operator import (  # noqa: E402
    branch_operator_lineage,
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
)
from torc.store import Store  # noqa: E402
from torc.verify import verify_store  # noqa: E402


def forge(store, base, pid, source_rev, ref_rev, compiler="p5-1"):
    record = {k: v for k, v in base.items() if k != "integrity"}
    record = record | {
        "projection_id": pid,
        "source_revision_id": source_rev,
        "compiler_version": compiler,
        "included_sections": [
            dict(base["included_sections"][0], source_ref=f"{ref_rev}:constraints")
        ],
        "omitted_sections": [],
    }
    store.insert_hashed_record("projections", pid, seal_record(record))


with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    s1, reader = substrate("s1"), substrate("reader")
    r1 = create_operator_lineage(
        store, lineage_id="lin", canonical_state=state(), substrate=s1, activation_id="a1"
    )["revision_id"]
    r2 = checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a1", canonical_state=state())["revision_id"]
    r3 = checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a1", canonical_state=state())["revision_id"]
    base = carry_operator_lineage(store, lineage_id="lin", substrate=reader)["projection"]
    branch_operator_lineage(
        store, source_lineage_id="lin", source_activation_id="a1", expected_source_revision_id=r3,
        child_lineage_id="child", child_activation_id="a-child", child_substrate=substrate("s2"),
        operator_ref="operator-review", target_assignment_ref="assignment-review",
        rationale="branch", evidence_refs=["evidence-branch"],
    )
    child_root = store.get_lineage("child")["head_revision_id"]
    child_base = carry_operator_lineage(store, lineage_id="child", substrate=reader)["projection"]

    def errors(lineage):
        return [(e["code"], e["record_id"]) for e in verify_store(store, lineage)["errors"]]

    forge(store, base, "p-ancestor", r2, r1)                     # (a) allowed
    print("(a) p5 cites ancestor         ->", errors("lin"))
    forge(store, base, "p-later", r2, r3)                        # (b) must fail
    print("(b) p5 cites later revision   ->", errors("lin"))
    forge(store, child_base, "p-parent", child_root, r3)         # (c) must fail
    print("(c) p5 on child cites parent  ->", errors("child"))
    forge(store, base, "p-p0", r2, r1, compiler="p0-1")          # (d) must fail
    print("(d) p0 cites ancestor         ->", errors("lin"))

"""Resolution semantics across repeated drop/restore cycles and transaction atomicity."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import head_state, show, state, substrate  # noqa: E402
from torc.errors import InvalidInputError, LeaseConflictError  # noqa: E402
from torc.operator import checkpoint_operator_lineage, create_operator_lineage  # noqa: E402
from torc.store import Store  # noqa: E402

with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
    create_operator_lineage(
        store, lineage_id="lin", canonical_state=state(open_work=["X"]), substrate=substrate("s1"), activation_id="a1"
    )

    def cp(st, **kw):
        return checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a1", canonical_state=st, **kw)

    def asks(r):
        return [(d["section"], d["item"]) for d in r["boundary"]["unaccounted"]]

    print("C1 drop X with resolution:", asks(cp(state(), resolutions=[{"section": "open_work", "item": "X", "disposition": "completed"}])))
    print("C2 re-add X:", asks(cp(state(open_work=["X"]))))
    print("C3 drop X again silently (new ask expected):", asks(cp(state())))
    print("C4 resolve the open drop later, no state change:", asks(cp(head_state(store, "lin"), resolutions=[{"section": "open_work", "item": "X", "disposition": "withdrawn"}])))
    print("C5 re-add and drop again silently:", asks(cp(state(open_work=["X"]))), asks(cp(state())))
    try:
        cp(head_state(store, "lin"), resolutions=[{"section": "open_work", "item": "X", "disposition": "completed"},
                                                  {"section": "constraints", "item": "X", "disposition": "completed"}])
    except InvalidInputError as exc:
        print("C6 resolution for a section that never held X ->", exc)

    # Atomicity: a resolution that fails validation after a valid one must leave no revision.
    head_before = store.get_lineage("lin")["head_revision_id"]
    count_before = store.connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
    try:
        cp(state(open_work=["new"]), resolutions=[{"section": "open_work", "item": "X", "disposition": "completed"},
                                                  {"section": "open_work", "item": "nope", "disposition": "completed"}])
    except InvalidInputError as exc:
        print("A1 rejected:", exc)
    print("A1 head unchanged:", store.get_lineage("lin")["head_revision_id"] == head_before,
          "revision count unchanged:", store.connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == count_before,
          "connection idle:", not store.connection.in_transaction)
    # Atomicity: wrong activation with valid resolutions -> no write, connection idle.
    try:
        checkpoint_operator_lineage(store, lineage_id="lin", activation_id="a-nobody", canonical_state=state(),
                                    resolutions=[{"section": "open_work", "item": "X", "disposition": "completed"}])
    except (LeaseConflictError, Exception) as exc:
        print("A2 rejected:", type(exc).__name__, exc)
    print("A2 head unchanged:", store.get_lineage("lin")["head_revision_id"] == head_before,
          "connection idle:", not store.connection.in_transaction)
    show("final head record resolutions", store.get_revision(head_before).get("resolutions"))

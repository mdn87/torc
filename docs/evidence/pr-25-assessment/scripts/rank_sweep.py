"""Sweep the small receiver's carry_limit and report which sections survive.

Run from the torc checkout: PYTHONPATH=src python3 <this file> <scratch-state-root>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import LINEAGE, build_quiet, load  # noqa: E402

from torc.operator import carry_operator_lineage  # noqa: E402
from torc.store import Store  # noqa: E402


def main(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for limit in (55, 68, 69, 70, 83, 84, 100):
        desc = load("receiver-small.json") | {"substrate_id": f"rank-{limit}"}
        desc["context_budget"]["carry_limit"] = limit
        with Store(root / str(limit)) as store:
            build_quiet(store)
            p = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=desc)["projection"]
        included = [s["section_id"] for s in p["included_sections"] if not s["required"]]
        omitted = [f"{o['section_id']}:{o['reason']}" for o in p["omitted_sections"]]
        print(f"carry_limit={limit:>3}: used {p['budget']['estimated_used']:>3}; optional included={included}; omitted={omitted}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

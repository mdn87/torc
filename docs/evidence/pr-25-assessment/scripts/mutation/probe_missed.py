from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # sibling scripts
sys.path.insert(0, str(HERE))
import run_mutations as rm  # noqa: E402  (driver has a __main__ guard)

# Bundle edit: pristine/ and the work-probe-* copies live in $MUTATION_SCRATCH (see run_mutations.py).
BASE = rm.BASE
EX = BASE / "pristine" / "examples"
MISSED = ["H5", "H6", "H10", "P5", "P9", "V1", "V2"]


def run(tree: Path) -> dict:
    p = subprocess.run([sys.executable, "-I", str(HERE / "probe_scenarios.py"), str(tree), str(EX)],
                       capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise SystemExit(f"probe failed for {tree}: {p.stderr[-800:]}")
    return json.loads(p.stdout)


base = run(BASE / "pristine")
table = {m[0]: m for m in rm.M}
for mid in MISSED:
    _, fname, desc, old, new = table[mid]
    tree = BASE / f"work-probe-{mid}"
    if tree.exists():
        shutil.rmtree(tree)
    try:
        shutil.copytree(BASE / "pristine" / "src", tree / "src",
                        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
        f = tree / "src" / "torc" / fname
        text = f.read_text(encoding="utf-8")
        assert text.count(old) == 1
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        got = run(tree)
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    diffs = {k: (base[k], got[k]) for k in base if base[k] != got[k]}
    print(f"=== {mid} ({desc}) -> {'BEHAVIOUR DIFFERS' if diffs else 'no observable difference in any probe'}")
    for k, (a, b) in diffs.items():
        print(f"  {k}\n      pristine: {json.dumps(a, sort_keys=True)}\n      mutant  : {json.dumps(b, sort_keys=True)}")

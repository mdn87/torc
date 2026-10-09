"""Mechanical mutation driver. Works only on copies of $MUTATION_SCRATCH/pristine; never touches the real repo.

Usage, from the torc root (MUTATION_SCRATCH is a directory outside the repository that holds
pristine/, a copy of the checkout under test; work-*/ copies and results*.json are written there):

    cd <torc root>
    MUTATION_SCRATCH=<scratch dir> PYTHONPATH=src python3 docs/evidence/pr-25-assessment/scripts/mutation/run_mutations.py [ID ...]
"""
from __future__ import annotations

import difflib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Bundle edit: pristine/, the work-* copies and results*.json live in $MUTATION_SCRATCH
# (outside the repository) instead of next to this script.
if "MUTATION_SCRATCH" not in os.environ:
    raise SystemExit("set MUTATION_SCRATCH to a directory (outside the repo) that holds pristine/, "
                     "a copy of the checkout under test")
BASE = Path(os.environ["MUTATION_SCRATCH"]).resolve()
PRISTINE = BASE / "pristine"

# (id, file under src/torc, short description, old, new)
M: list[tuple[str, str, str, str, str]] = []


def add(mid, fname, desc, old, new):
    M.append((mid, fname, desc, old, new))


# ---------------------------------------------------------------- history.py
add("H1", "history.py", "rollback no longer exempts removals",
    'rolled_back = current["event_type"] == "rollback_applied"',
    "rolled_back = False")
add("H2", "history.py", "returning item no longer clears its drop",
    "            for item in present:\n                open_drops.pop((section, item), None)\n",
    "")
add("H3", "history.py", "later resolution no longer clears earlier drop",
    "        for key in resolved:\n            open_drops.pop(key, None)\n",
    "")
add("H4", "history.py", "handoff_accepted exclusion removed from self-model authorship",
    'elif current["event_type"] != "handoff_accepted" and (',
    "elif True and (")
add("H5", "history.py", "rollback no longer restores authorship",
    "author = authors.get(target, author)",
    "author = author")
add("H6", "history.py", "restatement_due drops `author is not None` guard",
    "return author is not None and author != bearer_substrate_id",
    "return author != bearer_substrate_id")
add("H7", "history.py", "changes_since_substrate base = chain[0]",
    "base, head = chain[index], chain[-1]",
    "base, head = chain[0], chain[-1]")
add("H8", "history.py", "validate_resolutions: 'still present' check deleted",
    "        if item in new_state[section]:\n"
    "            raise InvalidInputError(\n"
    '                f"resolution names an item still present in {section}: {item}"\n'
    "            )\n",
    "")
add("H9", "history.py", "validate_resolutions: 'never dropped' check deleted",
    "        if item not in head_state[section] and (section, item) not in open_keys:\n"
    "            raise InvalidInputError(\n"
    '                f"resolution names an item that was never dropped from {section}: {item}"\n'
    "            )\n",
    "")
add("H10", "history.py", "default removed-item disposition always rolled_back",
    '"unaccounted" if key in unaccounted else "rolled_back"',
    '"rolled_back"')

# ------------------------------------------------------------- projections.py
add("P1", "projections.py", "CARRY_SHARE_PERCENT 5 -> 10",
    "CARRY_SHARE_PERCENT = 5", "CARRY_SHARE_PERCENT = 10")
add("P2", "projections.py", "carry floor removed from descriptor_share",
    'limit, source = min(context_limit, max(CARRY_FLOOR[unit], share)), "descriptor_share"',
    'limit, source = min(context_limit, share), "descriptor_share"')
add("P3", "projections.py", "operator cap can raise the budget",
    "if budget_cap < limit:", "if True:")
add("P4", "projections.py", "capability rule disabled",
    "if needed is not None and needed not in capabilities:", "if False:")
add("P5", "projections.py", "history tier sort: oldest drop first",
    'key=lambda pair: (-position[pair[1]["dropped_at_revision_id"]], pair[0]),',
    'key=lambda pair: (position[pair[1]["dropped_at_revision_id"]], pair[0]),')
add("P6", "projections.py", "required-tier budget check disabled",
    'if used > budget["limit"]:', "if False:")
add("P7", "projections.py", "partial sections omitted whole (no leading items kept)",
    "if kept:", "if False:")
add("P8", "projections.py", "restatement_due hard-coded False in provenance section",
    '"restatement_due": restatement_due(provenance, receiver_substrate_id),',
    '"restatement_due": False,')
add("P9", "projections.py", "characters budget counted as words",
    'if unit == "characters":', "if False:")

# ------------------------------------------------------------------ verify.py
add("V1", "verify.py", "ancestor allowance applies to p0-1 projections too",
    'if str(projection["compiler_version"]).startswith("p5-"):', "if True:")
add("V2", "verify.py", "every lineage revision allowed as projection source_ref",
    "source_prefixes = [f\"{projection['source_revision_id']}:\"]",
    'source_prefixes = [f"{rid}:" for rid in revision_ids]')

# ---------------------------------------------------------------- operator.py
add("O1", "operator.py", "handoff fit candidate_ids restriction removed",
    '        candidate_ids={authority["substrate_id"], target_substrate["substrate_id"]},\n',
    "")
add("O2", "operator.py", "checkpoint skips validate_resolutions",
    "        if resolutions is not None:\n"
    '            head_revision_id = store.get_lineage(lineage_id)["head_revision_id"]\n'
    "            resolutions = validate_resolutions(\n"
    "                revision_chain(store, head_revision_id), canonical_state, resolutions\n"
    "            )\n",
    "        pass\n")

# ------------------------------------------------------------------- store.py
add("S1", "store.py", "empty/None resolutions key always written",
    "if resolutions:", "if True:")

CTRL = ("CTRL", "(none)", "unmutated control copy", None, None)


def run_pytest(work: Path) -> tuple[int, str, bool]:
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-rfE", "-p", "no:cacheprovider"]
    try:
        p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=300)
        return p.returncode, p.stdout + p.stderr, False
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"")
        out = out.decode() if isinstance(out, bytes) else out
        return -1, out + "\n[TIMEOUT after 300s]", True


def one(entry) -> dict:
    mid, fname, desc, old, new = entry
    work = BASE / f"work-{mid}"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(PRISTINE, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    rec: dict = {"id": mid, "file": fname, "desc": desc}
    try:
        diff = ""
        if old is not None:
            target = work / "src" / "torc" / fname
            text = target.read_text(encoding="utf-8")
            n = text.count(old)
            assert n == 1, f"{mid}: expected exactly 1 occurrence of old string, found {n}"
            assert old != new
            mutated = text.replace(old, new, 1)
            target.write_text(mutated, encoding="utf-8")
            diff = "".join(difflib.unified_diff(
                text.splitlines(True), mutated.splitlines(True), "a/" + fname, "b/" + fname, n=0))
            try:
                py_compile.compile(str(target), cfile=str(work / "_chk.pyc"), doraise=True)
                rec["compiles"] = True
            except py_compile.PyCompileError as exc:
                rec["compiles"] = False
                rec["compile_error"] = str(exc)
        rec["diff"] = diff
        t0 = time.time()
        rc, out, timed_out = run_pytest(work)
        rec["seconds"] = round(time.time() - t0, 1)
        rec["returncode"] = rc
        rec["timed_out"] = timed_out
        lines = out.splitlines()
        rec["tail15"] = lines[-15:]
        summ = [ln for ln in lines if re.search(r"\b(passed|failed|error)\b", ln) and " in " in ln]
        rec["summary"] = summ[-1].strip("= ").strip() if summ else ""
        failing = []
        for ln in lines:
            if ln.startswith("FAILED ") or ln.startswith("ERROR "):
                failing.append(ln.split(" - ", 1)[0])
        rec["failing"] = failing
        m = re.search(r"(\d+) passed", rec["summary"])
        rec["passed"] = int(m.group(1)) if m else None
        if rc == 0 and rec["passed"] == 265 and not failing:
            rec["verdict"] = "MISSED"
        elif rc == 0:
            rec["verdict"] = "ANOMALY(rc=0 but counts differ)"
        else:
            rec["verdict"] = "CAUGHT"
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rec


def main() -> None:
    only = set(sys.argv[1:])
    entries = [CTRL] + M
    results = []
    for entry in entries:
        if only and entry[0] not in only:
            continue
        rec = one(entry)
        results.append(rec)
        print(f"{rec['id']:5} {rec['verdict']:7} rc={rec['returncode']:<3} {rec['seconds']:>5}s  "
              f"{rec['summary']}", flush=True)
        for f in rec["failing"][:3]:
            print(f"        {f}", flush=True)
    out = BASE / ("results.json" if not only else "results.partial.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

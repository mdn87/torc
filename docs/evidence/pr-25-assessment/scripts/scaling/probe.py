#!/usr/bin/env python3
"""Deterministic scaling probe for TORC's P5 receiver-fitted carry.

Run from the torc repo root.  The repository is only read: every store lives under
the --out-dir directory (keep it outside the repository), bytecode writing is disabled,
and no TORC code is patched, wrapped or re-implemented (private helpers are only *called*).

    cd <torc root>
    PYTHONPATH=src python3 docs/evidence/pr-25-assessment/scripts/scaling/probe.py --out-dir <scratch dir>

Defaults reproduce the requested protocol (series "drops": N = 25,100,400,1600;
series "resolved": N = 400,1600; REPS = 5; ~5 minutes).  Output: a report on stdout and
<out-dir>/results.json (+ <out-dir>/state/ with the built stores).  Pilot / re-run flags:
    --ns 25,100 --resolved-ns 100 --reps 2 --tag=_pilot     (note the "=": the tag starts
                                                             with "_", not "-")

Protocol per (series, N):
  * Build a fresh store: create + (N-1) checkpoints.  Checkpoint k adds "Task k" to
    open_work and removes "Task k-2" (k >= 3; checkpoints 1 and 2 only add, as nothing
    exists two checkpoints back).  Series "drops" removes it WITHOUT a resolution;
    series "resolved" attaches a "completed" resolution for it.  Constraints and
    commitments never change.  N counts revisions (create + N-1 checkpoints).
  * Every timed operation is run REPS times, each on a pristine file copy of the
    built store opened through a fresh Store() connection, with gc.collect() just
    before the timer.  Tables report the median; min/max stay in results.json.
    The last checkpoint is timed on copies of the store holding N-1 revisions (and
    once inline in the build).  Each carry gets its own copy so one carry's stored
    projection cannot inflate the next one's verification.  Status is read-only.
  * Extras (outside the requested protocol, reported separately): "parts" times
    verify_store / _boundary / revision_chain / unaccounted_drops /
    validate_resolutions / compile_receiver_projection standalone; "acc" stores 1 and
    3 large-receiver projections on one store and re-times verify_store and the next
    checkpoint to show what stored projections cost later calls.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # never write .pyc files into the repository tree

import argparse
import copy
import gc
import json
import math
import os
import platform
import shutil
import sqlite3
import statistics
import time
import traceback
from pathlib import Path

REPO = Path.cwd()  # run from the torc repo root
try:
    import torc  # noqa: F401
except ImportError:  # PYTHONPATH=src was not provided
    sys.path.insert(0, str(REPO / "src"))

from torc.canonical import canonical_json  # noqa: E402
from torc.errors import ProjectionBudgetError  # noqa: E402
from torc.history import revision_chain, unaccounted_drops, validate_resolutions  # noqa: E402
from torc.operator import (  # noqa: E402
    _boundary,
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
)
from torc.projections import compile_receiver_projection  # noqa: E402
from torc.store import Store  # noqa: E402
from torc.verify import verify_store  # noqa: E402

FIXTURE = REPO / "examples" / "p5-dropped-work"
LINEAGE = "probe-lineage"
ACTIVATION = "activation-implementer"


def load(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def log(message: str) -> None:
    print(message, flush=True)


def ms(seconds: float) -> float:
    return seconds * 1000.0


def timed(fn, expected=()):
    """Run fn() once on a collected heap -> (elapsed_seconds, value, expected_exception)."""
    gc.collect()
    start = time.perf_counter()
    try:
        value, exc = fn(), None
    except expected as caught:  # `expected=()` catches nothing
        value, exc = None, caught
    return time.perf_counter() - start, value, exc


def summarize(samples_s):
    ordered = sorted(samples_s)
    return {
        "median_ms": ms(statistics.median(ordered)),
        "min_ms": ms(ordered[0]),
        "max_ms": ms(ordered[-1]),
        "samples_ms": [round(ms(x), 3) for x in samples_s],
    }


def fresh_copy(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def on_copy(src: Path, tmp: Path, op, expected=()):
    """Copy src -> tmp, open it fresh, time op(store), delete tmp."""
    fresh_copy(src, tmp)
    try:
        with Store(tmp) as store:
            elapsed, value, exc = timed(lambda: op(store), expected)
            size = (tmp / "torc.sqlite3").stat().st_size
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return elapsed, value, exc, size


def compile_only(src: Path, tmp: Path, receiver):
    """Time compile_receiver_projection alone (what carry does after verifying)."""
    fresh_copy(src, tmp)
    try:
        with Store(tmp) as store:
            store.register_substrate(receiver)  # carry does this too, untimed here
            head = store.get_lineage(LINEAGE)["head_revision_id"]
            elapsed, _, _ = timed(
                lambda: compile_receiver_projection(
                    store,
                    lineage_id=LINEAGE,
                    source_revision_id=head,
                    receiver_substrate_id=receiver["substrate_id"],
                    purpose="session_start",
                )
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return elapsed


def checkpoint_plan(base_state, count: int, resolved: bool):
    """States for checkpoints k = 1..count: add 'Task k', drop 'Task k-2' (k >= 3)."""
    open_work = list(base_state["open_work"])
    plan = []
    for k in range(1, count + 1):
        open_work.append(f"Task {k}")
        removed = None
        if k >= 3:
            removed = f"Task {k - 2}"
            open_work.remove(removed)
        state = copy.deepcopy(base_state)
        state["open_work"] = list(open_work)
        resolutions = None
        if resolved and removed is not None:
            resolutions = [
                {"section": "open_work", "item": removed, "disposition": "completed"}
            ]
        plan.append((state, resolutions))
    return plan


def do_checkpoint(store, state, resolutions):
    return checkpoint_operator_lineage(
        store,
        lineage_id=LINEAGE,
        activation_id=ACTIVATION,
        canonical_state=state,
        resolutions=resolutions,
    )


def do_carry(store, receiver):
    return carry_operator_lineage(store, lineage_id=LINEAGE, substrate=receiver)


def shape(projection):
    included, omitted = projection["included_sections"], projection["omitted_sections"]
    fit = next(s for s in included if s["section_id"] == "receiver-fit")
    return {
        "budget_unit": projection["budget"]["unit"],
        "budget_limit": projection["budget"]["limit"],
        "budget_used": projection["budget"]["estimated_used"],
        "included": len(included),
        "omitted": len(omitted),
        "unacc_included": sum(s["section_id"].startswith("unaccounted-") for s in included),
        "unacc_omitted": sum(s["section_id"].startswith("unaccounted-") for s in omitted),
        "history_revisions_read": fit["content"]["history_revisions_read"],
        "projection_bytes": len(canonical_json(projection)),
        "other_included": [
            s["section_id"] for s in included if not s["section_id"].startswith("unaccounted-")
        ],
        "other_omitted": [
            f"{s['section_id']}({s['reason']})"
            for s in omitted
            if not s["section_id"].startswith("unaccounted-")
        ],
    }


def dir_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.iterdir() if p.is_file())


def run_cell(series: str, n: int, resolved: bool, reps: int, state_root: Path):
    root = state_root / f"{series}-N{n}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    base_state = load("state-1-created.json")
    source = load("source-substrate.json")
    large, small = load("receiver-large.json"), load("receiver-small.json")
    # n items: k = 1..n-2 build, k = n-1 is the timed last checkpoint, k = n is spare.
    plan = checkpoint_plan(base_state, n, resolved)
    build_dir, tmp = root / "build", root / "tmp"
    cell = {"series": series, "n": n, "resolved": resolved, "reps": reps}
    started = time.perf_counter()

    # ---- (a) build: create + checkpoints 1..n-2, timing every call for the curve.
    per_checkpoint_s = []
    with Store(build_dir) as store:
        create_operator_lineage(
            store,
            lineage_id=LINEAGE,
            canonical_state=base_state,
            substrate=source,
            activation_id=ACTIVATION,
        )
        for k in range(1, n - 1):
            state, res = plan[k - 1]
            elapsed, _, _ = timed(lambda: do_checkpoint(store, state, res))
            per_checkpoint_s.append(elapsed)
            if k % 200 == 0:
                log(f"  [{series} N={n}] built checkpoint {k}/{n - 1}  last={ms(elapsed):.1f} ms"
                    f"  elapsed={time.perf_counter() - started:.0f}s")
    cell["per_checkpoint_ms"] = [round(ms(x), 3) for x in per_checkpoint_s]
    shutil.copytree(build_dir, root / "pre_last")  # store holding n-1 revisions

    # ---- (b) last checkpoint: once inline in the build store, then REPS pristine copies.
    last_state, last_res = plan[n - 2]
    with Store(build_dir) as store:
        inline_s, last_result, _ = timed(lambda: do_checkpoint(store, last_state, last_res))
    cell["checkpoint_inline_ms"] = ms(inline_s)
    cell["checkpoint_result_unaccounted"] = len(last_result["boundary"]["unaccounted"])
    cell["checkpoint_response_bytes"] = len(canonical_json(last_result))
    samples = [
        on_copy(root / "pre_last", tmp, lambda s: do_checkpoint(s, last_state, last_res))[0]
        for _ in range(reps)
    ]
    cell["checkpoint"] = summarize(samples)
    shutil.rmtree(root / "pre_last")
    cell["build_total_s"] = time.perf_counter() - started
    cell["db_bytes_built"] = (build_dir / "torc.sqlite3").stat().st_size
    cell["dir_bytes_built"] = dir_bytes(build_dir)

    # ---- (d) status (read-only: run on the built store with a fresh connection each time).
    samples = []
    for _ in range(reps):
        with Store(build_dir) as store:
            elapsed, status, _ = timed(lambda: operator_lineage_status(store, LINEAGE))
        samples.append(elapsed)
    cell["status"] = summarize(samples)
    cell["status_payload_bytes"] = len(canonical_json(status))

    # ---- extra: where the time goes (all read-only, fresh connection each).
    spare_state, spare_res = plan[n - 1]  # the (n+1)-th revision; valid next checkpoint
    parts = {
        "verify_store": [],
        "boundary": [],  # revision_chain + unaccounted_drops + self_model_provenance
        "revision_chain": [],
        "unaccounted_drops": [],  # on a pre-loaded chain
        "validate_resolutions": [],  # revision_chain + validate_resolutions (series 2 only)
        "lineage_revisions": [],
    }
    verify_valid = None
    for _ in range(reps):
        with Store(build_dir) as store:
            head = store.get_lineage(LINEAGE)["head_revision_id"]
            t, v, _ = timed(lambda: verify_store(store, LINEAGE))
            parts["verify_store"].append(t)
            verify_valid = v["valid"] if verify_valid is None else verify_valid and v["valid"]
            parts["boundary"].append(timed(lambda: _boundary(store, LINEAGE))[0])
            parts["revision_chain"].append(timed(lambda: revision_chain(store, head))[0])
            chain = revision_chain(store, head)
            parts["unaccounted_drops"].append(timed(lambda: unaccounted_drops(chain))[0])
            if spare_res is not None:
                parts["validate_resolutions"].append(
                    timed(
                        lambda: validate_resolutions(
                            revision_chain(store, head), spare_state, spare_res
                        )
                    )[0]
                )
            parts["lineage_revisions"].append(
                timed(lambda: store.lineage_revisions(LINEAGE))[0]
            )
    for name, receiver in (("compile_large", large), ("compile_small", small)):
        parts[name] = [compile_only(build_dir, tmp, receiver) for _ in range(reps)]
    cell["parts"] = {name: summarize(vals) for name, vals in parts.items() if vals}

    # ---- sanity: the synthetic lineage is what the protocol says it is.
    expected_drops = 0 if resolved else max(0, n - 3)
    cell["sanity"] = {
        "revision_count": status["revision_count"],
        "expected_revision_count": n,
        "unaccounted_in_status": len(status["boundary"]["unaccounted"]),
        "expected_unaccounted": expected_drops,
        "verify_valid": verify_valid,
        "open_work_head": status["open_work"],
    }
    cell["sanity"]["ok"] = (
        status["revision_count"] == n
        and len(status["boundary"]["unaccounted"]) == expected_drops
        and verify_valid is True
    )

    # ---- (c) + (e) carries, each on its own pristine copy.
    for name, receiver in (("large", large), ("small", small)):
        samples, first, err, sizes = [], None, None, []
        for _ in range(reps):
            elapsed, value, exc, size = on_copy(
                build_dir, tmp, lambda s: do_carry(s, receiver), (ProjectionBudgetError,)
            )
            samples.append(elapsed)
            sizes.append(size)
            if exc is not None:
                err = f"{type(exc).__name__}: {exc}"
            elif first is None:
                first = value["projection"]
        entry = {"timing": summarize(samples), "db_bytes_after": sizes[0]}
        if err is not None:
            entry["error"] = err
        if first is not None:
            entry["shape"] = shape(first)
        cell[f"carry_{name}"] = entry

    # ---- extra: stored projections make every later verification slower.
    # P = number of large-receiver projections already stored for the lineage.
    acc_dir = fresh_copy(build_dir, root / "acc")
    acc = {"verify_P0": cell["parts"]["verify_store"]}

    def verify_reps(path: Path):
        samples = []
        for _ in range(reps):
            with Store(path) as store:
                samples.append(timed(lambda: verify_store(store, LINEAGE))[0])
        return summarize(samples)

    for stored in (1, 2, 3):
        with Store(acc_dir) as store:
            acc[f"carry_large_{stored}_ms"] = ms(timed(lambda: do_carry(store, large))[0])
        if stored in (1, 3):
            acc[f"verify_P{stored}"] = verify_reps(acc_dir)
    acc["db_bytes_after_3_carries"] = (acc_dir / "torc.sqlite3").stat().st_size
    acc["per_projection_ms_from_P3"] = (
        acc["verify_P3"]["median_ms"] - acc["verify_P0"]["median_ms"]
    ) / 3
    acc["per_projection_ms_from_P1"] = acc["verify_P1"]["median_ms"] - acc["verify_P0"]["median_ms"]
    acc["checkpoint_next_P0"] = summarize(
        [
            on_copy(build_dir, tmp, lambda s: do_checkpoint(s, spare_state, spare_res))[0]
            for _ in range(reps)
        ]
    )
    acc["checkpoint_next_P3"] = summarize(
        [
            on_copy(acc_dir, tmp, lambda s: do_checkpoint(s, spare_state, spare_res))[0]
            for _ in range(reps)
        ]
    )
    shutil.rmtree(acc_dir)
    cell["acc"] = acc
    cell["cell_total_s"] = time.perf_counter() - started
    if tmp.exists():
        shutil.rmtree(tmp)
    log(f"  [{series} N={n}] done in {cell['cell_total_s']:.0f}s  sanity_ok={cell['sanity']['ok']}")
    return cell


# --------------------------------------------------------------------------- reporting


def loglog_slope(points):
    xs = [math.log(x) for x, _ in points]
    ys = [math.log(y) for _, y in points]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)


def growth(label, points):
    parts = []
    for (n1, t1), (n2, t2) in zip(points, points[1:]):
        parts.append(
            f"{n1}->{n2} x{t2 / t1:.2f} (p={math.log(t2 / t1) / math.log(n2 / n1):.2f})"
        )
    text = f"{label:<22}" + "  ".join(parts)
    if len(points) > 2:
        text += f"  | LS log-log p={loglog_slope(points):.2f}"
    if len(points) >= 3:
        (n1, t1), (n2, t2) = points[-2], points[-1]
        slope = (t2 - t1) / (n2 - n1)
        icept = t1 - slope * n1
        preds = ", ".join(
            f"N={n}: pred {icept + slope * n:.1f} vs obs {t:.1f}" for n, t in points[:-2]
        )
        text += f"\n{'':<22}linear model from last two points: {slope * 1000:.1f} us/rev + {icept:.1f} ms; {preds}"
    return text


def fmt(value_ms):
    return f"{value_ms:,.1f}" if value_ms < 1000 else f"{value_ms:,.0f}"


def table(cells):
    header = (
        "| N | drops | ckpt ms | carry-L ms | carry-S ms | status ms | verify ms | db KB "
        "| L limit/used | L incl | L omit | L unacc incl/omit | L hist_read |"
    )
    lines = [header, "|" + "---:|" * (header.count("|") - 1)]
    for c in cells:
        large, small = c["carry_large"], c["carry_small"]
        shp = large.get("shape", {})
        small_cell = fmt(small["timing"]["median_ms"]) + (" ERR" if "shape" not in small else "")
        lines.append(
            "| {n} | {d} | {ck} | {cl} | {cs} | {st} | {vf} | {db} | {lim}/{used} | {inc} | {om} | {ui}/{uo} | {hr} |".format(
                n=c["n"],
                d=c["sanity"]["unaccounted_in_status"],
                ck=fmt(c["checkpoint"]["median_ms"]),
                cl=fmt(large["timing"]["median_ms"]),
                cs=small_cell,
                st=fmt(c["status"]["median_ms"]),
                vf=fmt(c["parts"]["verify_store"]["median_ms"]),
                db=f"{c['db_bytes_built'] / 1024:,.0f}",
                lim=shp.get("budget_limit", "-"),
                used=shp.get("budget_used", "-"),
                inc=shp.get("included", "-"),
                om=shp.get("omitted", "-"),
                ui=shp.get("unacc_included", "-"),
                uo=shp.get("unacc_omitted", "-"),
                hr=shp.get("history_revisions_read", "-"),
            )
        )
    return "\n".join(lines)


def report(results):
    out = []
    for series, title in (
        ("drops", "SERIES 1 - removed items have NO resolution (unaccounted drops accumulate)"),
        ("resolved", "SERIES 2 - removed items carry a 'completed' resolution (no drops)"),
    ):
        cells = [results["series"][series][k] for k in sorted(results["series"][series], key=int)]
        if not cells:
            continue
        out += ["", f"## {title}", "", table(cells), ""]
        for c in cells:
            small = c["carry_small"]
            if "error" in small:
                out.append(f"- N={c['n']} small receiver: {small['error']}")
            if "shape" in small:
                s = small["shape"]
                out.append(
                    f"- N={c['n']} small receiver: limit {s['budget_limit']} used {s['budget_used']}"
                    f" incl {s['included']} omit {s['omitted']} unacc incl/omit"
                    f" {s['unacc_included']}/{s['unacc_omitted']}"
                )
            if not c["sanity"]["ok"]:
                out.append(f"- WARNING N={c['n']} sanity mismatch: {c['sanity']}")
        out += ["", "growth (median ms; p = local log-log exponent between successive N):"]
        for label, getter in (
            ("last checkpoint", lambda c: c["checkpoint"]["median_ms"]),
            ("carry large", lambda c: c["carry_large"]["timing"]["median_ms"]),
            ("carry small", lambda c: c["carry_small"]["timing"]["median_ms"]),
            ("status", lambda c: c["status"]["median_ms"]),
            ("verify_store alone", lambda c: c["parts"]["verify_store"]["median_ms"]),
            ("_boundary alone", lambda c: c["parts"]["boundary"]["median_ms"]),
        ):
            out.append(growth(label, [(c["n"], getter(c)) for c in cells]))
        out += ["", "min..max over reps (ms):"]
        for c in cells:
            out.append(
                f"- N={c['n']}: ckpt {fmt(c['checkpoint']['min_ms'])}..{fmt(c['checkpoint']['max_ms'])}"
                f" (inline {fmt(c['checkpoint_inline_ms'])}), carry-L"
                f" {fmt(c['carry_large']['timing']['min_ms'])}..{fmt(c['carry_large']['timing']['max_ms'])}, carry-S"
                f" {fmt(c['carry_small']['timing']['min_ms'])}..{fmt(c['carry_small']['timing']['max_ms'])}, status"
                f" {fmt(c['status']['min_ms'])}..{fmt(c['status']['max_ms'])}"
            )
        out += ["", "extra - where the time goes (median ms of reps):"]
        for c in cells:
            p = c["parts"]
            out.append(
                f"- N={c['n']}: verify {fmt(p['verify_store']['median_ms'])}, _boundary"
                f" {fmt(p['boundary']['median_ms'])} (revision_chain {fmt(p['revision_chain']['median_ms'])},"
                f" unaccounted_drops {fmt(p['unaccounted_drops']['median_ms'])}),"
                f" validate_resolutions path "
                f"{fmt(p['validate_resolutions']['median_ms']) if 'validate_resolutions' in p else 'n/a'},"
                f" compile large/small {fmt(p['compile_large']['median_ms'])}/{fmt(p['compile_small']['median_ms'])},"
                f" lineage_revisions {fmt(p['lineage_revisions']['median_ms'])}"
            )
        out += ["", "extra - stored-projection accumulation (P = large-receiver projections already stored):"]
        for c in cells:
            a = c["acc"]
            shp = c["carry_large"].get("shape", {})
            out.append(
                f"- N={c['n']}: carry-L #1/#2/#3 on one store {fmt(a['carry_large_1_ms'])}/"
                f"{fmt(a['carry_large_2_ms'])}/{fmt(a['carry_large_3_ms'])}; verify P0/P1/P3"
                f" {fmt(a['verify_P0']['median_ms'])}/{fmt(a['verify_P1']['median_ms'])}/"
                f"{fmt(a['verify_P3']['median_ms'])} => +{fmt(a['per_projection_ms_from_P3'])} ms per stored"
                f" projection; next checkpoint P0 {fmt(a['checkpoint_next_P0']['median_ms'])} vs P3"
                f" {fmt(a['checkpoint_next_P3']['median_ms'])}; stored projection"
                f" {shp.get('projection_bytes', 0) / 1024:,.0f} KB; db {c['db_bytes_built'] / 1024:,.0f} KB built,"
                f" {c['carry_large']['db_bytes_after'] / 1024:,.0f} KB after one large carry,"
                f" {a['db_bytes_after_3_carries'] / 1024:,.0f} KB after three"
            )
        out += ["", "extra - what else the large carry contains:"]
        for c in cells:
            shp = c["carry_large"].get("shape", {})
            out.append(
                f"- N={c['n']}: non-drop included {shp.get('other_included')}; non-drop omitted"
                f" {shp.get('other_omitted')}; checkpoint response {c['checkpoint_response_bytes'] / 1024:,.0f} KB,"
                f" status response {c['status_payload_bytes'] / 1024:,.0f} KB"
            )
    # per-checkpoint curves from the largest build of each series
    for series in ("drops", "resolved"):
        cells = results["series"][series]
        if not cells:
            continue
        big = cells[max(cells, key=int)]
        curve = big["per_checkpoint_ms"]
        width = max(1, len(curve) // 8)
        out += ["", f"## Build-time per-checkpoint curve ({series}, N={big['n']}, single samples, median per bin)"]
        for start in range(0, len(curve), width):
            chunk = curve[start:start + width]
            mid = start + len(chunk) / 2
            med = statistics.median(chunk)
            out.append(
                f"- checkpoints {start + 1}-{start + len(chunk)}: median {med:.1f} ms  ({med * 1000 / mid:.0f} us per revision)"
            )
    return "\n".join(out)


def warm_up(state_root: Path) -> None:
    log("warm-up cell (not recorded) ...")
    run_cell("warmup", 30, False, 1, state_root)
    shutil.rmtree(state_root / "warmup-N30", ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ns", default="25,100,400,1600")
    parser.add_argument("--resolved-ns", default="400,1600")
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--tag", default="")
    parser.add_argument("--out-dir", required=True, type=Path,
                        help="scratch directory (outside the repository) for state*/ and results*.json")
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()
    state_root = out_dir / f"state{args.tag}"
    results_path = out_dir / f"results{args.tag}.json"
    state_root.mkdir(parents=True, exist_ok=True)

    results = {
        "env": {
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "loadavg_start": os.getloadavg(),
            "reps": args.reps,
            "torc_module": str(Path(sys.modules["torc"].__file__).resolve()),
        },
        "series": {"drops": {}, "resolved": {}},
        "failures": [],
    }
    log(json.dumps(results["env"]))
    warm_up(state_root)
    plan = [("drops", int(n), False) for n in args.ns.split(",") if n] + [
        ("resolved", int(n), True) for n in args.resolved_ns.split(",") if n
    ]
    for series, n, resolved in plan:
        log(f"== {series} N={n}")
        try:
            results["series"][series][str(n)] = run_cell(series, n, resolved, args.reps, state_root)
        except Exception:  # keep going, report the traceback at the end
            trace = traceback.format_exc()
            log(trace)
            results["failures"].append({"series": series, "n": n, "traceback": trace})
        results["env"]["loadavg_end"] = os.getloadavg()
        results_path.write_text(json.dumps(results, indent=1), encoding="utf-8")

    text = report(results)
    log(text)
    if results["failures"]:
        log("\nFAILURES:")
        for failure in results["failures"]:
            log(f"--- {failure['series']} N={failure['n']}\n{failure['traceback']}")
    log(f"\nloadavg start/end: {results['env']['loadavg_start']} / {results['env'].get('loadavg_end')}")
    log(f"results: {results_path}")
    return 1 if results["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

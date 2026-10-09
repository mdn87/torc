"""Scenarios the existing tests do not cover. Usage: probe_scenarios.py <tree> <examples-dir>.
Prints one JSON object of observable results; never writes outside a temp dir."""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
FIX = Path(sys.argv[2]).resolve() / "p5-dropped-work"
sys.path.insert(0, str(tree / "src"))
import torc  # noqa: E402

assert Path(torc.__file__).resolve().is_relative_to(tree), torc.__file__

from torc.canonical import seal_record  # noqa: E402
from torc.history import changes_since_substrate, restatement_due, self_model_provenance  # noqa: E402
from torc.operator import (  # noqa: E402
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
    prepare_operator_handoff,
    resolve_operator_handoff,
)
from torc.projections import compile_projection, compile_receiver_projection, estimate_units  # noqa: E402
from torc.store import Store  # noqa: E402
from torc.verify import verify_store  # noqa: E402
from torc.vocabulary import TRACKED_CONTINUITY_SECTIONS  # noqa: E402

LINEAGE, ACTIVATION = "p5-dropped-work", "activation-implementer"
DROPPED_WORK = "Handle exports larger than memory"
DROPPED_CONSTRAINT = "Never write outside the state directory"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def checkpoint(store, state, **kw):
    return checkpoint_operator_lineage(
        store, lineage_id=LINEAGE, activation_id=kw.pop("activation_id", ACTIVATION),
        canonical_state=state, **kw)


def build(store, through=4):
    created = create_operator_lineage(
        store, lineage_id=LINEAGE, canonical_state=load("state-1-created.json"),
        substrate=load("source-substrate.json"), activation_id=ACTIVATION)
    revs = [created["revision_id"]]
    steps = (("state-2-work-added.json", None), ("state-3-item-completed.json", load("resolutions-3.json")),
             ("state-4-last-summary.json", None))
    for name, res in steps[: through - 1]:
        revs.append(checkpoint(store, load(name), resolutions=res)["revision_id"])
    return revs


def handoff_plan():
    return {"target_substrate": load("receiver-large.json"), "target_activation_id": "activation-successor",
            "task_phase": "implementation",
            "requirements": {"capabilities": ["repository_read", "repository_write"],
                             "policy_labels": ["local-workspace"], "minimum_context_units": 1000},
            "target_responsibility": "Finish the lineage export command",
            "reason_code": "model_succession", "rationale": "A larger-context session takes over."}


def synth(i, event, sm, sub, target=None, **state):
    base = {s: [] for s in TRACKED_CONTINUITY_SECTIONS} | {"self_model": sm} | state
    rec = {"revision_id": f"r{i}", "event_type": event, "canonical_state": base,
           "actor": {"kind": "activation", "activation_id": f"act-{sub}" if sub else None, "substrate_id": sub}}
    if target:
        rec["rollback_context"] = {"target_revision_id": target}
    return rec


out: dict = {}


def scenario(name):
    def deco(fn):
        try:
            with tempfile.TemporaryDirectory() as d:
                out[name] = fn(Path(d))
        except Exception as exc:  # noqa: BLE001 - record, do not hide
            out[name] = f"EXC {type(exc).__name__}: {exc}"
            traceback.print_exc(file=sys.stderr)
        return fn
    return deco


@scenario("H5 rollback across another substrate's self-model edit -> authored_by")
def _(tmp):
    chain = [synth(0, "lineage_created", {"v": 0}, None), synth(1, "checkpoint", {"v": 1}, "A"),
             synth(2, "checkpoint", {"v": 2}, "B"), synth(3, "rollback_applied", {"v": 1}, "B", target="r1")]
    return self_model_provenance(chain)["authored_by_substrate_id"]


@scenario("H6a restatement_due for operator-authored (null substrate) self-model")
def _(tmp):
    return restatement_due({"authored_by_substrate_id": None}, "p5-receiver-large")


@scenario("H6b fresh operator lineage status: boundary.self_model.restatement_due")
def _(tmp):
    with Store(tmp) as store:
        create_operator_lineage(store, lineage_id=LINEAGE, canonical_state=load("state-1-created.json"),
                                substrate=load("source-substrate.json"), activation_id=ACTIVATION)
        sm = operator_lineage_status(store, LINEAGE)["boundary"]["self_model"]
        return {k: sm[k] for k in ("authored_by_substrate_id", "bearer_substrate_id", "restatement_due")}


@scenario("H10a changes_since_substrate: unresolved removal disposition (pure)")
def _(tmp):
    chain = [synth(0, "lineage_created", {}, None, open_work=["X"]),
             synth(1, "checkpoint", {}, "R", open_work=["X"]),
             synth(2, "checkpoint", {}, "S", open_work=[])]
    return changes_since_substrate(chain, "R")["removed"]


@scenario("H10b returning-bearer carry: unresolved removal disposition (e2e)")
def _(tmp):
    with Store(tmp) as store:
        build(store, through=3)
        prepared = prepare_operator_handoff(store, lineage_id=LINEAGE, source_activation_id=ACTIVATION,
                                            plan=handoff_plan())
        template = json.loads((store.state_dir / prepared["reconstruction_template_path"]).read_text("utf-8"))
        resolve_operator_handoff(store, handoff_id=prepared["handoff_id"],
                                 target_activation_id="activation-successor", reconstruction=template)
        adv = json.loads(json.dumps(store.get_revision(store.get_lineage(LINEAGE)["head_revision_id"])["canonical_state"]))
        adv["open_work"] = [DROPPED_WORK, "Publish the export guide"]  # drops 'round-trip test', NO resolution
        checkpoint(store, adv, activation_id="activation-successor")
        returning = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=load("source-substrate.json"))["projection"]
        sec = {s["section_id"]: s for s in returning["included_sections"]}
        return sec["changes-since-receiver"]["content"]["removed"]


@scenario("P5 two drops at different revisions: history-tier fit order under a tight budget")
def _(tmp):
    with Store(tmp) as store:
        build(store, through=3)
        s3 = load("state-3-item-completed.json")
        first = json.loads(json.dumps(s3))
        first["constraints"].remove(DROPPED_CONSTRAINT)       # drop #1 (older revision)
        checkpoint(store, first)
        checkpoint(store, load("state-4-last-summary.json"))  # drop #2 (newer revision)
        small = load("receiver-small.json")
        scan = {}
        for n in range(40, 140, 2):
            rc = json.loads(json.dumps(small))
            rc["substrate_id"] = f"scan-{n}"
            rc["context_budget"]["carry_limit"] = n
            try:
                proj = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=rc)["projection"]
            except Exception as exc:  # required tier does not fit
                scan[n] = type(exc).__name__
                continue
            scan[n] = [s["section_id"] for s in proj["included_sections"] if s["section_id"].startswith("unaccounted-")]
        # compress: report the order at the first budget where both fit, and the first where exactly one fits
        both = next((n for n, v in scan.items() if isinstance(v, list) and len(v) == 2), None)
        one = next((n for n, v in scan.items() if isinstance(v, list) and len(v) == 1), None)
        return {"first_budget_both_fit": [both, scan.get(both)], "first_budget_only_one_fits": [one, scan.get(one)]}


@scenario("P9a estimate_units characters vs words (pure)")
def _(tmp):
    return estimate_units({"a": "bb cc dd"}, "characters")


@scenario("P9b carry for a characters-unit receiver: budget.unit / estimated_used")
def _(tmp):
    with Store(tmp) as store:
        build(store)
        rc = load("receiver-large.json")
        rc["substrate_id"] = "chars-receiver"
        rc["context_budget"] = {"unit": "characters", "limit": 200000}
        proj = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=rc)["projection"]
        return {k: proj["budget"][k] for k in ("unit", "limit", "estimated_used")}


@scenario("V1 forged p0-1 projection citing an ancestor revision -> verify errors")
def _(tmp):
    with Store(tmp) as store:
        revs = build(store)
        frozen = compile_projection(store, lineage_id=LINEAGE, source_revision_id=revs[-1],
                                    target_substrate_id="p5-implementer", budget_limit=10000,
                                    handoff_reason="model_succession", target_responsibility="Continue")
        forged = seal_record({k: v for k, v in frozen.items() if k != "integrity"} | {
            "projection_id": "projection-forged-p0",
            "included_sections": [s | {"source_ref": f"{revs[-2]}:open_work"} if s["section_id"] == "open-work" else s
                                  for s in frozen["included_sections"]]})
        store.insert_hashed_record("projections", "projection-forged-p0", forged)
        return [(e["code"], e["record_id"]) for e in verify_store(store, LINEAGE)["errors"]]


@scenario("V2 forged p5-1 projection citing a LATER revision of the same lineage -> verify errors")
def _(tmp):
    with Store(tmp) as store:
        revs = build(store)
        old = compile_receiver_projection(store, lineage_id=LINEAGE, source_revision_id=revs[1],
                                          receiver_substrate_id="p5-implementer", purpose="session_start")
        forged = seal_record({k: v for k, v in old.items() if k != "integrity"} | {
            "projection_id": "projection-forged-p5",
            "included_sections": [s | {"source_ref": f"{revs[3]}:constraints"} if s["section_id"] == "constraints" else s
                                  for s in old["included_sections"]]})
        store.insert_hashed_record("projections", "projection-forged-p5", forged)
        return [(e["code"], e["record_id"]) for e in verify_store(store, LINEAGE)["errors"]]


print(json.dumps(out, indent=1, sort_keys=True, default=str))

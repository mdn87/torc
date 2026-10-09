"""Replay the P5 fixture and measure what each transport delivers.

Run from the torc checkout: PYTHONPATH=src python3 <this file> <scratch-state-root>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from torc.operator import (
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
    prepare_operator_handoff,
    render_carry,
    resolve_operator_handoff,
)
from torc.projections import compile_projection, compile_receiver_projection
from torc.store import Store

ROOT = Path.cwd()
FIXTURE = ROOT / "examples" / "p5-dropped-work"
LINEAGE = "p5-dropped-work"
ACTIVATION = "activation-implementer"
DROPPED_WORK = "Handle exports larger than memory"
DROPPED_CONSTRAINT = "Never write outside the state directory"
WORD = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)


def load(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def words(text: str) -> int:
    return len(WORD.findall(text))


def build(store: Store) -> list[str]:
    created = create_operator_lineage(
        store,
        lineage_id=LINEAGE,
        canonical_state=load("state-1-created.json"),
        substrate=load("source-substrate.json"),
        activation_id=ACTIVATION,
    )
    revisions = [created["revision_id"]]
    for name, resolutions in (
        ("state-2-work-added.json", None),
        ("state-3-item-completed.json", load("resolutions-3.json")),
        ("state-4-last-summary.json", None),
    ):
        response = checkpoint_operator_lineage(
            store,
            lineage_id=LINEAGE,
            activation_id=ACTIVATION,
            canonical_state=load(name),
            resolutions=resolutions,
        )
        revisions.append(response["revision_id"])
        print(f"  checkpoint {name}: unaccounted={[(d['section'], d['item']) for d in response['boundary']['unaccounted']]}")
    return revisions


def section_table(projection) -> str:
    rows = []
    for s in projection["included_sections"]:
        rows.append(f"    + {s['section_id']:<28} {s['estimated_units']:>4} {projection['budget']['unit']}  req={s['required']} prio={s['priority']}")
    for s in projection["omitted_sections"]:
        rows.append(f"    - {s['section_id']:<28} omitted: {s['reason']}")
    return "\n".join(rows)


def compiled_prompt_from_head(state: dict, responsibility: str) -> dict:
    """The P1 compiled-prompt lane shape (experiment_lanes.materialize_compiled_prompt),
    built from the head state the way the P1 source capture is built."""
    return {
        "instruction": "Continue the work using only this frozen continuity.",
        "continuity": {
            "lineage_identity": state["identity"]["label"],
            "current_responsibility": responsibility,
            "settled_decisions": state["self_model"].get("settled_decisions", []),
            "active_commitments": state["commitments"],
            "hard_constraints": state["constraints"],
            "unresolved_work": state["open_work"],
            "uncertainties": state["uncertainties"],
            "evidence_refs": state["artifact_refs"],
        },
    }


def main(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    print("== 1. Fixture replay ==")
    with Store(root / "replay") as store:
        revisions = build(store)
        head = store.get_revision(revisions[-1])["canonical_state"]
        status = operator_lineage_status(store, LINEAGE)
        print(f"  status.boundary.self_model = {status['boundary']['self_model']}")

        results = {}
        for receiver in ("receiver-small.json", "receiver-large.json"):
            carried = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=load(receiver))
            p = carried["projection"]
            results[receiver] = p
            rendered = render_carry(p)
            print(f"\n  P5 carry for {receiver}: budget {p['budget']['estimated_used']}/{p['budget']['limit']} {p['budget']['unit']}, sections {len(p['included_sections'])} included / {len(p['omitted_sections'])} omitted")
            print(section_table(p))
            required_units = sum(s["estimated_units"] for s in p["included_sections"] if s["required"])
            history_units = sum(s["estimated_units"] for s in p["included_sections"] if s["section_id"].startswith(("unaccounted-", "changes-since")))
            optional_units = p["budget"]["estimated_used"] - required_units - history_units
            print(f"    units: required={required_units} history={history_units} optional={optional_units}")
            print(f"    rendered carry: {words(rendered)} words, {len(rendered.encode())} bytes; canonical projection JSON: {len(json.dumps(p, sort_keys=True, separators=(',', ':')).encode())} bytes")
            print(f"    carries dropped work: {DROPPED_WORK in rendered}; carries dropped constraint: {DROPPED_CONSTRAINT in rendered}")
            (root / f"carry-{receiver}.md").write_text(rendered, encoding="utf-8")
            (root / f"carry-{receiver}.json").write_text(json.dumps(p, indent=2, sort_keys=True), encoding="utf-8")

        print("\n== 2. Same head, P0 compiler at the same budgets ==")
        for receiver, limit in (("receiver-small.json", 100), ("receiver-large.json", 10000)):
            substrate_id = load(receiver)["substrate_id"]
            try:
                p0 = compile_projection(
                    store,
                    lineage_id=LINEAGE,
                    source_revision_id=revisions[-1],
                    target_substrate_id=substrate_id,
                    budget_limit=limit,
                    handoff_reason="model_succession",
                    target_responsibility="Continue the export command",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  P0 for {receiver} at {limit}: {type(exc).__name__}: {exc}")
                continue
            text = json.dumps(p0["included_sections"])
            print(f"  P0 for {receiver} at {limit}: used {p0['budget']['estimated_used']}, included {[s['section_id'] for s in p0['included_sections']]}, omitted {[s['section_id'] for s in p0['omitted_sections']]}")
            print(f"    carries dropped work: {DROPPED_WORK in text}; carries dropped constraint: {DROPPED_CONSTRAINT in text}")

        print("\n== 3. P1 compiled-prompt lane shape from the same head ==")
        cp = compiled_prompt_from_head(head, "Continue the export command")
        cp_text = json.dumps(cp)
        print(f"  compiled prompt: {words(cp_text)} words, {len(cp_text.encode())} bytes; carries dropped work: {DROPPED_WORK in cp_text}; carries dropped constraint: {DROPPED_CONSTRAINT in cp_text}")

        print("\n== 4. Smallest receiver budget that compiles (small receiver descriptor) ==")
        lo, hi = 1, 100
        floor_fit = None
        while lo <= hi:
            mid = (lo + hi) // 2
            desc = load("receiver-small.json") | {"substrate_id": f"probe-{mid}"}
            desc["context_budget"]["carry_limit"] = mid
            try:
                with Store(root / f"probe-{mid}") as probe_store:
                    build_quiet(probe_store)
                    p = carry_operator_lineage(probe_store, lineage_id=LINEAGE, substrate=desc)["projection"]
                floor_fit = (mid, p)
                hi = mid - 1
            except Exception:  # noqa: BLE001
                lo = mid + 1
        if floor_fit:
            mid, p = floor_fit
            print(f"  smallest carry_limit that compiles: {mid} words (required tier = {sum(s['estimated_units'] for s in p['included_sections'] if s['required'])} words)")
            for s in p["included_sections"]:
                if s["required"]:
                    print(f"    required {s['section_id']:<24} {s['estimated_units']:>3} words")
            print(f"    at that budget the history tier is: {[o['section_id'] + ':' + o['reason'] for o in p['omitted_sections'] if o['section_id'].startswith('unaccounted')] or 'included'}")

    print("\n== 5. Codex review scenarios ==")
    scenario_resolve_restore_drop(root / "s1")
    scenario_restate_unchanged(root / "s2")
    scenario_returning_substrate(root / "s3")


def build_quiet(store: Store) -> list[str]:
    created = create_operator_lineage(
        store,
        lineage_id=LINEAGE,
        canonical_state=load("state-1-created.json"),
        substrate=load("source-substrate.json"),
        activation_id=ACTIVATION,
    )
    revisions = [created["revision_id"]]
    for name, resolutions in (
        ("state-2-work-added.json", None),
        ("state-3-item-completed.json", load("resolutions-3.json")),
        ("state-4-last-summary.json", None),
    ):
        revisions.append(
            checkpoint_operator_lineage(
                store, lineage_id=LINEAGE, activation_id=ACTIVATION,
                canonical_state=load(name), resolutions=resolutions,
            )["revision_id"]
        )
    return revisions


def handoff_plan() -> dict:
    return {
        "target_substrate": load("receiver-large.json"),
        "target_activation_id": "activation-successor",
        "task_phase": "implementation",
        "requirements": {
            "capabilities": ["repository_read", "repository_write"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 1000,
        },
        "target_responsibility": "Finish the lineage export command",
        "reason_code": "model_succession",
        "rationale": "A larger-context session takes over the export work.",
    }


def do_handoff(store: Store, source_activation: str, plan: dict) -> None:
    prepared = prepare_operator_handoff(
        store, lineage_id=LINEAGE, source_activation_id=source_activation, plan=plan
    )
    template = json.loads(
        (store.state_dir / prepared["reconstruction_template_path"]).read_text(encoding="utf-8")
    )
    result = resolve_operator_handoff(
        store,
        handoff_id=prepared["handoff_id"],
        target_activation_id=plan["target_activation_id"],
        reconstruction=template,
    )
    assert result["disposition"] == "accepted", result


def head_state(store: Store) -> dict:
    return json.loads(json.dumps(
        store.get_revision(store.get_lineage(LINEAGE)["head_revision_id"])["canonical_state"]
    ))


def scenario_resolve_restore_drop(root: Path) -> None:
    """Item resolved, restored, dropped again without a resolution; the returning
    original substrate asks what changed."""
    print("\n  S1: resolve -> restore -> drop again, then carry for the substrate that was away")
    with Store(root) as store:
        build_quiet(store)  # head: open_work = [round-trip test]; implementer authored
        do_handoff(store, ACTIVATION, handoff_plan())  # successor (p5-receiver-large) now bears
        state = head_state(store)
        # successor removes the round-trip test WITH a resolution
        state["open_work"] = []
        checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-successor", canonical_state=state,
            resolutions=[{"section": "open_work", "item": "Write the export round-trip test", "disposition": "completed"}],
        )
        # successor restores it
        state = head_state(store)
        state["open_work"] = ["Write the export round-trip test"]
        checkpoint_operator_lineage(store, lineage_id=LINEAGE, activation_id="activation-successor", canonical_state=state)
        # successor drops it again WITHOUT a resolution
        state = head_state(store)
        state["open_work"] = []
        response = checkpoint_operator_lineage(store, lineage_id=LINEAGE, activation_id="activation-successor", canonical_state=state)
        print(f"    boundary.unaccounted after second drop: {[(d['section'], d['item']) for d in response['boundary']['unaccounted']]}")
        carry = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=load("source-substrate.json"))["projection"]
        sections = {s["section_id"]: s for s in carry["included_sections"]}
        changes = sections.get("changes-since-receiver", {}).get("content")
        print(f"    changes-since-receiver.removed: {changes and changes.get('removed')}")
        print(f"    unaccounted sections in carry: {[k for k in sections if k.startswith('unaccounted-')]}")
        contradictory = changes and any(
            r["disposition"] != "unaccounted" for r in changes.get("removed", {}).get("open_work", [])
        ) and any(k.startswith("unaccounted-") for k in sections)
        print(f"    CONTRADICTION (same item both 'completed' and unaccounted): {bool(contradictory)}")


def scenario_restate_unchanged(root: Path) -> None:
    """New bearer confirms the inherited self-model verbatim via self_model_revised."""
    print("\n  S2: successor confirms the inherited self-model unchanged with self_model_revised")
    with Store(root) as store:
        build_quiet(store)
        do_handoff(store, ACTIVATION, handoff_plan())
        before = operator_lineage_status(store, LINEAGE)["boundary"]["self_model"]
        response = checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-successor",
            canonical_state=head_state(store), event_type="self_model_revised",
        )
        after = response["boundary"]["self_model"]
        print(f"    before: author={before['authored_by_substrate_id']} restatement_due={before['restatement_due']}")
        print(f"    after unchanged self_model_revised: author={after['authored_by_substrate_id']} restatement_due={after['restatement_due']}")
        # and with a trivial change
        state = head_state(store)
        state["self_model"]["methods"] = ["Write the failing test first", "Confirmed by successor"]
        changed = checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-successor",
            canonical_state=state, event_type="self_model_revised",
        )["boundary"]["self_model"]
        print(f"    after changed self_model_revised: author={changed['authored_by_substrate_id']} restatement_due={changed['restatement_due']}")


def scenario_returning_substrate(root: Path) -> None:
    """A -> B (B completes work with a resolution) -> back to A; A's carry."""
    print("\n  S3: implementer hands to successor, successor resolves work, hands back; implementer's carry")
    with Store(root) as store:
        build_quiet(store)
        do_handoff(store, ACTIVATION, handoff_plan())
        state = head_state(store)
        state["open_work"] = ["Publish the export guide"]
        checkpoint_operator_lineage(
            store, lineage_id=LINEAGE, activation_id="activation-successor", canonical_state=state,
            resolutions=[{"section": "open_work", "item": "Write the export round-trip test", "disposition": "completed"}],
        )
        # carry for the implementer BEFORE it takes the lineage back
        before = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=load("source-substrate.json"))["projection"]
        b_sections = {s["section_id"]: s for s in before["included_sections"]}
        print(f"    carry for implementer while successor still bears: changes-since-receiver present={('changes-since-receiver' in b_sections)}; revisions_since={b_sections.get('changes-since-receiver', {}).get('content', {}).get('revisions_since')}")
        # hand back to the implementer (new activation on the source substrate)
        plan = handoff_plan() | {
            "target_substrate": load("source-substrate.json"),
            "target_activation_id": "activation-implementer-2",
            "target_responsibility": "Resume the export command",
        }
        do_handoff(store, "activation-successor", plan)
        after = carry_operator_lineage(store, lineage_id=LINEAGE, substrate=load("source-substrate.json"))["projection"]
        a_sections = {s["section_id"]: s for s in after["included_sections"]}
        print(f"    carry for implementer after taking the lineage back: changes-since-receiver present={('changes-since-receiver' in a_sections)}")
        print(f"    session-purpose: {a_sections['session-purpose']['content']}")
        print(f"    self-model-provenance: {a_sections['self-model-provenance']['content']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

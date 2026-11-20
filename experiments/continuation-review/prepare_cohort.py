"""Prepare matched held-out contexts and reviewer questions. Runs no candidates or models."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory

from torc.canonical import canonical_json, payload_sha256
from torc.p5_capsules import derive, verify
from torc.projections import compile_receiver_projection
from torc.store import Store

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INVENTORY = ROOT / "docs/evidence/2026-11-20-continuation-fixtures.json"
INTAKE = ROOT / ".torc/fixture-intake/2026-11-20"
BRIEF = "CONTINUATION_BRIEF.md"
LANE = ("Use Read, Glob, Grep, Edit and Write in the supplied source tree. "
        "Only edit the listed files. Report any checks you could not perform.")
INTRO = ("Continue the interrupted task. The starting files and " + BRIEF
         + " are available to you.\n" + LANE + "\n\n").encode()


def read_specs():
    return json.loads((HERE / "heldout-cases.json").read_bytes())


def checked(path, pin):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != pin:
        raise ValueError(f"Content changed: {path.name}")
    return data


def relative_file(name):
    path = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if (not name or windows.drive or windows.root or "\\" in name or ":" in name
            or ".." in path.parts or path.as_posix() != name or name == "."):
        raise ValueError(f"Invalid study file name: {name}")
    return path


def write_json(path, value):
    path.write_bytes(canonical_json(value).encode("utf-8"))


def retained_state(case, spec):
    return {
        "identity": {"label": case},
        "self_model": {"role": spec["request"], "settled_decisions": [spec["at_stop"]],
                       "methods": []},
        "constraints": [LANE, *spec["holds"]], "goals": [spec["request"]],
        "commitments": [], "open_work": spec["requirements"], "uncertainties": [],
        "artifact_refs": [BRIEF], "memory_refs": [],
    }


def plain_notes(spec):
    blocks = [spec["request"], spec["at_stop"], *spec["requirements"], *spec["holds"]]
    return "\n\n".join(blocks)


def prepare_case(row, spec, intake, destination):
    case = row["candidate_id"]
    directory = intake / relative_file(case)
    tree = directory / "complete-tree"
    if not tree.is_dir():
        tree = directory / "tree"
    manifest = json.loads(checked(directory / f"{tree.name}-manifest.json",
                                  row["tree_manifest_sha256"]))
    history = directory / "history-extended.json"
    if not history.exists():
        history = directory / "history.json"
    events = json.loads(checked(history, row["history_sha256"]))["events"]
    lines = {e["source_line"]: payload_sha256(e) for e in events}
    provenance = {str(n): lines[n] for n in spec["source_lines"]}
    editable = [*row["editable_files"], *spec.get("additional_editable_files", [])]
    for name in editable:
        relative_file(name)
    if len(editable) != len(set(editable)) or any(n.casefold() == BRIEF.casefold()
                                                  for n in [*editable, *manifest]):
        raise ValueError("Duplicate edit path or reserved briefing name")

    destination.mkdir(parents=True, exist_ok=False)
    shared = destination / "shared"
    shared.mkdir()
    for name, pin in manifest.items():
        rel = relative_file(name)
        src = tree / rel
        if src.resolve(strict=True) != src.absolute():
            raise ValueError(f"Expected an ordinary source file: {name}")
        target = shared / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(checked(src, pin))

    notes = plain_notes(spec)
    brief = (notes + "\n\nPermitted files\n" + "\n".join(editable) + "\n\n" + LANE
             + "\n\nSource record\n" + row["history_sha256"] + "\nRetained event lines "
             + ", ".join(map(str, spec["source_lines"])) + "\n").encode()
    (shared / BRIEF).write_bytes(brief)
    at = row["boundary_timestamp"]
    state = retained_state(case, spec)
    lineage, revision = case + "-lineage", case + "-stop"
    # The timestamp and IDs make retrospective preparation reproducible.
    # The lease belongs to preparation. Receiving a prompt transfers no authority.
    with Store(destination / "control") as store:
        descriptor = {"schema_version": 1, "adapter": "manual",
                      "capabilities": ["repository_read", "repository_write"],
                      "policy_labels": ["local-workspace"], "task_affinities": ["implementation"],
                      "context_budget": {"unit": "words", "limit": 32000, "carry_limit": 400}}
        store.register_substrate({**descriptor, "substrate_id": "study-receiver",
                                  "label": "File editing receiver"})
        store.register_substrate({**descriptor, "substrate_id": "study-preparation",
                                  "label": "Retrospective preparation"})
        store.create_lineage(lineage, state, revision_id=revision, created_at=at)
        activation = case + "-preparation"
        store.create_activation(lineage, revision, "study-preparation",
                                activation_id=activation, started_at=at)
        store.acquire_lease(lineage, activation, lease_id=case + "-lease", issued_at=at)
        projection = compile_receiver_projection(
            store, lineage_id=lineage, source_revision_id=revision,
            receiver_substrate_id="study-receiver", purpose="session_start",
            projection_id=case + "-projection", compiled_at=at)
        identity = projection["projection_id"], projection["integrity"]["canonical_payload_sha256"]
        capsule, control, composition = derive(store, *identity)
        verify(store, *identity, capsule, control, composition)
    write_json(destination / "composition.json", composition)
    prompts = destination / "prompts"
    prompts.mkdir()
    pins = {}
    for arm, body in (("compiled", notes), ("torc", canonical_json(capsule))):
        data = INTRO + body.encode("utf-8") + b"\n"
        (prompts / f"{arm}.txt").write_bytes(data)
        pins[arm] = hashlib.sha256(data).hexdigest()

    review = {"task": case, "request": spec["request"], "at_stop": spec["at_stop"],
              "rows": spec["review"], "usable": spec["usable"], "preference": spec["preference"],
              "reason": spec["reason"], "missing_observation": "Cannot judge"}
    write_json(destination / "review.json", review)
    brief_pin = hashlib.sha256(brief).hexdigest()
    receipt = {
        "case": case, "source_tree_sha256": row["tree_manifest_sha256"],
        "source_files": len(manifest), "source_prefix_sha256": row["source_prefix_sha256"],
        "history_sha256": row["history_sha256"], "event_sha256": provenance,
        "editable_files": editable, "brief_sha256": brief_pin,
        "shared_files_sha256": payload_sha256({**manifest, BRIEF: brief_pin}),
        "review_sha256": payload_sha256(review), "prompt_sha256": pins,
        "projection_sha256": identity[1], "composition_sha256": payload_sha256(composition),
    }
    write_json(destination / "preparation.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New private output directory")
    parser.add_argument("--intake", type=Path, default=INTAKE)
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_bytes())
    specs = read_specs()
    cases = inventory["candidates"]
    if len(cases) != 8 or {r["candidate_id"] for r in cases} != set(specs):
        raise ValueError("The eight recovered tasks and review definitions must match")
    dest = args.destination.resolve()
    if dest.exists():
        parser.error("Choose a new output directory")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=dest.parent) as scratch:
        staged = Path(scratch) / "study"
        receipts = [prepare_case(r, specs[r["candidate_id"]], args.intake,
                                 staged / r["candidate_id"]) for r in cases]
        result = {"version": 1, "cases": receipts, "definitions_sha256": payload_sha256(specs),
                  "inventory_sha256": hashlib.sha256(INVENTORY.read_bytes()).hexdigest()}
        write_json(staged / "preparation.json", result)
        staged.rename(dest)
    print(f"Prepared {len(receipts)} matched tasks. Receipt {payload_sha256(result)}")


if __name__ == "__main__":
    main()

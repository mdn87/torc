"""Model-free scorer qualification using trusted history and Autowork ownership.

This command accepts no worker candidate and grants no live-trial admission.
It proves a bounded fixture path, including read isolation and runtime integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import workloads

OWNER_HASHES = {
    "provider_safety.py": "f30a9412ffbbb3616ae6d7aea89b53009241beb85632520ebda401b13068c6d9",
    "agent_assignment.py": "06b90de048d7135408e27b05143af7946b214c5f21ddde9a7331adfbe84ea266",
    "owned_subprocess.py": "d850094cdf965c1c3a7e4f0daa035d40bc1d1c52d515257595bf2ae073d8ddf8",
    "verification.py": "167ea1b6807a553b3c2cdef49c0e9c8b63102f7adf913cd3d49ed9f6d01261bc",
    "process_owner.py": "73f72ee41e9df436d3fb4e4433779c44528df4c97b9ae4eba03648bef210fcb3",
    "route_supervisor.py": "d6a0f8e1f7e24d1eb7529a4161ba60263358ae476f22c8dceed92507cb22e73e",
}
ENTRY = (
    'import os,runpy,sys; os.chdir("workspace"); '
    'sys.argv=["pytest",*sys.argv[1:]]; runpy.run_module("pytest",run_name="__main__")'
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def runtime_hash(root):
    # Hash contents and symlink destinations; Python/framework dependencies
    # outside this venv are separately identified by the interpreter probe.
    values = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            values[path.relative_to(root).as_posix()] = {"symlink": os.readlink(path)}
        elif path.is_file():
            values[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    return sha(json.dumps(values, sort_keys=True).encode())


def load_owner(owner):
    if sys.platform != "darwin":
        raise ValueError("only the inspected macOS scorer path is supported")
    owner = Path(owner).resolve()
    source = owner / "src"
    for name, expected in OWNER_HASHES.items():
        path = source / "autowork/campaign" / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise ValueError("execution owner changed; inspect scorer path again")
    sys.path.insert(0, str(source))
    modules = {}
    for name in ("agent_assignment", "provider_safety", "owned_subprocess", "verification"):
        module = importlib.import_module("autowork.campaign." + name)
        if not Path(module.__file__).resolve().is_relative_to(source):
            raise ValueError("loaded module is outside declared owner")
        modules[name] = module
    return owner, modules


def sandbox_argv(codex, root, projection, command):
    args = []
    for i, token in enumerate(projection.safety_argv[:-1]):
        if token in {"-c", "--disable"}:
            args.extend((token, projection.safety_argv[i + 1]))
    return (
        str(codex),
        "sandbox",
        "-P",
        "autowork_isolated",
        "-C",
        str(root),
        *args,
        "--",
        *command,
    )


def controls_pass(rows):
    expected = {
        (task, kind) for task in workloads.TASKS for kind in ("baseline", "reference", "mutant")
    }
    if len(rows) != len(expected) or {(r["task"], r["kind"]) for r in rows} != expected:
        return False
    for row in rows:
        if (row["timed_out"] or row["interrupted"] or not row["runtime_unchanged"]
                or not row["inputs_unchanged"]):
            return False
        code = row["exit_code"]
        if type(code) is not int or (code != 0 if row["kind"] == "reference" else code == 0):
            return False
        if row["kind"] == "reference" and "[100%]" not in row["stdout"]:
            return False
        if row["kind"] == "mutant" and (code != 1 or "FAILED " not in row["stdout"]):
            return False
    return True


def qualify(owner, runtime, destination):
    owner, api = load_owner(owner)
    runtime = Path(runtime).resolve(strict=True)
    if not (runtime / "pyvenv.cfg").is_file():
        raise ValueError("provide the dedicated scorer virtualenv")
    root = Path(destination).resolve()
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    receipts = root / "receipts"
    receipts.mkdir()
    home = root / "empty-home"
    home.mkdir()
    private = root / "private-arm-sentinel"
    private.write_text("private-arm-label-not-for-scorer")
    codex = Path(shutil.which("codex")).resolve(strict=True)
    env = {
        "PATH": str(codex.parent) + os.pathsep + os.defpath,
        "HOME": str(home),
        "CODEX_HOME": str(home),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "LC_ALL": "C",
    }
    version = subprocess.run(
        [str(codex), "--version"], env=env, capture_output=True, text=True, check=True, timeout=15
    ).stdout.strip()
    if version != "codex-cli 0.163.0":
        raise ValueError("scorer qualification requires the inspected Codex 0.163.0")
    policy = api["provider_safety"].load_provider_safety_manifest(
        owner / "campaign/provider-safety/codex-0.163.0.toml"
    )
    api["provider_safety"].inspect_provider_safety(
        policy, inherited_env=env, argv_prefix=(str(codex),)
    )
    assignment = api["agent_assignment"].AgentAssignment.from_dict(
        json.loads((owner / "tests/fixtures/agent-assignment/v2/write-worker.json").read_text())
    )
    assignment = replace(assignment, grant=replace(assignment.grant, loaded_skills=()))
    seed_hash = runtime_hash(runtime)
    counter = 0

    def run(label, argv, cwd):
        nonlocal counter
        counter += 1
        identity = f"scorer-{counter:02d}-{label}"
        record = {
            "attempt_id": identity,
            "argv": list(argv),
            "cwd": str(cwd),
            "status": "starting",
            "model_call": False,
        }
        write(receipts / (identity + "-start.json"), record)
        spec = api["owned_subprocess"].OwnedSubprocessSpec(
            argv=tuple(argv),
            supervisor_python=Path(sys.executable).resolve(),
            cwd=cwd,
            env=env,
            owner_path=receipts / (identity + "-owner.json"),
            run_id=identity,
            timeout_seconds=120,
        )
        try:
            result = api["owned_subprocess"].run_owned_subprocess(spec)
        except Exception as error:
            write(
                receipts / (identity + "-failure.json"),
                {"error_type": type(error).__name__, "error": str(error)},
            )
            raise
        row = {
            "attempt_id": identity,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "interrupted": result.interrupted,
            "owner_evidence": result.owner_evidence(),
        }
        write(receipts / (identity + "-result.json"), row)
        return row

    rows, effects = [], {}
    for task in workloads.TASKS:
        candidate = root / (task + "-trusted-candidate")
        workloads.stage(task, candidate)
        editable = workloads.TASKS[task]["editable_paths"][0]
        for kind in ("baseline", "reference", "mutant"):
            if kind == "reference":
                (candidate / editable).write_bytes(
                    workloads._git("show", f"{workloads.REFERENCE}:{editable}")
                )
            elif kind == "mutant":
                path = candidate / editable
                old, new = (
                    (
                        "current.update(lineage_id=lineage_id, "
                        'lineage_revision_id=lineage["head_revision_id"])',
                        "current.update(lineage_id=lineage_id)",
                    )
                    if task == "capsule-context"
                    else ("ordered[-1][f] if ordered else None", "_sum([n[f] for n in ordered])")
                )
                text = path.read_text()
                if text.count(old) != 1:
                    raise ValueError("trusted historical mutant site changed")
                path.write_text(text.replace(old, new))
            packet = root / f"{task}-{kind}"
            packet.mkdir()
            job = workloads.prepare_score(task, candidate, packet / "workspace")
            local_runtime = packet / ".codex/runtime"
            shutil.copytree(runtime, local_runtime, symlinks=True, copy_function=os.link)
            if runtime_hash(local_runtime) != seed_hash:
                raise ValueError("runtime copy changed")
            python = str(local_runtime / "bin/python")
            projection = api["provider_safety"].build_controller_safety_projection(
                assignment=assignment,
                manifest=policy,
                codex_launch_sha256=sha(codex.read_bytes()),
                final_env=env,
                workspace=packet,
            )
            command = partial(sandbox_argv, codex, packet, projection)
            if not effects:
                read = (
                    python,
                    "-I",
                    "-c",
                    "import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text())",
                    str(private),
                )
                old = api["verification"]._sandbox_logical_argv(packet, packet, read)
                legacy = run("legacy-read", (str(codex), *old[1:]), packet)
                effects["legacy_private_read_visible"] = private.read_text() in legacy["stdout"]
                denied = run("private-read", command(read), packet)
                effects["private_read_denied"] = (
                    denied["exit_code"] == 1 and "PermissionError" in denied["stderr"]
                )
                write_code = 'import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("probe")'
                for label, target in (
                    ("runtime-write", local_runtime / "write-probe"),
                    ("outside-write", root / "outside-write-probe"),
                ):
                    denied = run(
                        label, command((python, "-I", "-c", write_code, str(target))), packet
                    )
                    effects[label + "-denied"] = (
                        denied["exit_code"] == 1
                        and "PermissionError" in denied["stderr"]
                        and not target.exists()
                    )
                positive = run(
                    "candidate-write",
                    command((python, "-I", "-c", write_code, str(packet / "scratch-probe"))),
                    packet,
                )
                effects["candidate_write_allowed"] = positive["exit_code"] == 0
                runtime_info = run(
                    "runtime-info",
                    command(
                        (
                            python,
                            "-I",
                            "-c",
                            'import importlib.metadata as m,json,sys;'
                            'print(json.dumps({"python":sys.version,"prefix":sys.prefix,'
                            '"packages":{n:m.version(n) for n in '
                            '("pytest","jsonschema","PyYAML")}}))',
                        )
                    ),
                    packet,
                )
                effects["runtime_imports"] = runtime_info["exit_code"] == 0
                effects["runtime_info"] = (
                    json.loads(runtime_info["stdout"]) if effects["runtime_imports"] else None
                )
                try:
                    with socket.create_connection(("1.1.1.1", 443), timeout=3):
                        effects["network_positive_control"] = True
                except OSError:
                    effects["network_positive_control"] = False
                denied = run("network", command((python, "-I", "-c",
                    'import socket; socket.create_connection(("1.1.1.1",443),timeout=3).close()')),
                    packet)
                effects["network_denied"] = (denied["exit_code"] == 1
                    and "PermissionError" in denied["stderr"])
            before = runtime_hash(local_runtime)
            input_files = workloads._entries(packet / "workspace")
            actual = (python, "-I", "-c", ENTRY, *job["command"][4:])
            result = run(task + "-" + kind, command(actual), packet)
            rows.append(
                {
                    **result,
                    "task": task,
                    "kind": kind,
                    "job": job,
                    "runtime_unchanged": runtime_hash(local_runtime) == before,
                    "inputs_unchanged": all((packet / "workspace" / p).read_bytes() == data
                                            for p, data in input_files.items()),
                    "projection_sha256": projection.launch_surface_sha256,
                }
            )
    required = (
        "private_read_denied",
        "runtime-write-denied",
        "outside-write-denied",
        "candidate_write_allowed",
        "runtime_imports",
        "network_positive_control",
        "network_denied",
    )
    report = {
        "schema_version": 1,
        "observed_at": datetime.now(UTC).isoformat(),
        "source_sha256": sha(Path(__file__).read_bytes()),
        "owner_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=owner,
                                       capture_output=True, text=True, check=True).stdout.strip(),
        "owner_source_sha256": OWNER_HASHES,
        "codex_version": version,
        "codex_raw_sha256": sha(codex.read_bytes()),
        "provider_policy_sha256": policy.source_sha256,
        "runtime_tree_sha256": seed_hash,
        "effects": effects,
        "cases": rows,
        "attempt_count": counter,
        "live_model_calls": 0,
        "trusted_fixture_path_passed": controls_pass(rows) and all(effects[k] for k in required),
        "live_scoring_admitted": False,
        "limitations": [
            "Trusted historical fixtures only; no worker candidate accepted.",
            "Fresh runtime/policy qualification and terminal worker evidence "
            "required per live lane.",
            "Only this macOS runtime and policy were exercised; other hosts are unqualified.",
        ],
    }
    write(root / "scoring-qualification.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--autowork-source", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    result = qualify(args.autowork_source, args.runtime, args.destination)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["trusted_fixture_path_passed"] else 1)

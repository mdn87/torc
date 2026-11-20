"""Replay the frozen Tableforge browser controls under the Autowork Linux owner."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from torc.canonical import payload_sha256

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = "tableforge-settlement-renderer"
PRIOR = ROOT / "docs/evidence/2026-11-20-continuation-scorer-preparation.json"
TESTS = (
    "two seats and the public board play the opening through the real pages",
    "the alternate package swaps the BE edge for AC "
    "and the page offers only what the package defines",
    "a wrong token is refused on the page and a display token cannot take a seat",
)


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def browser_verdict(report, exit_code, test_source):
    """Count behavior failures only when Playwright identifies a frozen test assertion."""
    assertions = {
        n
        for n, line in enumerate(test_source.splitlines(), 1)
        if re.match(r"\s*(?:await\s+)?expect\(", line)
    }
    specs = [spec for suite in report["suites"] for spec in suite.get("specs", [])]
    require(
        not report["errors"]
        and len(report["suites"]) == 1
        and not report["suites"][0].get("suites")
        and len(specs) == 3
        and {s["title"] for s in specs} == set(TESTS),
        "expected the three frozen tests with no runner errors",
    )
    outcomes = {}
    for spec in specs:
        require(
            spec["file"] == "settlement.spec.ts" and len(spec["tests"]) == 1,
            "wrong test file or project count",
        )
        test = spec["tests"][0]
        require(
            test["projectName"] == "chromium"
            and test["expectedStatus"] == "passed"
            and len(test["results"]) == 1,
            "wrong browser or repeated test",
        )
        result = test["results"][0]
        require(
            result["retry"] == 0 and result["status"] in ("passed", "failed"), "test did not finish"
        )
        if result["status"] == "failed":
            require(
                result["errors"]
                and all(
                    e.get("location", {}).get("file") == "/work/tests/browser/settlement.spec.ts"
                    and e["location"].get("line") in assertions
                    and re.match(
                        r"(?:Error: )?expect\(", re.sub(r"\x1b\[[0-9;]*m", "", e.get("message", ""))
                    )
                    for e in result["errors"]
                ),
                "failure did not identify an assertion in the frozen game test",
            )
        else:
            require(not result["errors"], "passing test has errors")
        outcomes[spec["title"]] = result["status"]
    failed = "failed" in outcomes.values()
    require(exit_code == int(failed), "runner exit disagrees with the test outcomes")
    return {"status": "behavior_failed" if failed else "accepted", "tests": outcomes}


def run_job(launcher, runtime, packet, output, evidence, command, timeout):
    output.mkdir()
    evidence.mkdir()
    record = evidence / "owner.json"
    run_id = uuid4().hex
    attempt = launcher(
        runtime, packet, output, owner_path=record, run_id=run_id, command=command, timeout=timeout
    )
    for name in ("stdout", "stderr"):
        (evidence / name).write_bytes(getattr(attempt, name).encode())
    owner = attempt.owner_evidence()
    receipt = {
        "run_id": run_id,
        "exit": attempt.exit_code,
        "timed_out": attempt.timed_out,
        "interrupted": attempt.interrupted,
        "owner": owner,
        "owner_record_sha256": digest(record),
        "stdout_sha256": digest(evidence / "stdout"),
        "stderr_sha256": digest(evidence / "stderr"),
    }
    save(evidence / "terminal.json", receipt)
    require(
        owner["identity_verified"]
        and owner["completed"]
        and not attempt.timed_out
        and not attempt.interrupted,
        f"incomplete owned job {run_id}",
    )
    return receipt


def prove_boundary(launcher, runtime, scratch, evidence, external):
    packet = scratch / "probe"
    packet.mkdir()
    (packet / "witness").write_text("inside")
    shutil.copyfile(HERE / "settlement_network_check.py", packet / "check.py")
    private = evidence / "outside-witness"
    private.write_text("outside")
    require(private.read_text() == "outside", "outside file witness unavailable")
    with socket.socket() as host:
        host.bind(("", 0))
        host.listen(2)
        port = host.getsockname()[1]
        for address in ("127.0.0.1", external):
            with socket.create_connection((address, port), timeout=2) as client:
                with host.accept()[0] as peer:
                    peer.sendall(b"outside")
                    require(client.recv(7) == b"outside", "outside listener witness unavailable")
        receipt = run_job(
            launcher,
            runtime,
            packet,
            scratch / "probe-out",
            evidence / "probe",
            ("/usr/bin/python3", "-I", "/work/check.py", str(private), external, str(port)),
            20,
        )
    require(receipt["exit"] == 0, "boundary probe failed to run")
    checks = read(evidence / "probe/stdout")
    require(
        checks["read_own_file"]
        and checks["same_job_connection"]
        and checks["interfaces"] == ["lo"]
        and not checks["ipv4_default_routes"]
        and checks["private_file_open"] in ("ENOENT", "EACCES")
        and checks["runtime_open_for_writing"] == checks["input_open_for_writing"] == "EROFS"
        and checks["host_loopback_connect"] == "ECONNREFUSED"
        and checks["external_witness_connect"] in ("ENETUNREACH", "EHOSTUNREACH"),
        "browser isolation controls did not all pass",
    )
    return {"observed": checks, "outside_witnesses_reachable_before_job": True, "terminal": receipt}


def dependency_dirs(deps):
    return [
        deps / "node_modules",
        *sorted(deps.glob("apps/*/node_modules")),
        *sorted(deps.glob("packages/*/node_modules")),
    ]


def dependency_hash(deps):
    files = {}
    for directory in dependency_dirs(deps):
        for path in directory.rglob("*"):
            name = path.relative_to(deps).as_posix()
            if path.is_symlink():
                link = os.readlink(path)
                require(
                    not os.path.isabs(link) and path.resolve(strict=True).is_relative_to(deps),
                    f"external dependency link {name}",
                )
                files[name] = {"link": link}
            elif path.is_file():
                files[name] = digest(path)
    return payload_sha256(files)


def install_oracle(source, target, expected):
    # These are the same scorer-only paths committed in the previous preparation.
    names = [
        "tests/browser/host-fixture.ts",
        "tests/browser/playwright.config.ts",
        "tests/browser/settlement.spec.ts",
        "packages/renderer-region-graph/test/layout.test.ts",
    ]
    require(
        payload_sha256({name: digest(source / name) for name in names}) == expected,
        "oracle bytes changed",
    )
    for name in names:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)


def copy_build_outputs(built, packet, packages):
    hashes = {}
    for package in packages:
        src = built / package / "dist"
        require(src.resolve() == src, "build output points outside its directory")
        if not src.is_dir():
            continue
        for path in src.rglob("*"):
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                continue
            require(stat.S_ISREG(mode), "unexpected file type in build output")
            name = path.relative_to(built)
            target = packet / name
            target.parent.mkdir(exist_ok=True, parents=True)
            require(not target.exists(), "build output shadows a frozen input")
            shutil.copyfile(path, target)
            hashes[name.as_posix()] = digest(target)
    require(hashes, "no built game files")
    return payload_sha256(hashes)


def replay(launcher, args, shared, prep, expected, control, dep_hash, normalizations):
    # Only the opaque candidate ID enters the job. Scorer-only files arrive after the build.
    tag = control["candidate"]["tag"]
    require(re.fullmatch("[0-9a-f]{8}", tag), "invalid candidate ID")
    saved = args.controls / tag
    pins = read(saved / "candidate/files.json")
    require(
        set(pins) == set(prep["editable_files"])
        and payload_sha256(pins) == expected["files_sha256"] == control["candidate"]["sha256"],
        "candidate manifest changed",
    )
    area, evidence = args.scratch / tag, args.evidence / tag
    area.mkdir()
    evidence.mkdir()
    packet = area / "packet"
    shutil.copytree(shared, packet)
    for name, pin in pins.items():
        target = packet / name
        if pin is None:
            require(not target.exists(), "unexpected file in the interrupted control")
        else:
            source = saved / "candidate" / name
            require(digest(source) == pin, "candidate file changed")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for item in normalizations:
        target = packet / item["path"]
        require(digest(target) == item["before"], "asset does not match normalization input")
        target.write_bytes(target.read_bytes().replace(b"\r\n", b"\n"))
        require(digest(target) == item["after"], "asset normalization changed")
    for directory in dependency_dirs(args.dependencies):
        shutil.copytree(directory, packet / directory.relative_to(args.dependencies), symlinks=True)
    require(dependency_hash(packet) == dep_hash, "transferred dependencies differ")
    build = run_job(
        launcher,
        args.runtime,
        packet,
        area / "build",
        evidence / "build",
        ("/bin/sh", "-ec", "cp -a /work /out/game; cd /out/game; exec pnpm -r build"),
        180,
    )
    require(build["exit"] == 0, f"game build failed for {tag}")
    packages = [
        p.parent.relative_to(args.dependencies)
        for pattern in ("apps/*/package.json", "packages/*/package.json")
        for p in args.dependencies.glob(pattern)
    ]
    built_hash = copy_build_outputs(area / "build/game", packet, packages)
    install_oracle(saved / "w", packet, control["oracle_sha256"])
    (packet / "bench/runs").symlink_to("/out", target_is_directory=True)
    cli = "/work/node_modules/@playwright/test/cli.js"
    behavior = run_job(
        launcher,
        args.runtime,
        packet,
        area / "browser",
        evidence / "browser",
        (
            "/usr/bin/node",
            cli,
            "test",
            "--config",
            "tests/browser/playwright.config.ts",
            "--reporter=json",
            "settlement.spec.ts",
        ),
        240,
    )
    verdict = browser_verdict(
        read(evidence / "browser/stdout"),
        behavior["exit"],
        (packet / "tests/browser/settlement.spec.ts").read_text(),
    )
    for name, pin in pins.items():
        target = packet / name
        require(
            (digest(target) if target.is_file() else None) == pin,
            "candidate bytes changed during scoring",
        )
    result = {
        "candidate_sha256": payload_sha256(pins),
        "build_outputs_sha256": built_hash,
        "dependencies_sha256": dep_hash,
        "oracle_sha256": control["oracle_sha256"],
        "build": build,
        "browser": behavior,
        **verdict,
    }
    save(evidence / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "owner",
        "runtime",
        "dependencies",
        "prepared",
        "controls",
        "normalizations",
        "scratch",
        "evidence",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--outside-witness-address", required=True, help="A non-loopback IPv4 address on this host"
    )
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    external = ipaddress.IPv4Address(args.outside_witness_address)
    require(
        not external.is_loopback and not external.is_unspecified, "provide an external host witness"
    )
    sys.path.insert(0, str(args.owner / "src"))
    from autowork.campaign import private_browser_job

    owner_module = Path(private_browser_job.__file__).resolve()
    require(
        owner_module == args.owner / "src/autowork/campaign/private_browser_job.py",
        "wrong execution owner",
    )
    git = ["git", "-C", args.owner]
    revision = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
    prefix = subprocess.check_output([*git, "rev-parse", "--show-prefix"], text=True).strip()
    owner_files = {}
    for name in (
        "private_browser_job.py",
        "owned_subprocess.py",
        "route_supervisor.py",
        "process_owner.py",
    ):
        source = owner_module.parent / name
        key = source.relative_to(args.owner).as_posix()
        committed = subprocess.check_output([*git, "show", f"{revision}:{prefix}{key}"])
        require(source.read_bytes() == committed, "owner source differs from its recorded commit")
        owner_files[key] = digest(source)
    args.scratch.mkdir()
    args.evidence.mkdir()
    effective = prove_boundary(
        private_browser_job.run_private_browser_job,
        args.runtime,
        args.scratch,
        args.evidence,
        str(external),
    )
    prior = read(PRIOR)
    case = next(row for row in prior["cases"] if row["case"] == CASE)
    prep = read(args.prepared / "preparation.json")
    shared = args.prepared / "shared"
    require(
        payload_sha256(
            {p.relative_to(shared).as_posix(): digest(p) for p in shared.rglob("*") if p.is_file()}
        )
        == prep["shared_files_sha256"]
        == case["shared_workspace_sha256"],
        "source tree changed",
    )
    controls = read(args.controls / "controls.json")
    require(
        controls["case"] == CASE and controls["preparation"] == payload_sha256(prep),
        "wrong preparation",
    )
    normalizations = read(args.normalizations)
    deps = {
        p: digest(args.dependencies / p)
        for p in ("pnpm-lock.yaml", "apps/terminal/package.json", "apps/table-display/package.json")
    }
    deps["asset_normalization"] = payload_sha256(normalizations)
    require(
        payload_sha256(deps) == case["native_dependency_inputs_sha256"],
        "frozen dependency inputs changed",
    )
    dep_hash = dependency_hash(args.dependencies)
    results = {}
    for role, control in sorted(
        controls["controls"].items(), key=lambda c: c[1]["candidate"]["tag"]
    ):
        require(
            control["oracle_sha256"] == case["native_oracle_files_sha256"]
            and control["dependencies"] == deps,
            "control uses different tests or dependencies",
        )
        results[role] = replay(
            private_browser_job.run_private_browser_job,
            args,
            shared,
            prep,
            case["historical_controls"][role],
            control,
            dep_hash,
            normalizations,
        )
    require(
        results["reference"]["status"] == "accepted"
        and results["interrupted"]["status"] == "behavior_failed",
        "controls did not distinguish the frozen pair",
    )
    require(
        prior["isolated_control_pairs"] == 7 and prior["historical_control_pairs"] == 8,
        "unexpected earlier control set",
    )
    runtime_files = [
        args.runtime / "usr/bin/node",
        args.runtime / "tools/pnpm/package/bin/pnpm.cjs",
        *sorted((args.runtime / "ms-playwright").rglob("chrome-headless-shell")),
    ]
    require(len(runtime_files) == 3, "unable to identify the pinned Chromium executable")
    save(
        args.evidence / "qualification.json",
        {
            "version": 1,
            "case": CASE,
            "prior_evidence_sha256": digest(PRIOR),
            "source_sha256": case["shared_workspace_sha256"],
            "preparation_sha256": prior["preparation_receipt_sha256"],
            "controls": results,
            "isolation": effective,
            "isolated_control_pairs": 8,
            "benchmark_admissions": 0,
            "experimental_model_calls": 0,
            "human_reviews_of_real_cases": 0,
            "experimental_spend_usd": 0,
            "runtime": {p.relative_to(args.runtime).as_posix(): digest(p) for p in runtime_files},
            "bubblewrap_sha256": digest(Path("/usr/bin/bwrap")),
            "owner_sources_sha256": owner_files,
            "owner_commit": revision,
            "qualification_program_sha256": digest(Path(__file__)),
            "boundary_probe_sha256": digest(HERE / "settlement_network_check.py"),
        },
    )


if __name__ == "__main__":
    main()

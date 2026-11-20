"""Prepare the pinned Linux Chromium runtime and lockfile dependencies outside scoring jobs."""

import argparse
import base64
import hashlib
import io
import json
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path

IMAGE = (
    "mcr.microsoft.com/playwright@sha256:"
    "ee15712262f017b8157421b212b12099146645f44b1bc5c0514cbbe6a229b1d0"
)
PNPM = "10.33.0"
PNPM_SHA512 = (
    "EFaLtKavtYyes2MNqQzJUWQXq+vT+rvmc58K55VyjaFJHp21pUTHatjrdXD1xLs9bGN7LLQb/c20f6gjyGSTGQ=="
)
REFERENCE = "da6e935f3bf06ed58d047967357e21637f51c843"
LOCK = "9c16df49309f1809f8724d23354f23a5889f36aa94494a268374a9c5f4789a54"
PARTS = (
    "bin",
    "sbin",
    "lib",
    "lib64",
    "usr",
    "etc/fonts",
    "etc/ld.so.cache",
    "etc/passwd",
    "etc/group",
    "etc/nsswitch.conf",
    "ms-playwright/chromium_headless_shell-1248",
    "ms-playwright/ffmpeg-1013",
)


def prepare(destination, tableforge, node):
    destination.mkdir()
    root = destination / "root"
    root.mkdir()
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--workdir",
        "/",
        "--entrypoint",
        "/bin/tar",
        IMAGE,
        "-cf",
        "-",
        *PARTS,
    ]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as image:
        unpack = subprocess.run(
            ["tar", "--no-same-owner", "-xf", "-", "-C", root], stdin=image.stdout
        )
        image.stdout.close()
        if image.wait() or unpack.returncode:
            raise RuntimeError("could not unpack the pinned browser image")
    for name in ("work", "out", "tmp", "dev", "proc", "tools/pnpm"):
        (root / name).mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(
        f"https://registry.npmjs.org/pnpm/-/pnpm-{PNPM}.tgz", timeout=90
    ) as response:
        archive = response.read()
    if hashlib.sha512(archive).digest() != base64.b64decode(PNPM_SHA512):
        raise ValueError("pnpm archive differs from the frozen release")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        package.extractall(root / "tools/pnpm", filter="data")
    manager = Path("/tools/pnpm/package/bin/pnpm.cjs")
    (root / "usr/local/bin/pnpm").symlink_to(manager)

    # The network-enabled installer receives only the trusted manifests. The candidate
    # source and the scorer-only tests enter later, inside separate offline jobs.
    deps = destination / "dependencies"
    git = ["git", "-C", tableforge]
    listing = subprocess.check_output([*git, "ls-tree", "-r", "--name-only", REFERENCE], text=True)
    for name in listing.splitlines():
        if name in ("package.json", "pnpm-workspace.yaml", "pnpm-lock.yaml") or (
            name.startswith(("packages/", "apps/"))
            and name.count("/") == 2
            and name.endswith("/package.json")
        ):
            path = deps / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.check_output([*git, "show", f"{REFERENCE}:{name}"]))
    if hashlib.sha256((deps / "pnpm-lock.yaml").read_bytes()).hexdigest() != LOCK:
        raise ValueError("lockfile changed")
    home = destination / "setup-home"
    home.mkdir()
    subprocess.run(
        [
            node,
            root / manager.relative_to("/"),
            "install",
            "--frozen-lockfile",
            "--ignore-scripts",
            "--store-dir",
            destination / "pnpm-store",
        ],
        cwd=deps,
        check=True,
        env={"PATH": f"{node.parent}:{os.defpath}", "HOME": str(home), "CI": "1"},
    )
    (destination / "runtime-inputs.json").write_text(
        json.dumps(
            {
                "image": IMAGE,
                "extracted": PARTS,
                "pnpm_integrity": "sha512-" + PNPM_SHA512,
                "pnpm_version": PNPM,
                "lock_sha256": LOCK,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--tableforge", type=Path, required=True)
    parser.add_argument("--node", type=Path, required=True, help="Linux Node 22 or later for setup")
    args = parser.parse_args()
    prepare(args.destination.resolve(), args.tableforge.resolve(), args.node.resolve(strict=True))

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .demo import inspect_lineage, run_demo
from .errors import TorcError
from .store import Store
from .verify import verify_store
from .vocabulary import HANDOFF_REASON_CODES

_REQUIRED_PATHS = (
    "README.md",
    "AGENTS.md",
    "docs/project-brief.md",
    "docs/architecture.md",
    "docs/domain-model.md",
    "docs/vertical-slice.md",
    "docs/integration-boundaries.md",
    "docs/prompts/CODEX_BOOTSTRAP_PROMPT.md",
    "schemas/lineage-revision.schema.json",
    "schemas/execution-projection.schema.json",
    "schemas/fit-decision.schema.json",
    "schemas/handoff-snapshot.schema.json",
    "schemas/handoff-result.schema.json",
)


def _find_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "docs").is_dir():
            return candidate
    return None


def _doctor_payload() -> dict[str, object]:
    root = _find_repo_root()
    missing: list[str] = []
    if root is None:
        missing = list(_REQUIRED_PATHS)
    else:
        missing = [path for path in _REQUIRED_PATHS if not (root / path).exists()]

    return {
        "project": "torc",
        "version": __version__,
        "status": "p0_ready" if not missing else "incomplete",
        "implementation_status": "p0_lineage_handoff_implemented",
        "repository_root": str(root) if root is not None else None,
        "missing_required_paths": missing,
        "handoff_reason_codes": list(HANDOFF_REASON_CODES),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="torc",
        description="TORC lineage and continuity control plane.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    about = subparsers.add_parser("about", help="Print TORC's architectural purpose.")
    about.add_argument("--json", action="store_true", dest="as_json")

    doctor = subparsers.add_parser("doctor", help="Verify the repository and P0 surface.")
    doctor.add_argument("--json", action="store_true", dest="as_json")

    demo = subparsers.add_parser("demo", help="Run the deterministic P0 handoff.")
    demo.add_argument("--state-dir", type=Path, required=True)
    demo.add_argument("--json", action="store_true", dest="as_json")

    inspect = subparsers.add_parser("inspect", help="Inspect a lineage without mutation.")
    inspect.add_argument("--state-dir", type=Path, required=True)
    inspect.add_argument("--lineage", required=True)
    inspect.add_argument("--json", action="store_true", dest="as_json")

    verify = subparsers.add_parser("verify", help="Verify stored TORC provenance.")
    verify.add_argument("--state-dir", type=Path, required=True)
    verify.add_argument("--lineage")
    verify.add_argument("--json", action="store_true", dest="as_json")

    return parser


def _run_about(as_json: bool) -> int:
    payload = {
        "project": "TORC Plane",
        "purpose": "Lineage and continuity control plane for Lugos agents.",
        "principle": "The agent is the governed lineage, not the transient activation.",
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["project"])
        print(payload["purpose"])
        print(payload["principle"])
    return 0


def _run_doctor(as_json: bool) -> int:
    payload = _doctor_payload()
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"TORC status: {payload['status']}")
        print(f"Implementation: {payload['implementation_status']}")
        missing = payload["missing_required_paths"]
        if missing:
            print("Missing required paths:")
            for path in missing:
                print(f"  - {path}")
    return 0 if not payload["missing_required_paths"] else 1


def _print_payload(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "about":
        return _run_about(args.as_json)
    if args.command == "doctor":
        return _run_doctor(args.as_json)
    try:
        if args.command == "demo":
            payload = run_demo(args.state_dir)
            _print_payload(payload, args.as_json)
            return 0 if payload["verification"]["valid"] else 1
        if args.command == "inspect":
            with Store(args.state_dir) as store:
                payload = inspect_lineage(store, args.lineage)
            _print_payload(payload, args.as_json)
            return 0 if payload["integrity"]["valid"] else 1
        if args.command == "verify":
            with Store(args.state_dir) as store:
                payload = verify_store(store, args.lineage)
            _print_payload(payload, args.as_json)
            return 0 if payload["valid"] else 1
    except (TorcError, OSError, ValueError) as exc:
        payload = {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        _print_payload(payload, getattr(args, "as_json", False))
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

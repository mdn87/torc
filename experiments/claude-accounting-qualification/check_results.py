"""Recheck both development exports offline. Invocation never starts a provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from torc.claude_continuation_evidence import FIELDS, owner_metrics

# The two development.py task strings at the revision used for admission.
PROMPTS = {
    "single": "de8494b182746616c861b0736b5cb13a0a8aa7645bdb4d8927543fd59768ce80",
    "multi": "053b42eefda4b0aeafe0890299e6675403260b992e27220bb951ec5486954b20",
}


def read(path):
    return json.loads(path.read_bytes())


def assess(root, prices):
    cases = {}
    for label in ("single", "multi"):
        folder = root / label
        cases[label] = (read(folder / "usage.json"), read(folder / "summary.json"))
    calls = [c for owner, _ in cases.values() for c in owner["calls"]]
    models = sorted({r["model"] for c in calls for r in c["requests"] if r["model"]})
    versions = sorted({c["version"] for c in calls})
    launches = sorted({c["launch_sha256"] for c in calls})
    aux = sorted({m for c in calls for m in c["aggregate_only_models"]})
    problems = []
    if len(models) != 1 or not models[0].startswith("claude-opus-"):
        problems.append("The observed main requests do not identify a single Opus model.")
    if len(versions) != 1 or len(launches) != 1:
        problems.append("The development assignments do not identify a single client build.")
    policy = {
        "client_version": versions[0] if len(versions) == 1 else "unresolved",
        "launch_sha256": launches[0] if len(launches) == 1 else "unresolved",
        "main_model": models[0] if len(models) == 1 else "unresolved",
        "auxiliary_models": aux,
        "cache_sharing_scope": "unknown",
        "prices": prices,
    }
    report = {}
    for label, (owner, outcome) in cases.items():
        starts = owner["calls"]
        expected = f"torc-development-{label}"
        spec = {"trial_id": expected, "prompt_sha256": PROMPTS[label]}
        metrics = owner_metrics(owner, spec, policy)
        counts = [len(c["requests"]) for c in starts]
        if [c["role"] for c in starts] != ["worker", "checker"]:
            problems.append(f"The {label} assignment did not record both roles.")
        if (
            not counts
            or (label == "single" and counts[0] != 1)
            or (label == "multi" and counts[0] < 2)
        ):
            problems.append(f"The {label} worker did not demonstrate the specified request count.")
        if metrics["total_context_tokens"] is None or metrics["first_request_input"] is None:
            problems.append(f"The {label} assignment has incomplete token coverage.")
        if outcome["owner_status"] != "completed" or outcome["behavior_verified"] is not True:
            problems.append(f"The {label} assignment did not demonstrate the requested behavior.")
        rows = []
        for call in starts:
            requests = [
                {
                    "request_sha256": hashlib.sha256(r["id"].encode()).hexdigest(),
                    "model": r["model"],
                    "usage": r["usage"],
                }
                for r in call["requests"]
            ]
            rows.append(
                {
                    "role": call["role"],
                    "status": call["status"],
                    "first_request_input": call["first_request_input"],
                    "total_context_tokens": call["total_context_tokens"],
                    "issues": call["issues"],
                    "requests": requests,
                    "observed": {k: sum(r["usage"].get(k, 0) for r in requests) for k in FIELDS}
                    if requests
                    else None,
                    "terminal": call["terminal"],
                    "aggregate_only_models": call["aggregate_only_models"],
                    "diagnostics": call["diagnostics"],
                    "evidence_sha256": call["evidence_sha256"],
                    "raw_output_sha256": call["raw_output_sha256"],
                }
            )
        report[label] = {
            "outcome": outcome,
            "owner_issues": owner["issues"],
            "usage_sha256": hashlib.sha256((root / label / "usage.json").read_bytes()).hexdigest(),
            "calls": rows,
            **{k: v for k, v in metrics.items() if k != "calls"},
        }
    return {
        "qualified": not problems,
        "problems": problems,
        "observed_policy": policy,
        "development_assignments": len(cases),
        "cli_starts": len(calls),
        "benchmark_admissions": 0,
        "cases": report,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("prices", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(assess(args.root, read(args.prices)), indent=2, allow_nan=False)
    sys.stdout.buffer.write((rendered + "\n").encode("utf-8"))

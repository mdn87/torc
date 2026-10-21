"""Prepare and analyze offline pilot drafts. No model execution or live admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

from replay import HERE, P5, replay

from torc.canonical import canonical_json, payload_sha256
from torc.continuation_analysis import analyze
from torc.continuation_trials import file_ref, prepare_manifest
from torc.harness_capture.persist import publish


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def asset(root, data):
    """Create-once exact context bytes, without the JSON publisher's newline."""
    directory = root / "assets"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = directory / hashlib.sha256(data).hexdigest()
    try:
        with path.open("xb") as stream:
            path.chmod(0o600)
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError("existing asset hash mismatch") from None
    return file_ref(root, path.relative_to(root).as_posix())


def demo(output):
    """Synthetic arithmetic only; the two workload IDs repeat one P5 fixture."""
    bridge = replay(output)
    bridge_path = publish(output, "bridge-report", bridge)
    bundle = load(output / bridge["artifacts"]["capsule-bundle"])
    capsule = asset(output, canonical_json(bundle["capsule"]).encode())
    histories = [asset(output, p.read_bytes()) for p in sorted(P5.glob("state-*.json"))]
    prompt = asset(output, canonical_json({"compiler": "full-history-demo-v0",
                   "history": [load(output / r["path"]) for r in histories]}).encode())
    common = asset(output, b"Synthetic offline mechanics; no worker executes this task. "
                   b"All arms have identical history access, tools (none) and recovery report.")
    sampling = asset(output, b"Two duplicated P5 fixture IDs, two repetitions. "
                     b"These are NOT independent workload samples or model measurements. "
                     b"Confidence values demonstrate arithmetic only; stop after all eight rows.")
    scoring = asset(output, b"Synthetic scoring receipt contract: bind trial and candidate hashes; "
                    b"retain false completion, duplicate effects and authority violations. "
                    b"A live scorer needs hidden tests and a separately qualified "
                    b"blinded procedure.")
    plan = {
        "cohort_id": "continuation-offline-comparison-demo-v0", "experiment": "A",
        "purpose": "pilot", "seed": 37, "repetitions": 2,
        "arms": ["compiled_prompt", "torc_capsule"],
        "lane": {"provider": None, "model": None, "effort": None,
                 "harness_version": None, "billing_mode": "subscription",
                 "qualification_ref": None},
        "resources": {"authorization_ref": None, "max_arm_runs": 8,
                      "max_total_seconds": 4800, "max_api_usd": 0},
        "telemetry": {"exporter_version": "fixture-v1", "semantics_ref": None,
                      "proxy_compatible": False},
        "instructions_ref": common, "execution_contract_ref": common,
        "sampling_plan_ref": sampling,
        "workloads": [
            {"workload_id": f"duplicated-mechanical-fixture-{n}", "stratum": "cold",
             "evidence_class": "calibration", "history_refs": histories,
             "workspace_refs": [histories[-1]],
             "report_ref": file_ref(output, bridge["artifacts"]["reconciliation"]),
             "scoring_refs": [scoring],
             "contexts": {"compiled_prompt": prompt, "torc_capsule": capsule},
             "capsule_verification_ref": file_ref(output,
                                                   bridge_path.relative_to(output).as_posix())}
            for n in range(2)],
    }
    plan_path = publish(output, "trial-plan", plan)
    manifest = prepare_manifest(plan, output)
    manifest_path = publish(output, "trial-manifest", manifest)
    base = load(HERE / "fixtures/offline-usage.json")["cases"][0]
    results = []
    for row in manifest["schedule"]:
        task = deepcopy(base)
        task.update(task_id=row["trial_id"], arm=row["arm"])
        candidate = payload_sha256({"synthetic_candidate": row["trial_id"]})
        results.append({
            "manifest_id": manifest["manifest_id"], "trial_id": row["trial_id"],
            "candidate_sha256": candidate, "accounting_input": task,
            "score": {"trial_id": row["trial_id"], "candidate_sha256": candidate,
                      "source": "independent_scorer", "blinded": True,
                      "evidence_ref": "synthetic-receipt-not-an-actual-scorer-run",
                      "verified_success": True, "critical_failures": []},
            "metrics": {"elapsed_seconds": None, "repeated_investigation_count": None,
                        "operator_seconds": None},
        })
    cases = {"complete_synthetic": results, "missing_trial": results[:-1]}
    missing_usage = deepcopy(results)
    for observation in missing_usage[0]["accounting_input"]["usage_groups"][0]["observations"]:
        observation["usage"].pop("output_tokens", None)
    cases["missing_usage"] = missing_usage
    false_completion = deepcopy(results)
    false_completion[0]["score"]["verified_success"] = False
    cases["false_completion"] = false_completion
    summaries = {}
    for name, rows in cases.items():
        inputs = publish(output, "trial-results", {"results": rows})
        report = analyze(manifest, rows, output, expected_manifest_id=manifest["manifest_id"])
        path = publish(output, "trial-analysis", report)
        summaries[name] = {key: report[key] for key in (
            "trial_count", "attempt_count", "known_attempt_count", "fallback_attempt_count",
            "critical_failure_count", "missing_trial_ids", "criteria_met", "adoption_authorized",
            "comparisons")}
        summaries[name].update(results=inputs.relative_to(output).as_posix(),
                               analysis=path.relative_to(output).as_posix())
    return {
        "schema_version": "torc.offline_comparison_demo.v0", "live_model_trials": 0,
        "evidence_kind": "duplicated_synthetic_mechanics_only", "baseline_commit": "9d96039",
        "manifest_id": manifest["manifest_id"], "state": manifest["state"],
        "launch_authorized": False, "readiness_blockers": manifest["readiness_blockers"],
        "plan": plan_path.relative_to(output).as_posix(),
        "manifest": manifest_path.relative_to(output).as_posix(), "cases": summaries,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "conclusion": "Effectiveness and token savings remain unmeasured. No live calls occurred.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    example = subparsers.add_parser("demo", help="synthetic replay; no model calls")
    example.add_argument("--output-dir", required=True, type=Path)
    prepare = subparsers.add_parser("prepare", help="pin an offline pilot draft")
    prepare.add_argument("--plan", required=True, type=Path)
    prepare.add_argument("--asset-root", required=True, type=Path)
    prepare.add_argument("--output-dir", required=True, type=Path)
    analysis = subparsers.add_parser("analyze", help="analyze supplied offline evidence")
    analysis.add_argument("--manifest", required=True, type=Path)
    analysis.add_argument("--expected-manifest-id", required=True)
    analysis.add_argument("--results", required=True, type=Path,
                          help="JSON object with a results list")
    analysis.add_argument("--asset-root", required=True, type=Path)
    analysis.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "demo":
        result = demo(args.output_dir)
    elif args.command == "prepare":
        result = prepare_manifest(load(args.plan), args.asset_root)
        publish(args.output_dir, "trial-manifest", result)
    else:
        result = analyze(load(args.manifest), load(args.results)["results"], args.asset_root,
                         expected_manifest_id=args.expected_manifest_id)
        publish(args.output_dir, "trial-analysis", result)
    sys.stdout.buffer.write((json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
                             + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()

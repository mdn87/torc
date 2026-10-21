"""Summarize an externally pinned private owner archive without executing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from torc.continuation_evidence import import_responses
from torc.continuation_observations import collect_observations


def summarize(path, expected_sha256):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("owner archive differs from external pin")
    private = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive members")
        hashes = json.loads(archive.read("sha256.json"))
        if set(hashes) != set(names) - {"sha256.json"}:
            raise ValueError("archive inventory differs")
        for name, digest in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("archive member hash mismatch")

        def read(name):
            return json.loads(archive.read(name))

        manifest = read("inputs/manifest.json")
        launch = read("inputs/launch-intent.json")
        sequence = ["seed-" + row["workload_id"] for row in launch["seed_intents"]]
        sequence += [row["trial_id"] for row in manifest["schedule"]]
        records, attempts, totals, seeds, trials = [], [], {}, [], []
        admission_threads = {}
        for step in sequence:
            result_path = f"steps/{step}.result.json"
            if result_path not in hashes:
                continue
            result = read(result_path)
            admission_id = result["admission_id"]
            prefix = f"runs/{admission_id}/"
            owners = [
                name
                for name in names
                if name.startswith(prefix + "owner-attempts/") and name.endswith(".result.json")
            ]
            if len(owners) != 1:
                raise ValueError("worker owner result absent or ambiguous")
            owner = read(owners[0])
            if (
                owner["status"] != "completed"
                or not owner["execution"]["capture_complete"]
                or not owner["execution"]["tree_absent"]
            ):
                raise ValueError("worker termination or capture incomplete")
            attempt = owner["attempt_id"]
            attempts.append(attempt)
            events = [
                event
                for event in owner["usage"]["native_events"]
                if event.get("type") == "turn.completed"
            ]
            if len(events) != 1:
                raise ValueError("completion counter absent or ambiguous")
            total = events[0]["usage"]
            invocation = read(f"invocations/{admission_id}.result.json")
            source = invocation["execution"]["source_admission_id"]
            baseline = totals[source] if source else {key: 0 for key in total}
            totals[admission_id] = total
            threads = owner["usage"]["observed_thread_ids"]
            if len(threads) != 1:
                raise ValueError("native thread binding ambiguous")
            binding_valid = source is None or threads[0] != admission_threads[source]
            if not binding_valid:
                raise ValueError("fork did not establish a distinct native thread")
            admission_threads[admission_id] = threads[0]
            records.append(
                {
                    "response_id": attempt + ":turn.completed:0",
                    "attempt_id": attempt,
                    "identity_kind": "owner_completion_event_not_provider_response",
                    "counter_epoch": threads[0],
                    "cumulative_usage": total,
                    "baseline_usage": baseline,
                    "baseline_evidence_ref": f"archive:{source or admission_id}:owned-session",
                    "evidence_ref": "archive:sha256:" + hashes[owners[0]],
                }
            )
            summary = {
                "step": step,
                "admission_id": admission_id,
                "owner_attempt_id": attempt,
                "status": result["status"],
                "elapsed_seconds": result["elapsed_seconds"],
                "worker_seconds": owner["execution"]["duration_seconds"],
                "terminal_capture_complete": True,
                "process_tree_absent": True,
                "native_binding_valid": binding_valid,
                "owner_result_sha256": hashes[owners[0]],
                "paid_api_used": result["paid_api_used"],
            }
            if step.startswith("seed-"):
                summary["workload_id"] = step.removeprefix("seed-")
                seeds.append(summary)
                continue
            row = next(row for row in manifest["schedule"] if row["trial_id"] == step)
            summary.update(arm=row["arm"], workload_id=row["workload_id"])
            original_score = f"scores/{step}/result.json"
            corrected_score = f"scores/{step}-corrected/result.json"
            score_path = corrected_score if corrected_score in hashes else original_score
            summary["protocol_deviation"] = corrected_score in hashes
            summary["acceptance_passed"] = False
            summary["scored"] = score_path in hashes
            summary["observations"] = None
            if score_path in hashes:
                score = read(score_path)
                summary.update(
                    acceptance_passed=score["verified_success"],
                    scorer_exit_code=score["exit_code"],
                    scorer_result_sha256=hashes[score_path],
                    candidate_sha256=score["candidate_sha256"],
                    failed_test_ids=[
                        line.split(" - ")[0].removeprefix("FAILED ")
                        for line in score["stdout"].splitlines()
                        if line.startswith("FAILED ")
                    ],
                )
                trace_events, invalid = [], 0
                stdout_path = prefix + "child-output/attempt-001.stdout.txt"
                for line_number, line in enumerate(archive.read(stdout_path).splitlines()):
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        invalid += 1
                        continue
                    item = event.get("item", {})
                    if event.get("type") != "item.completed" or item.get("type") not in {
                        "command_execution",
                        "file_change",
                    }:
                        continue
                    exit_code = item.get("exit_code")
                    trace_events.append(
                        {
                            "sequence": line_number,
                            "relative_seconds": None,
                            "action_kind": "edit" if item["type"] == "file_change" else "other",
                            "result_status": (
                                "unknown"
                                if exit_code is None
                                else "success"
                                if exit_code == 0
                                else "failure"
                            ),
                            "action": item,
                            "evidence_ref": f"{stdout_path}:{line_number + 1}",
                        }
                    )
                start = read(f"steps/{step}.start.json")["monotonic_start"]
                trace = {
                    "trial_id": step,
                    "attempt_id": attempt,
                    "candidate_sha256": score["candidate_sha256"],
                    "workspace_sha256": score["candidate_sha256"],
                    "complete": False,  # No complete operator-intervention trace exists.
                    "process_tree_absent": True,
                    "owner_receipt_ref": owners[0],
                    "events": trace_events,
                    "intervals": [
                        {
                            "phase": "attempt",
                            "start_monotonic": start,
                            "end_monotonic": start + result["elapsed_seconds"],
                            "clock_id": "operator-controller",
                        }
                    ],
                    "interventions": [{"reason": "scorer command correction; no model retry"}]
                    if corrected_score in hashes
                    else [],
                }
                packet, provenance = collect_observations(trace, opaque_id="trial-" + step[:12])
                summary["observations"] = packet
                summary["malformed_trace_lines"] = invalid
                private[step] = provenance
            else:
                summary["unscored_reason"] = result["status"]
            resolution_path = f"resolutions/{step}.json"
            if resolution_path in hashes:
                summary["retained_failure_resolution_sha256"] = hashes[resolution_path]
                summary["protocol_deviation"] = True
            trials.append(summary)
        accounting = import_responses(records, owned_attempt_ids=attempts)
        for row in seeds + trials:
            observation = next(
                item
                for item in accounting["responses"]
                if item["attempt_id"] == row["owner_attempt_id"]
            )
            row["observed_incremental_usage"] = observation["incremental_usage"]
            row["inherited_usage"] = observation["normalized_baseline_usage"]
        public = {
            "schema_version": 1,
            "cohort_id": manifest["plan"]["cohort_id"],
            "manifest_id": manifest["manifest_id"],
            "archive_sha256": expected_sha256,
            "verified_members": len(hashes),
            "planned_invocations": 8,
            "admitted_invocations": len(attempts),
            "max_invocations": read("limit-amendment.json")["max_invocations"],
            "planned_comparisons": 6,
            "completed_comparisons": len(trials),
            "accepted_comparisons": sum(row["acceptance_passed"] for row in trials),
            "seed_preparation": seeds,
            "trials": trials,
            "observed_whole_pilot_incremental_usage": accounting["observed_incremental_sums"],
            "provider_coverage_complete": None,
            "actual_api_cost": None,
            "paid_api_used": any(row["paid_api_used"] for row in seeds + trials),
            "whole_task_savings_available": False,
            "adoption_supported": False,
            "limitations": [
                "Two historical tasks and one run per arm do not support a general quality claim.",
                "Counters are owner completion observations, not an inventory "
                "of provider responses.",
                "Hidden retries and failed-request usage remain unknown; "
                "input/cache fields may overlap.",
                "Seed expense is separate and included once in the observed whole-pilot totals.",
                "Elapsed intervals exclude time between trials and the first model-free rescore.",
                "Malformed trace lines are retained privately; event timestamps "
                "and complete intervention capture are unavailable.",
                "Repeated-investigation rates and operator active time remain unknown.",
                "The first scorer command and subsequent terminal scope disposition "
                "were amended; original outcomes remain retained.",
            ],
        }
    return public, private


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--private-provenance", type=Path, required=True)
    args = parser.parse_args()
    report, private = summarize(args.archive, args.sha256)
    with args.private_provenance.open("x", encoding="utf-8") as stream:
        json.dump(private, stream, sort_keys=True, indent=2)
    sys.stdout.buffer.write((json.dumps(report, sort_keys=True, indent=2) + "\n").encode())

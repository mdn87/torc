"""Import hash-verified retained owner completion counters, never native state."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from torc.continuation_evidence import import_responses

ARCHIVE_SHA256 = "f0ba4d8ea36f3e63336c90ec833053f81508b56248f194b71024f1dcbb88031a"


def import_archive(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("qualification archive differs from its external pin")
    with zipfile.ZipFile(path) as archive:
        entries = archive.namelist()
        if len(entries) != len(set(entries)):
            raise ValueError("duplicate archive entries")
        hashes = json.loads(archive.read("sha256.json"))
        if set(hashes) != set(entries) - {"sha256.json"}:
            raise ValueError("archive inventory differs")
        for name, digest in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("archive member hash mismatch")
        report = json.loads(archive.read("report.json"))
        records, totals, attempts = [], {}, []
        for row in report["canary_results"]:
            admission_id = row["admission_id"]
            attempt_id = row["owner_attempt_id"]
            admission = json.loads(archive.read(f"invocations/{admission_id}.result.json"))
            owner_path = f"runs/{admission_id}/owner-attempts/{attempt_id}.result.json"
            owner = json.loads(archive.read(owner_path))
            if (owner["status"] != "completed"
                    or owner["execution"].get("tree_absent") is not True
                    or owner["execution"].get("capture_complete") is not True):
                raise ValueError("owner completion evidence is incomplete")
            events = [event for event in owner["usage"]["native_events"]
                      if event.get("type") == "turn.completed"]
            if len(events) != 1:
                raise ValueError("retained completion counter is absent or ambiguous")
            total = events[0]["usage"]
            source = admission["execution"]["source_admission_id"]
            if source is None:
                baseline = {key: 0 for key in total}
                baseline_ref = f"archive:{admission_id}:owned-new-session"
            else:
                if source not in totals:
                    raise ValueError("source baseline was not retained before continuation")
                baseline = totals[source]
                baseline_ref = f"archive:{source}:turn.completed"
            totals[admission_id] = total
            attempts.append(attempt_id)
            records.append({
                "response_id": attempt_id + ":turn.completed:0",
                "identity_kind": "owner_completion_event_not_provider_response",
                "attempt_id": attempt_id, "counter_epoch": row["thread_id"],
                "evidence_ref": f"archive:{owner_path}#{hashes[owner_path]}",
                "cumulative_usage": total, "baseline_usage": baseline,
                "baseline_evidence_ref": baseline_ref,
            })
    accounting = import_responses(records, owned_attempt_ids=attempts)
    fork = accounting["responses"][1]
    proof = {"inherited_input": fork["normalized_baseline_usage"]["input_tokens"],
             "new_input": fork["incremental_usage"]["input_tokens"],
             "thread_input": fork["normalized_cumulative_usage"]["input_tokens"]}
    if proof != {"inherited_input": 9240, "new_input": 10329, "thread_input": 19569}:
        raise ValueError("retained fork arithmetic differs from qualification")
    return {
        "schema_version": 1, "archive_sha256": ARCHIVE_SHA256,
        "verified_members": len(hashes), "live_model_calls": 0,
        "imported_observation_kind": "owner completion counters; not individual provider responses",
        "qualification_report_unique_successful_response_records": 7,
        "fork_proof": proof, "accounting": accounting,
        "whole_task_savings_available": False,
        "limitations": ["Six completions do not enumerate the seven provider response records.",
                        "Provider-internal failed requests and retries remain unknown.",
                        "The archive pin authenticates no live execution authority."],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    sys.stdout.buffer.write((json.dumps(import_archive(args.archive), indent=2, sort_keys=True)
                            + "\n").encode())

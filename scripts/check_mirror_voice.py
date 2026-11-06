"""Replay exported TORC deliveries through the real lugos-voice pure consumer.

The caller explicitly supplies the local adapter module. This never plays audio.
Run after `torc mirror experiment`; stdout is a machine-readable result.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from datetime import datetime
from pathlib import Path

NODE_SCRIPT = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { selectTorcResponse } = await import(pathToFileURL(process.argv[1]).href);
const cases = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(cases.map(c => selectTorcResponse(c.contract, c.context))));
"""


def milliseconds(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1000


def check(experiment_dir: Path, adapter: Path):
    root = experiment_dir.resolve()
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    cases = []
    for turn in report["turns"]:
        path = (root / turn["delivery_file"]).resolve()
        path.relative_to(root)
        contract = json.loads(path.read_text(encoding="utf-8"))
        context = {
            "enabled": True, "sessionId": turn["binding"]["conversation_id"],
            "responseId": turn["response_id"], "responseText": contract["written"],
            "now": milliseconds(turn["now"]),
        }
        cases.append({"name": f"{turn['name']}:accepted", "contract": contract,
                      "context": context, "expected": "accepted"})
        for mutation in ("expired", "session", "source", "omission", "rewrite", "absent", "off"):
            changed, environment = copy.deepcopy(contract), dict(context)
            expected = "invalid"
            if mutation == "expired":
                environment["now"] = milliseconds(contract["expires_at"])
                expected = "expired"
            elif mutation == "session":
                environment["sessionId"] = "another-session"
                expected = "binding_mismatch"
            elif mutation == "source":
                environment["responseId"] = "superseding-response"
                expected = "binding_mismatch"
            elif mutation == "omission":
                required = next(f["id"] for f in changed["result"]["facts"]
                                if f["kind"] == "verification")
                changed["speech"]["fact_ids"].remove(required)
            elif mutation == "rewrite":
                changed["speech"]["segments"] = ["Everything is finished and verified."]
            elif mutation == "absent":
                changed, expected = None, "absent"
            else:
                environment["enabled"], expected = False, "off"
            cases.append({"name": f"{turn['name']}:{mutation}", "contract": changed,
                          "context": environment, "expected": expected})
    process = subprocess.run(
        ["node", "--input-type=module", "-e", NODE_SCRIPT, str(adapter.resolve())],
        input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8", timeout=30,
        check=True,
    )
    results = json.loads(process.stdout)
    checks = []
    for case, result in zip(cases, results, strict=True):
        passed = result["disposition"] == case["expected"]
        if case["expected"] == "accepted":
            expected_speech = " ".join(" ".join(case["contract"]["speech"]["segments"]).split())
            passed = passed and result["speech"] == expected_speech
        else:
            passed = passed and result["speech"] is None
        checks.append({"case": case["name"], "passed": passed,
                       "disposition": result["disposition"]})
    return {"ok": bool(checks) and all(c["passed"] for c in checks), "checks": checks,
            "accepted": sum(c["disposition"] == "accepted" for c in checks),
            "audio_played": False, "native_model_called": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.experiment_dir, args.adapter)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Freeze the 32-assignment run order and measured settings before any admission.

The seed is recorded in the schedule. Everything else is derived from it, the
published scorer preparation and the qualified accounting policy, so the
schedule can be rebuilt byte for byte from those three inputs.
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

from .canonical import payload_sha256
from .claude_continuation_analysis import ARMS, VERSION
from .claude_continuation_evidence import PREPARATION, _load

EXECUTION = {
    "profile": "claude-measured-continuation",
    "billing_mode": "subscription",
    "shared_deadline_seconds": 600,
    "max_starts": {"worker": 1, "checker": 1},
    "continuations": 0,
    "replacements": 0,
    "paid_ceiling_usd": 2,
}


def _draw(seed, *parts):
    return int(payload_sha256({"order_seed": seed, "draw": list(parts)}), 16)


def freeze_schedule(preparation, qualification, order_seed):
    """Seeded first arm per task, reversed for repetition two; task order drawn per repetition."""
    if payload_sha256(preparation) != PREPARATION:
        raise ValueError("Preparation differs from the published scorer receipt")
    if (
        qualification.get("qualified") is not True
        or qualification.get("problems")
        or qualification.get("benchmark_admissions") != 0
    ):
        raise ValueError("Accounting is not qualified, or a benchmark admission already exists")
    if not isinstance(order_seed, str) or not order_seed.strip():
        raise ValueError("The order seed must be a nonempty string")
    cases = {c["case"]: c["prompt_sha256"] for c in preparation["cases"]}
    if len(cases) != 8 or any(set(p) != set(ARMS) for p in cases.values()):
        raise ValueError("Expected eight cases with one prompt per arm")
    first = {case: ARMS[_draw(order_seed, "first", case) % 2] for case in cases}
    trials = []
    for repetition in (1, 2):
        for case in sorted(cases, key=lambda c: _draw(order_seed, "order", repetition, c)):
            lead = first[case] if repetition == 1 else next(a for a in ARMS if a != first[case])
            for position, arm in enumerate((lead, *(a for a in ARMS if a != lead)), 1):
                trials.append(
                    {
                        "sequence": len(trials) + 1,
                        "trial_id": f"torc-continuation-r{repetition}-{case}-{arm}",
                        "case": case,
                        "arm": arm,
                        "repetition": repetition,
                        "position": position,
                        "prompt_sha256": cases[case][arm],
                    }
                )
    return {
        "contract": VERSION,
        "order_seed": order_seed,
        "preparation_sha256": PREPARATION,
        "accounting_qualification_sha256": payload_sha256(qualification),
        "policy": qualification["observed_policy"],
        "execution": EXECUTION,
        "trials": trials,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preparation", type=Path)
    parser.add_argument("qualification", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--order-seed", help="Rebuild a recorded schedule; omit to draw one")
    args = parser.parse_args()
    seed = args.order_seed or secrets.token_hex(16)
    schedule = freeze_schedule(
        _load(args.preparation.read_bytes()), _load(args.qualification.read_bytes()), seed
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(schedule, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(payload_sha256(schedule))


if __name__ == "__main__":
    main()

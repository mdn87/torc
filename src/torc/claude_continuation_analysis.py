"""Offline paired analysis of the two-repetition Claude continuation study."""

from __future__ import annotations

import math
from collections import defaultdict
from fractions import Fraction
from statistics import median

VERSION = "torc.claude_continuation_analysis.v1"
ARMS = ("compiled", "torc")


def sum_known(values):
    values = list(values)
    return sum(values) if values and None not in values else None


def _sum_observed(values):
    known = [x for x in values if x is not None]
    return sum(known) if known else None


def _sign_test(reductions):
    positive = sum(x > 0 for x in reductions)
    negative = sum(x < 0 for x in reductions)
    n = positive + negative
    tail = sum(math.comb(n, k) for k in range(min(positive, negative) + 1))
    return dict(
        positive=positive,
        negative=negative,
        ties=len(reductions) - n,
        p_two_sided=min(1.0, 2 * tail / 2**n),
    )


def _group(rows):
    cases = defaultdict(dict)
    seen = set()
    for row in rows:
        case, arm, rep = (row[k] for k in ("case", "arm", "repetition"))
        key = arm, rep
        if (
            arm not in ARMS
            or type(rep) is not int
            or rep not in (1, 2)
            or type(row["position"]) is not int
            or row["position"] not in (1, 2)
            or key in cases[case]
            or row["trial_id"] in seen
        ):
            raise ValueError("Invalid or duplicated trial in paired schedule")
        seen.add(row["trial_id"])
        cases[case][key] = row
    if len(cases) != 8 or any(len(group) != 4 for group in cases.values()):
        raise ValueError("Expected eight tasks with both arms in both repetitions")
    for group in cases.values():
        if group["torc", 1]["position"] == group["torc", 2]["position"] or any(
            group["compiled", r]["position"] == group["torc", r]["position"] for r in (1, 2)
        ):
            raise ValueError("Paired order must reverse in repetition two")
    return cases


def paired_report(rows):
    groups = _group(rows)
    results, reductions = [], []
    strata = defaultdict(lambda: {arm: [] for arm in ARMS})
    quality_ok = True
    for case, group in groups.items():
        usage, lower, first, passes = {}, {}, {}, {}
        for arm in ARMS:
            runs = [group[arm, r] for r in (1, 2)]
            usage[arm] = sum_known(run["total_context_tokens"] for run in runs)
            lower[arm] = _sum_observed(run["observed_input_lower_bound"] for run in runs)
            first[arm] = sum_known(run["first_request_input"] for run in runs)
            passes[arm] = sum(run["verified_success"] is True for run in runs)
        for r in (1, 2):
            outcomes = {True: "pass", False: "fail", None: "unscored"}
            pair = "/".join(outcomes[group[arm, r]["verified_success"]] for arm in ARMS)
            for arm in ARMS:
                strata[pair][arm].append(group[arm, r]["total_context_tokens"])
        ratio = None
        if None not in usage.values() and usage["compiled"] > 0:
            ratio = 1 - Fraction(usage["torc"], usage["compiled"])
            reductions.append(ratio)
        quality_ok &= passes["torc"] >= passes["compiled"]
        results.append(
            {
                "case": case,
                "usage": usage,
                "observed_input_lower_bounds": lower,
                "first_request_input": first,
                "passes_out_of_two": passes,
                "first_request_difference_torc_minus_compiled": first["torc"] - first["compiled"]
                if None not in first.values()
                else None,
                "reduction": float(ratio) if ratio is not None else None,
            }
        )
    acceptance = {}
    for arm in ARMS:
        scores = [row["verified_success"] for row in rows if row["arm"] == arm]
        acceptance[arm] = dict(passed=scores.count(True), scheduled=16, unscored=scores.count(None))
    unresolved = len(groups) - len(reductions)
    middle = median(reductions) if not unresolved else None
    sign = _sign_test(reductions) if not unresolved else None
    unscored = any(a["unscored"] for a in acceptance.values())
    critical = [r["trial_id"] for r in rows if r["critical_failures"]]
    if not unscored and not any(a["passed"] for a in acceptance.values()):
        decision = "failed_feasibility"
    elif unresolved:
        decision = "incomplete_usage"
    elif any(row["deviations"] for row in rows):
        decision = "protocol_deviation"
    elif unscored:
        decision = "incomplete_scoring"
    elif quality_ok and not critical and middle >= Fraction(1, 5) and sign["p_two_sided"] < 0.05:
        decision = "consider_confirmation"
    else:
        decision = "no_advance"
    return {
        "contract": VERSION,
        "endpoint": "total_context_tokens",
        "decision": decision,
        "unresolved_tasks": unresolved,
        "by_task": results,
        "acceptance": acceptance,
        "critical_failure_trials": critical,
        "median_reduction": float(middle) if middle is not None else None,
        "sign_test": sign,
        "descriptive_range": [float(min(reductions)), float(max(reductions))]
        if not unresolved
        else None,
        "usage_by_paired_score_compiled_then_torc": {
            key: {
                arm: {"runs": len(values), "total_context_tokens": sum_known(values)}
                for arm, values in by_arm.items()
            }
            for key, by_arm in strata.items()
        },
        "trials_by_order_and_repetition": rows,
    }

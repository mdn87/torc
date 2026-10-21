"""Offline, all-trial analysis with paired workload uncertainty.

Scores and telemetry are supplied evidence, not independently discovered here.
The exact marginal binomial bounds plus a union bound give a conservative bound
on paired gains minus losses. Workloads must be independent representative
samples for population inference; repeated executions do not supply more units.
"""

from __future__ import annotations

import math
from copy import deepcopy
from statistics import median

from .canonical import payload_sha256
from .continuation_trials import _digest, verify_manifest
from .continuation_usage import account_task

VERSION = "torc.continuation_analysis.v0"
METRICS = ("elapsed_seconds", "repeated_investigation_count", "operator_seconds")


def _binomial_cdf(k, n, probability):
    if probability <= 0:
        return 1.0
    if probability >= 1:
        return float(k == n)
    terms = [math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                      + i * math.log(probability) + (n - i) * math.log1p(-probability))
             for i in range(k + 1)]
    return min(1.0, math.fsum(terms))


def _upper(k, n, tail):
    if k == n:
        return 1.0
    if k == 0:
        return 1 - tail ** (1 / n)
    low, high = 0.0, 1.0
    for _ in range(60):
        mid = (low + high) / 2
        if _binomial_cdf(k, n, mid) > tail:
            low = mid
        else:
            high = mid
    return high


def success_difference_lower_bound(gains, losses, n, alpha):
    """One-sided (1-alpha) conservative lower bound for P(gain)-P(loss)."""
    if (any(type(v) is not int or v < 0 for v in (gains, losses, n))
            or gains + losses > n or not 0 < alpha < 1):
        raise ValueError("invalid paired binomial counts or alpha")
    if n == 0:
        return -1.0
    lower_gain = 0.0 if gains == 0 else 1 - _upper(n - gains, n, alpha / 2)
    return lower_gain - _upper(losses, n, alpha / 2)


def _median_interval(values, alpha):
    """Distribution-free order-statistic interval; null ends mean unbounded."""
    values = sorted(values)
    n = len(values)
    rank = 0
    for k in range(1, n // 2 + 1):
        if 2 * _binomial_cdf(k - 1, n, 0.5) <= alpha:
            rank = k
    if not rank:
        return {"lower": None, "upper": None, "reason": "too_few_independent_workloads"}
    return {"lower": values[rank - 1], "upper": values[n - rank], "reason": None}


def _read_result(raw, scheduled, manifest_id):
    if raw.get("manifest_id") != manifest_id:
        raise ValueError("result manifest binding mismatch")
    candidate = raw.get("candidate_sha256")
    if candidate is not None:
        _digest(candidate)
    task = raw.get("accounting_input")
    accounting = None if task is None else account_task(task)
    if accounting is not None and (accounting["task_id"] != scheduled["trial_id"]
                                   or accounting["arm"] != scheduled["arm"]):
        raise ValueError("accounting task/arm binding mismatch")
    score = raw.get("score")
    critical = []
    if score is not None:
        if (score.get("trial_id") != scheduled["trial_id"]
                or score.get("candidate_sha256") != candidate
                or score.get("source") != "independent_scorer"
                or score.get("blinded") is not True
                or not isinstance(score.get("evidence_ref"), str)
                or not score["evidence_ref"].strip()
                or type(score.get("verified_success")) is not bool
                or not isinstance(score.get("critical_failures"), list)
                or any(not isinstance(s, str) or not s.strip()
                       for s in score["critical_failures"])
                or (score["verified_success"] and candidate is None)):
            raise ValueError("invalid independent score or candidate binding")
        critical = list(score["critical_failures"])
        if (accounting is not None and accounting["outcome"] == "verified_completion"
                and not score["verified_success"]):
            critical.append("false_verified_completion")
    metrics = raw.get("metrics", {})
    for field in METRICS:
        value = metrics.get(field)
        if value is not None and (type(value) not in (int, float)
                                  or not math.isfinite(value) or value < 0):
            raise ValueError(f"invalid metric: {field}")
    repeated = metrics.get("repeated_investigation_count")
    if repeated is not None and type(repeated) is not int:
        raise ValueError("repeated_investigation_count must be an integer")
    # Only whole-trial setup exclusions remove a primary pair. A failed setup
    # followed by an actual execution still counts, including its fallback.
    excluded = (accounting is not None
                and accounting["excluded_attempt_count"] == accounting["attempt_count"])
    return {**scheduled, "candidate_sha256": candidate, "accounting": accounting,
            "score": deepcopy(score), "critical_failures": sorted(set(critical)),
            "setup_excluded": excluded,
            "metrics": {field: metrics.get(field) for field in METRICS}}


def _success(row):
    return None if row is None or row["score"] is None else row["score"]["verified_success"]


def _proxy(row):
    return (None if row is None or row["accounting"] is None or row["setup_excluded"]
            else row["accounting"]["uncached_processed_token_proxy"])


def _comparison(manifest, indexed, stratum, baseline, alpha):
    workloads = [w for w in manifest["plan"]["workloads"] if w["stratum"] == stratum]
    selected = [r for r in manifest["schedule"]
                if r["stratum"] == stratum and r["arm"] in {baseline, "torc_capsule"}]
    lookup = {(r["workload_id"], r["arm"], r["repetition"]): indexed.get(r["trial_id"])
              for r in selected}
    pairs = [(lookup[w["workload_id"], "torc_capsule", 0],
              lookup[w["workload_id"], baseline, 0]) for w in workloads]
    usage_complete = all(_proxy(indexed.get(r["trial_id"])) is not None for r in selected)
    scores_complete = all(_success(indexed.get(r["trial_id"])) is not None
                          and not indexed[r["trial_id"]]["setup_excluded"] for r in selected)
    savings, gains, losses, complete_scores = [], 0, 0, 0
    sensitivity_low, sensitivity_high = 0, 0
    metric_differences = {field: [] for field in METRICS}
    for torc, other in pairs:
        a, b = _proxy(torc), _proxy(other)
        if a is not None and b is not None and b > 0:
            savings.append(1 - a / b)
        sa, sb = _success(torc), _success(other)
        if ((torc is not None and torc["setup_excluded"])
                or (other is not None and other["setup_excluded"])):
            sa, sb = None, None
        sensitivity_low += (0 if sa is None else int(sa)) - (1 if sb is None else int(sb))
        sensitivity_high += (1 if sa is None else int(sa)) - (0 if sb is None else int(sb))
        if sa is not None and sb is not None:
            complete_scores += 1
            gains += int(sa and not sb)
            losses += int(sb and not sa)
        for field in METRICS:
            va = None if torc is None else torc["metrics"][field]
            vb = None if other is None else other["metrics"][field]
            if va is not None and vb is not None:
                metric_differences[field].append(va - vb)
    n = len(workloads)
    lower = (success_difference_lower_bound(gains, losses, n, alpha)
             if scores_complete else None)
    success_passed = lower is not None and lower > -manifest["analysis_contract"]["success_margin"]
    endpoint = median(savings) if usage_complete and len(savings) == n else None
    metrics = {field: {"complete_primary_pairs": len(values),
                       "median_torc_minus_baseline": median(values) if len(values) == n else None}
               for field, values in metric_differences.items()}
    return {
        "stratum": stratum, "baseline": baseline, "primary_workload_pairs": n,
        "complete_primary_score_pairs": complete_scores,
        "complete_primary_cost_pairs": len(savings),
        "scheduled_arm_runs": len(selected), "alpha": alpha,
        "median_savings_fraction": endpoint,
        "savings_unavailable_reason": None if endpoint is not None else
            "missing_or_excluded_trial_usage_or_nonpositive_baseline",
        "complete_pair_median_diagnostic": median(savings) if savings else None,
        "median_savings_interval": _median_interval(savings, alpha) if endpoint is not None else
            {"lower": None, "upper": None, "reason": "incomplete_endpoint"},
        "success_gains": gains, "success_losses": losses,
        "success_difference": (gains - losses) / n if scores_complete else None,
        "success_difference_lower_bound": lower,
        "success_noninferiority_passed": success_passed,
        "success_point_sensitivity": {"worst": sensitivity_low / n, "best": sensitivity_high / n},
        "savings_target_met": endpoint is not None and endpoint >= 0.20,
        "primary_metric_differences": metrics,
    }


def analyze(manifest, results, root, *, expected_manifest_id):
    """Retain every supplied result and account for every scheduled missing row."""
    verify_manifest(manifest, root, expected_manifest_id=expected_manifest_id)
    schedule = {r["trial_id"]: r for r in manifest["schedule"]}
    indexed = {}
    for raw in results:
        identity = raw["trial_id"]
        if identity in indexed:
            raise ValueError("duplicate trial result")
        if identity not in schedule:
            raise ValueError("unknown trial result")
        indexed[identity] = _read_result(raw, schedule[identity], expected_manifest_id)
    missing = sorted(set(schedule) - set(indexed))
    baselines = sorted(set(manifest["plan"]["arms"]) - {"torc_capsule"})
    strata = sorted({w["stratum"] for w in manifest["plan"]["workloads"]})
    alpha = manifest["analysis_contract"]["familywise_alpha"] / (len(baselines) * len(strata))
    comparisons = [_comparison(manifest, indexed, stratum, baseline, alpha)
                   for stratum in strata for baseline in baselines]
    rows = [indexed[r["trial_id"]] for r in manifest["schedule"] if r["trial_id"] in indexed]
    accounted = [r["accounting"] for r in rows if r["accounting"] is not None]
    incomplete_accounting = bool(missing) or len(accounted) != len(rows)
    counts = {}
    for field in ("attempt_count", "failed_attempt_count", "fallback_attempt_count",
                  "excluded_attempt_count", "request_count"):
        known = sum(a[field] for a in accounted)
        counts[field] = None if incomplete_accounting else known
        counts["known_" + field] = known
    return {
        "schema_version": VERSION, "manifest_id": expected_manifest_id,
        "results_sha256": payload_sha256(results), "results": deepcopy(results),
        "interpretation": "offline_arithmetic_only; not live effectiveness evidence",
        "scheduled_trial_count": len(schedule), "trial_count": len(rows), **counts,
        "missing_trial_ids": missing,
        "missing_accounting_trial_ids": [r["trial_id"] for r in rows if r["accounting"] is None],
        "missing_score_trial_ids": [r["trial_id"] for r in rows if r["score"] is None],
        "critical_failure_count": sum(len(r["critical_failures"]) for r in rows),
        "critical_failure_trial_ids": [r["trial_id"] for r in rows if r["critical_failures"]],
        "setup_excluded_trial_ids": [r["trial_id"] for r in rows if r["setup_excluded"]],
        "comparisons": comparisons, "trials": rows,
        "criteria_met": False, "adoption_authorized": False,
        "adoption_blockers": list(manifest["readiness_blockers"]) + [
            "pilot drafts do not authorize adoption",
            "realistic representative workloads and full safe-baseline qualification required",
        ],
        "limitations": [
            "Receipt binding does not authenticate scorer independence or telemetry completeness.",
            "Confidence bounds assume independent representative workloads, not repeated runs.",
            "Missing usage has no finite worst-case savings bound; complete pairs are diagnostic.",
            "API costs are unavailable; this version analyzes the subscription token proxy only.",
        ],
    }

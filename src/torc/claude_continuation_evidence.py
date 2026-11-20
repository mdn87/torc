"""Read hash-bound Claude owner exports and independent scores for paired analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from .canonical import payload_sha256
from .claude_continuation_analysis import ARMS, VERSION, paired_report, sum_known

PREPARATION = "9e919604161de8f027ffdacee3345c64e22351b47be275683fcf12734e102c99"
OWNER = "autowork.claude_subscription_usage.v1"
FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
MODEL_FIELDS = ("inputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "outputTokens")
TTL = ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens")


def _integer(value):
    return type(value) is int and value >= 0


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Expected a SHA-256 digest")
    return value


def _load(raw):
    def unique(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate JSON field")
        return result

    return json.loads(raw, object_pairs_hook=unique)


def _artifact(root, ref):
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Evidence reference leaves its directory")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _sha(ref["sha256"]):
        raise ValueError("Evidence bytes differ from the artifact reference")
    return _load(raw)


def _price(model, usage, prices, *, aggregate_only=False):
    """Dollars at dated per-million token rates. Tiered aggregate-only usage is unpriceable."""
    tiers = prices["models"].get(model, [])
    if not tiers or (aggregate_only and len(tiers) != 1):
        return None, None
    tokens = sum(usage[k] for k in FIELDS[:3])
    tier = next((t for t in tiers if t["through"] is None or tokens <= t["through"]), None)
    if not tier:
        return None, None
    rates = [tier[k] for k in ("fresh", "write_5m", "write_1h", "read", "output")]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in rates):
        raise ValueError("Invalid dated model rate")
    output = usage["output_tokens"] * rates[4] / 1_000_000
    ttl = usage.get("cache_creation", {})
    writes = [ttl.get(k) for k in TTL]
    if usage["cache_creation_input_tokens"] == 0:
        writes = [0, 0]
    if not all(_integer(v) for v in writes) or sum(writes) != usage["cache_creation_input_tokens"]:
        return None, output
    counts = [usage["input_tokens"], *writes, usage["cache_read_input_tokens"]]
    return sum(n * rate for n, rate in zip(counts, rates[:4], strict=True)) / 1_000_000, output


def owner_metrics(owner, spec, policy):
    """The owner qualifies the event mapping. Recheck trial identity and primary totals here."""
    if owner["contract"] != OWNER:
        raise ValueError("Unsupported owner accounting contract")
    calls = owner["calls"]
    roles = [c["role"] for c in calls]
    if len(roles) > 2 or roles != ["worker", "checker"][: len(roles)]:
        raise ValueError("Owner call sequence does not match the bounded assignment")
    coverage = owner["completion"] or {}
    if coverage and coverage.get("task_sha256") != spec["prompt_sha256"]:
        raise ValueError("Completion checkpoint is bound to a different prompt")
    if any(
        c.get("correlation_id") != spec["trial_id"] or c.get("task_sha256") != spec["prompt_sha256"]
        for c in calls
    ):
        raise ValueError("Owner usage is bound to a different trial or prompt")
    if len({c["attempt_id"] for c in calls}) != len(calls) or any(
        len({c[key] for c in calls}) > 1 for key in ("run_id", "assignment_id")
    ):
        raise ValueError("Duplicate starts or mixed assignments in one owner export")
    complete = (
        owner["complete"] is True
        and calls
        and not owner["issues"]
        and coverage.get("calls") == len(calls)
        and coverage.get("status") in {"complete", "incomplete"}
        and coverage.get("reason") != "deadline"
    )
    totals = Counter()
    deviations = set()
    input_costs, output_costs, cli_costs = [], [], []
    details = []
    for call in calls:
        _sha(call["evidence_sha256"])
        term = call["terminal"]
        native = term.get("usage", {})
        if (
            call["version"] != policy["client_version"]
            or call["launch_sha256"] != policy["launch_sha256"]
        ):
            deviations.add("unexpected_client")
        all_models = term.get("modelUsage", {})
        aux = set(call["aggregate_only_models"])
        if aux - set(policy["auxiliary_models"]):
            deviations.add("unexpected_auxiliary_model")
        requests = call["requests"]
        if len({r["id"] for r in requests}) != len(requests):
            raise ValueError("Duplicate request in normalized owner export")
        call_complete = (
            not call["issues"]
            and call["status"] in {"returned", "failed"}
            and bool(requests)
            and bool(all_models)
            and all(_integer(native.get(k)) for k in FIELDS)
        )
        if call_complete:
            if any(not all(_integer(v.get(k)) for k in MODEL_FIELDS) for v in all_models.values()):
                raise ValueError("Terminal model counters are incomplete")
            if any(
                native[k] != sum(v[nk] for v in all_models.values())
                for k, nk in zip(FIELDS, MODEL_FIELDS, strict=True)
            ):
                raise ValueError("Terminal model counts disagree with invocation totals")
            if call["total_context_tokens"] != sum(native[k] for k in FIELDS[:3]):
                raise ValueError("Owner total disagrees with native input")
            totals.update({k: native[k] for k in FIELDS})
        complete = complete and call_complete
        per_model = {}
        for req in requests:
            if req["model"] != policy["main_model"]:
                deviations.add("unexpected_main_model")
            usage = req["usage"]
            if all(_integer(usage.get(k)) for k in FIELDS):
                per_model.setdefault(req["model"], Counter()).update({k: usage[k] for k in FIELDS})
                inc, out = _price(req["model"], usage, policy["prices"])
                input_costs.append(inc)
                output_costs.append(out)
            elif call_complete:
                raise ValueError("Qualified call contains incomplete request counters")
        if call_complete:
            if set(all_models) != per_model.keys() | aux or per_model.keys() & aux:
                raise ValueError("Unexplained terminal model coverage")
            for model, counted in per_model.items():
                if any(
                    counted[k] != all_models[model][nk]
                    for k, nk in zip(FIELDS, MODEL_FIELDS, strict=True)
                ):
                    raise ValueError("Normalized request counters disagree with terminal model")
            for model in aux:
                usage = dict(zip(FIELDS, (all_models[model][k] for k in MODEL_FIELDS), strict=True))
                inc, out = _price(model, usage, policy["prices"], aggregate_only=True)
                input_costs.append(inc)
                output_costs.append(out)
        cli_costs.append(term.get("total_cost_usd"))
        details.append(
            {
                "role": call["role"],
                "attempt_id": call["attempt_id"],
                "issues": call["issues"],
                "requests": requests,
                "terminal": term,
                "diag": call["diagnostics"],
                "aggregate_only_models": sorted(aux),
                "reserved_at": call["reserved_at"],
                "completed_at": call["completed_at"],
                "evidence_sha256": call["evidence_sha256"],
            }
        )
    total = sum(totals[k] for k in FIELDS[:3]) if complete else None
    if total is not None and total != owner["total_context_tokens"]:
        raise ValueError("Assignment total disagrees with its CLI starts")
    first = owner["first_request_input"]
    if complete and (
        not calls[0]["requests"]
        or first != sum(calls[0]["requests"][0]["usage"][k] for k in FIELDS[:3])
    ):
        raise ValueError("First-request input disagrees with the first worker request")
    # Prices describe the declared API-equivalent setting, separate from subscription billing.
    settings = policy["prices"]["usage_settings"]
    compatible = (
        complete
        and set(settings) == {"service_tier", "speed", "inference_geo"}
        and all(
            all(c["terminal"].get(k) in allowed for k, allowed in settings.items()) for c in calls
        )
    )
    inc = sum_known(input_costs) if compatible else None
    out = sum_known(output_costs) if compatible else None
    interval = None
    if calls and calls[-1]["completed_at"]:
        interval = (
            datetime.fromisoformat(calls[-1]["completed_at"])
            - datetime.fromisoformat(calls[0]["reserved_at"])
        ).total_seconds()
        if interval < 0:
            raise ValueError("Owner completion time precedes the first reservation")
    return {
        "total_context_tokens": total,
        "observed_input_lower_bound": owner["observed_input_lower_bound"]
        if any(c["requests"] for c in calls)
        else None,
        "first_request_input": first,
        "usage_categories": dict(totals) if complete else None,
        "calls": details,
        "cli_estimate_usd": sum_known(cli_costs) if complete else None,
        "estimated_input_usd": inc,
        "estimated_output_usd": out,
        "estimated_total_usd": sum_known([inc, out]),
        "cli_elapsed_seconds": sum_known(c["elapsed_seconds"] for c in calls),
        "first_start_to_last_exit_seconds": interval,
        "deviations": sorted(deviations),
    }


def analyze(schedule, preparation, results, root):
    if schedule["contract"] != VERSION or payload_sha256(preparation) != PREPARATION:
        raise ValueError("Unexpected schedule contract or preparation receipt")
    if results["schedule_sha256"] != payload_sha256(schedule):
        raise ValueError("Trial records belong to a different frozen schedule")
    policy = schedule["policy"]
    if not isinstance(schedule.get("order_seed"), str) or not schedule["order_seed"].strip():
        raise ValueError("The frozen schedule needs its recorded order seed")
    date.fromisoformat(policy["prices"]["as_of"])
    cases = {c["case"]: c for c in preparation["cases"]}
    submitted = {r["trial_id"]: r for r in results["trials"]}
    if len(submitted) != len(results["trials"]) or submitted.keys() - {
        s["trial_id"] for s in schedule["trials"]
    }:
        raise ValueError("Duplicate or unscheduled trial record")
    attempts = set()
    rows = []
    for spec in schedule["trials"]:
        case, arm = spec["case"], spec["arm"]
        if (
            case not in cases
            or arm not in ARMS
            or spec["prompt_sha256"] != cases[case]["prompt_sha256"][arm]
        ):
            raise ValueError("Scheduled prompt is absent from frozen preparation")
        row = {
            **spec,
            "total_context_tokens": None,
            "first_request_input": None,
            "observed_input_lower_bound": None,
            "verified_success": None,
            "critical_failures": [],
            "deviations": [],
        }
        record = submitted.get(spec["trial_id"], {})
        if record.get("usage") is not None:
            row.update(owner_metrics(_artifact(root, record["usage"]), spec, policy))
            for call in row["calls"]:
                if call["attempt_id"] in attempts:
                    raise ValueError("Owner start was assigned to multiple trials")
                attempts.add(call["attempt_id"])
            row["usage_sha256"] = record["usage"]["sha256"]
        if record.get("score") is not None:
            score = _artifact(root, record["score"])
            candidate = record.get("candidate_sha256")
            if candidate is not None:
                _sha(candidate)
            if (
                score["trial_id"] != spec["trial_id"]
                or score["candidate_sha256"] != candidate
                or score["oracle_sha256"] != cases[case]["native_oracle_files_sha256"]
                or type(score["verified_success"]) is not bool
                or (score["verified_success"] and candidate is None)
                or not isinstance(score["critical_failures"], list)
                or not all(isinstance(k, str) and k.strip() for k in score["critical_failures"])
            ):
                raise ValueError("Independent score differs from the scheduled candidate or oracle")
            row.update(
                verified_success=score["verified_success"],
                critical_failures=score["critical_failures"],
                score_sha256=record["score"]["sha256"],
                candidate_sha256=candidate,
            )
        rows.append(row)
    report = paired_report(rows)
    report.update(
        schedule_sha256=payload_sha256(schedule),
        preparation_sha256=PREPARATION,
        price_basis=policy["prices"],
        cache_sharing_scope=policy["cache_sharing_scope"],
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("schedule", "preparation", "results"):
        parser.add_argument(name, type=Path)
    parser.add_argument(
        "--schedule-sha256", required=True, help="Previously frozen canonical JSON digest"
    )
    args = parser.parse_args()
    schedule = _load(args.schedule.read_bytes())
    if payload_sha256(schedule) != _sha(args.schedule_sha256):
        parser.error("Schedule differs from its frozen digest")
    report = analyze(
        schedule,
        _load(args.preparation.read_bytes()),
        _load(args.results.read_bytes()),
        args.results.parent,
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

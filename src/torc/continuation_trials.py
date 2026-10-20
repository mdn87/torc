"""Offline comparison preparation. A pinned manifest grants no execution authority.

This version prepares Experiment A pilot drafts only. Live-lane qualification,
capsule verification and resource admission remain with their existing owners.
References pin evidence bytes; their presence does not validate their claims.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

from .canonical import payload_sha256

VERSION = "torc.continuation_trials.v0"
ARMS = {"compiled_prompt", "torc_capsule", "native_warm", "native_cold"}
CONTRACT = {
    "primary_endpoint": "uncached_processed_token_proxy",
    "primary_repetition": 0,
    "savings_target": 0.20,
    "success_margin": 0.05,
    "familywise_alpha": 0.05,
    "confidence_method": "paired_gain_loss_clopper_pearson_union_bound",
    "multiplicity": "all_declared_baseline_stratum_comparisons",
    "independent_unit": "workload; repetitions are descriptive only",
    "maximum_missingness": 0,
    "stopping_rule": "all scheduled trials; no outcome-dependent replacement",
    "missing_usage_sensitivity": "unbounded; no headline savings",
    "missing_success_sensitivity": "worst and best paired assignments",
    "setup_exclusion": "retain accounting-approved exclusions; no replacement",
    "adoption_authorized": False,
}


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _digest(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError("invalid SHA-256 digest")
    return value


def file_ref(root, relative_path):
    """Pin a regular file within the declared asset root, without absolute paths."""
    root = Path(root).resolve()
    relative = Path(_text(relative_path, "relative_path"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("asset path must be relative and contained in root")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("asset path must resolve to a file inside root")
    return {"path": relative.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _ref(root, value):
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError("file reference requires path and sha256")
    _digest(value["sha256"])
    if value != file_ref(root, value["path"]):
        raise ValueError(f"asset hash mismatch: {value['path']}")
    return value


def _implementation():
    root = Path(__file__).parent
    names = ("continuation_trials.py", "continuation_analysis.py", "continuation_usage.py",
             "experiment_usage.py", "canonical.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def _positive(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and positive")


def prepare_manifest(plan, root, *, require_ready=False):
    """Hash-pin a draft and seeded paired schedule; never admit a live run.

    The caller must retain the returned manifest_id independently. Editing a
    plan, implementation or asset requires a new cohort and external pin.
    """
    plan = deepcopy(plan)
    json.dumps(plan, allow_nan=False)
    _text(plan["cohort_id"], "cohort_id")
    if plan["experiment"] != "A" or plan["purpose"] != "pilot":
        raise ValueError("this preparer supports Experiment A pilot drafts only")
    arms = plan["arms"]
    if (not isinstance(arms, list) or len(set(arms)) != len(arms)
            or not {"compiled_prompt", "torc_capsule"} <= set(arms) <= ARMS):
        raise ValueError("unique arms must include compiled_prompt and torc_capsule")
    if type(plan["seed"]) is not int:
        raise ValueError("seed must be an integer")
    repetitions = plan["repetitions"]
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    resources = plan["resources"]
    if type(resources["max_arm_runs"]) is not int or resources["max_arm_runs"] < 1:
        raise ValueError("invalid arm-run budget")
    _positive(resources["max_total_seconds"], "time budget")
    if plan["lane"]["billing_mode"] != "subscription" or resources["max_api_usd"] != 0:
        raise ValueError("only subscription proxy analysis without paid fallback is supported")
    common = [_ref(root, plan[key]) for key in
              ("instructions_ref", "execution_contract_ref", "sampling_plan_ref")]
    workloads = plan["workloads"]
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("at least one workload is required")
    count = len(workloads) * repetitions * len(arms)
    if count > resources["max_arm_runs"]:
        raise ValueError("schedule exceeds arm-run budget")
    blockers = ["live admission is not implemented by this offline preparer"]
    for section, fields in (
        ("lane", ("provider", "model", "effort", "harness_version", "qualification_ref")),
        ("resources", ("authorization_ref",)),
        ("telemetry", ("exporter_version", "semantics_ref")),
    ):
        for key in fields:
            value = plan[section].get(key)
            if value is None:
                blockers.append(f"missing {section}.{key}")
            elif key.endswith("_ref"):
                _ref(root, value)
            else:
                _text(value, key)
    if type(plan["telemetry"]["proxy_compatible"]) is not bool:
        raise ValueError("proxy_compatible must be boolean")
    if not plan["telemetry"]["proxy_compatible"]:
        blockers.append("lane counter semantics not qualified")
    ids, visible, hidden, blocks = set(), list(common), [], []
    for workload in workloads:
        identity = _text(workload["workload_id"], "workload_id")
        if identity in ids:
            raise ValueError("duplicate workload ID")
        ids.add(identity)
        if workload["stratum"] not in {"cold", "warm", "interrupted"}:
            raise ValueError("unknown workload stratum")
        if workload["evidence_class"] not in {"calibration", "realistic"}:
            raise ValueError("unknown evidence class")
        if set(workload["contexts"]) != set(arms):
            raise ValueError("contexts must cover exactly the scheduled arms")
        visible += [_ref(root, value) for value in workload["contexts"].values()]
        visible.append(_ref(root, workload["report_ref"]))
        for field in ("history_refs", "workspace_refs", "scoring_refs"):
            refs = workload[field]
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"{field} must be a nonempty list")
            checked = [_ref(root, ref) for ref in refs]
            (hidden if field == "scoring_refs" else visible).extend(checked)
        receipt = workload.get("capsule_verification_ref")
        if receipt is None:
            blockers.append(f"missing capsule verification: {identity}")
        else:
            _ref(root, receipt)
        for repetition in range(repetitions):
            block = {"workload_id": identity, "stratum": workload["stratum"],
                     "repetition": repetition}
            rows = []
            for arm in arms:
                key = {"cohort_id": plan["cohort_id"], "seed": plan["seed"], **block, "arm": arm}
                rows.append({**block, "arm": arm, "trial_id": payload_sha256(key)})
            rows.sort(key=lambda row: row["trial_id"])
            order = payload_sha256({"seed": plan["seed"], **block})
            blocks.append((order, rows))
    if ({ref["sha256"] for ref in hidden} & {ref["sha256"] for ref in visible}
            or {ref["path"] for ref in hidden} & {ref["path"] for ref in visible}):
        raise ValueError("hidden scoring assets overlap worker-visible assets")
    schedule = [row for _, rows in sorted(blocks) for row in rows]
    body = {"schema_version": VERSION, "state": "draft", "launch_authorized": False,
            "readiness_blockers": blockers, "plan": plan, "analysis_contract": deepcopy(CONTRACT),
            "implementation_sha256": _implementation(), "schedule": schedule}
    if require_ready:
        raise ValueError("not ready: " + "; ".join(blockers))
    return {**body, "manifest_id": payload_sha256(body)}


def verify_manifest(manifest, root, *, expected_manifest_id):
    """Check the external pin, source implementation, schedule and every asset."""
    _digest(expected_manifest_id)
    body = {k: v for k, v in manifest.items() if k != "manifest_id"}
    if (manifest.get("manifest_id") != expected_manifest_id
            or payload_sha256(body) != expected_manifest_id):
        raise ValueError("manifest does not match its external pin")
    if manifest != prepare_manifest(manifest["plan"], root):
        raise ValueError("manifest implementation, schedule or contract changed")


def scoring_packet(manifest, trial_id, candidate_sha256):
    """Only opaque identity, candidate binding and scoring assets go to the scorer.

    The operator must isolate the scorer from the manifest and worker logs.
    This packet cannot attest that a human or process was actually blinded.
    """
    _digest(candidate_sha256)
    row = next((row for row in manifest["schedule"] if row["trial_id"] == trial_id), None)
    if row is None:
        raise ValueError("unknown trial ID")
    workload = next(w for w in manifest["plan"]["workloads"]
                    if w["workload_id"] == row["workload_id"])
    return {"trial_id": trial_id, "candidate_sha256": candidate_sha256,
            "scoring_refs": deepcopy(workload["scoring_refs"])}

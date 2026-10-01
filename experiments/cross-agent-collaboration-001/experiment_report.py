"""Summarize immutable cross-agent experiment runs without mixing tokenizers."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = EXPERIMENT_ROOT / "runs" / "smoke-001"


class ExperimentReportError(RuntimeError):
    """Raised when committed run evidence cannot be summarized safely."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentReportError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExperimentReportError(f"expected a JSON object: {path}")
    return value


def _phase_records(run_dir: Path, result: dict[str, Any] | None) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if result is not None and isinstance(result.get("phases"), list):
        for phase in result["phases"]:
            if isinstance(phase, dict) and isinstance(phase.get("record"), str):
                paths.append(run_dir / phase["record"])
    if not paths:
        paths = sorted((run_dir / "phases").glob("*/worker-run.json"))
    return [_object(path) for path in paths]


def summarize_run(run_dir: Path) -> dict[str, Any]:
    result_path = run_dir / "workflow-result.json"
    disposition_path = run_dir / "disposition.json"
    result = _object(result_path) if result_path.is_file() else None
    disposition = _object(disposition_path) if disposition_path.is_file() else None
    records = _phase_records(run_dir, result)
    if result is None and disposition is None and not records:
        raise ExperimentReportError(f"run has no evidence: {run_dir}")

    if disposition is not None:
        valid_attempt = disposition.get("valid_attempt") is True
        category = disposition.get("category")
        comparative_use = disposition.get("comparative_use")
    else:
        valid_attempt = result is not None and isinstance(
            result.get("accepted_final"), bool
        )
        category = "valid_smoke" if valid_attempt else "incomplete"
        comparative_use = "smoke_only" if valid_attempt else "excluded"

    phases: list[dict[str, Any]] = []
    for record in records:
        usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
        timing = (
            record.get("timing") if isinstance(record.get("timing"), dict) else {}
        )
        phases.append(
            {
                "provider": record.get("provider"),
                "role": record.get("role"),
                "tool_mode": record.get("tool_mode", "workspace"),
                "prompt_bytes": record.get("prompt_bytes"),
                "input_tokens": usage.get("input_tokens"),
                "cached_input_tokens": usage.get("cached_input_tokens"),
                "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "completion_ms": timing.get("completion_ms"),
            }
        )

    return {
        "run_id": run_dir.name,
        "fixture_id": result.get("fixture_id") if result else None,
        "workflow_id": result.get("workflow_id") if result else None,
        "worker_interface": (
            result.get("worker_interface", "workspace-tools-v0")
            if result
            else "workspace-tools-v0"
        ),
        "valid_attempt": valid_attempt,
        "category": category,
        "comparative_use": comparative_use,
        "accepted_final": result.get("accepted_final") if result else None,
        "phases": phases,
    }


def build_report(runs_dir: Path = DEFAULT_RUNS_DIR) -> dict[str, Any]:
    if not runs_dir.is_dir():
        raise ExperimentReportError(f"runs directory does not exist: {runs_dir}")
    runs = [
        summarize_run(path)
        for path in sorted(runs_dir.iterdir())
        if path.is_dir()
    ]
    usage: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {
            "phase_count": 0,
            "reported_input_phase_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
    )
    for run in runs:
        for phase in run["phases"]:
            provider = phase["provider"]
            if not isinstance(provider, str):
                continue
            key = (run["worker_interface"], provider)
            usage[key]["phase_count"] += 1
            if isinstance(phase["input_tokens"], int):
                usage[key]["reported_input_phase_count"] += 1
                usage[key]["input_tokens"] += phase["input_tokens"]
            if isinstance(phase["output_tokens"], int):
                usage[key]["output_tokens"] += phase["output_tokens"]

    by_interface_provider = [
        {
            "worker_interface": interface,
            "provider": provider,
            **values,
            "mean_input_tokens_per_reported_phase": (
                round(
                    values["input_tokens"] / values["reported_input_phase_count"], 3
                )
                if values["reported_input_phase_count"]
                else None
            ),
        }
        for (interface, provider), values in sorted(usage.items())
    ]
    valid_runs = [run for run in runs if run["valid_attempt"]]
    comparisons: list[dict[str, Any]] = []
    fixtures = sorted(
        {
            run["fixture_id"]
            for run in valid_runs
            if isinstance(run["fixture_id"], str)
        }
    )
    for fixture_id in fixtures:
        solo = [
            run
            for run in valid_runs
            if run["fixture_id"] == fixture_id
            and run["workflow_id"] == "codex-solo"
            and run["worker_interface"] == "patch-artifact-v1"
        ]
        reviewed = [
            run
            for run in valid_runs
            if run["fixture_id"] == fixture_id
            and run["workflow_id"] == "codex-review"
            and run["worker_interface"] == "patch-artifact-v1"
        ]
        if not solo or not reviewed:
            continue
        baseline = max(solo, key=lambda run: run["run_id"])
        candidate = max(reviewed, key=lambda run: run["run_id"])
        if {
            phase["provider"] for phase in baseline["phases"] + candidate["phases"]
        } != {"codex"}:
            continue

        def total(run: dict[str, Any], field: str) -> float | int | None:
            values = [phase[field] for phase in run["phases"]]
            if not values or not all(isinstance(value, (int, float)) for value in values):
                return None
            return sum(values)

        solo_input = total(baseline, "input_tokens")
        reviewed_input = total(candidate, "input_tokens")
        solo_time = total(baseline, "completion_ms")
        reviewed_time = total(candidate, "completion_ms")
        comparisons.append(
            {
                "fixture_id": fixture_id,
                "provider": "codex",
                "solo_run_id": baseline["run_id"],
                "reviewed_run_id": candidate["run_id"],
                "solo_accepted": baseline["accepted_final"],
                "reviewed_accepted": candidate["accepted_final"],
                "quality_delta": int(candidate["accepted_final"] is True)
                - int(baseline["accepted_final"] is True),
                "solo_phase_count": len(baseline["phases"]),
                "reviewed_phase_count": len(candidate["phases"]),
                "solo_input_tokens": solo_input,
                "reviewed_input_tokens": reviewed_input,
                "input_ratio": (
                    round(reviewed_input / solo_input, 3)
                    if isinstance(solo_input, (int, float))
                    and solo_input
                    and isinstance(reviewed_input, (int, float))
                    else None
                ),
                "solo_completion_ms": solo_time,
                "reviewed_completion_ms": reviewed_time,
                "completion_ratio": (
                    round(reviewed_time / solo_time, 3)
                    if isinstance(solo_time, (int, float))
                    and solo_time
                    and isinstance(reviewed_time, (int, float))
                    else None
                ),
            }
        )
    return {
        "schema_version": 1,
        "runs_dir": str(runs_dir.resolve()),
        "run_count": len(runs),
        "valid_run_count": len(valid_runs),
        "excluded_run_count": len(runs) - len(valid_runs),
        "accepted_valid_run_count": sum(
            run["accepted_final"] is True for run in valid_runs
        ),
        "usage_by_interface_and_provider": by_interface_provider,
        "matched_workflow_comparisons": comparisons,
        "runs": runs,
        "token_accounting_note": (
            "Token counts are aggregated only within the same provider and worker interface; "
            "no cross-provider total is computed."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    args = parser.parse_args(argv)
    try:
        print(canonical_json(build_report(args.runs_dir)))
        return 0
    except ExperimentReportError as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministically score a baseline critic replay against preregistered defects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
DEFAULT_PLAN = EXPERIMENT_ROOT / "critic-transport-series-002-plan.json"


class CriticProbeScoreError(RuntimeError):
    """Raised when replay evidence does not match the preregistered probe."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticProbeScoreError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticProbeScoreError(f"expected a JSON object: {path}")
    return value


def _candidate(plan: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        raise CriticProbeScoreError("plan candidates are invalid")
    matches = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("candidate_id") == candidate_id
    ]
    if len(matches) != 1:
        raise CriticProbeScoreError(f"candidate is not uniquely planned: {candidate_id}")
    return matches[0]


def _finding_matches_area(
    finding: dict[str, Any], area: dict[str, Any]
) -> bool:
    claims = finding.get("claim_ids")
    if not isinstance(claims, list) or not set(claims).intersection(
        area["acceptable_claim_ids"]
    ):
        return False
    summary = finding.get("summary")
    evidence = finding.get("evidence")
    if not isinstance(summary, str) or not isinstance(evidence, str):
        return False
    text = f"{summary}\n{evidence}".lower()
    return all(
        any(term.lower() in text for term in group)
        for group in area["evidence_term_groups"]
    )


def score_run(
    *,
    run_dir: Path,
    candidate_id: str,
    plan_path: Path = DEFAULT_PLAN,
) -> dict[str, Any]:
    plan = _object(plan_path)
    candidate = _candidate(plan, candidate_id)
    resolved_run = run_dir.resolve()
    result = _object(resolved_run / "workflow-result.json")
    source = _object(resolved_run / "source-primary-ref.json")
    candidate_score = _object(resolved_run / "score-candidate.json")
    critique = _object(resolved_run / "critique.json")

    expected_source = f"fixture-baseline:{candidate['fixture_id']}"
    if result.get("fixture_id") != candidate["fixture_id"]:
        raise CriticProbeScoreError("run fixture does not match the planned candidate")
    if result.get("replay_source_id") != expected_source:
        raise CriticProbeScoreError("run is not a replay of the planned fixture baseline")
    if source.get("source_kind") != "fixture_baseline" or source.get(
        "source_id"
    ) != expected_source:
        raise CriticProbeScoreError("source reference is not the planned fixture baseline")
    expected_hash = candidate["candidate_workspace_tree_sha256"]
    if source.get("workspace_tree_sha256") != expected_hash or candidate_score.get(
        "workspace_tree_sha256"
    ) != expected_hash:
        raise CriticProbeScoreError("candidate workspace hash does not match the plan")
    if candidate_score.get("accepted") is not candidate["expected_accepted"]:
        raise CriticProbeScoreError("candidate acceptance does not match the plan")
    if result.get("critic_context") not in plan["transports"]:
        raise CriticProbeScoreError("run critic transport is not planned")

    phases = result.get("phases")
    if not isinstance(phases, list) or len(phases) != 1:
        raise CriticProbeScoreError("probe run must contain exactly one critic phase")
    phase = phases[0]
    if not isinstance(phase, dict) or not isinstance(phase.get("record"), str):
        raise CriticProbeScoreError("probe critic phase reference is invalid")
    worker = _object(resolved_run / phase["record"])
    controls = plan["provider_controls"]
    if (
        worker.get("provider") != controls["provider"]
        or worker.get("model") != controls["model"]
        or worker.get("effort") != controls["effort"]
        or worker.get("tool_mode") != controls["tool_mode"]
        or worker.get("harness_version") != controls["harness_version"]
    ):
        raise CriticProbeScoreError("critic worker controls do not match the plan")

    findings = critique.get("findings")
    if critique.get("verdict") not in {"approve", "changes_requested"} or not isinstance(
        findings, list
    ):
        raise CriticProbeScoreError("critique shape is invalid")
    areas = candidate["required_defect_areas"]
    covered: list[str] = []
    matched_findings: set[str] = set()
    for area in areas:
        matches = [
            finding
            for finding in findings
            if isinstance(finding, dict) and _finding_matches_area(finding, area)
        ]
        if matches:
            covered.append(area["area_id"])
            matched_findings.update(
                finding["finding_id"]
                for finding in matches
                if isinstance(finding.get("finding_id"), str)
            )
    finding_ids = {
        finding["finding_id"]
        for finding in findings
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str)
    }
    acceptable_claim_ids = {
        claim_id
        for area in areas
        for claim_id in area["acceptable_claim_ids"]
    }
    valid_claim_citation_count = sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        for claim_id in finding.get("claim_ids", [])
        if claim_id in acceptable_claim_ids
    )
    required_count = len(areas)
    recall = round(len(covered) / required_count, 6) if required_count else None
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "candidate_id": candidate_id,
        "run_id": result.get("run_id", resolved_run.name),
        "critic_context": result["critic_context"],
        "critic_verdict": critique["verdict"],
        "changes_requested_correct": critique["verdict"] == "changes_requested",
        "required_defect_area_count": required_count,
        "covered_defect_area_count": len(covered),
        "defect_area_recall": recall,
        "covered_defect_area_ids": covered,
        "missed_defect_area_ids": [
            area["area_id"] for area in areas if area["area_id"] not in covered
        ],
        "finding_count": len(findings),
        "valid_claim_citation_count": valid_claim_citation_count,
        "unsupported_finding_count": len(finding_ids - matched_findings),
        "unsupported_finding_ids": sorted(finding_ids - matched_findings),
        "candidate_workspace_tree_sha256": expected_hash,
        "prompt_bytes": worker.get("prompt_bytes"),
        "usage": worker.get("usage"),
        "timing": worker.get("timing"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    args = parser.parse_args(argv)
    try:
        print(
            canonical_json(
                score_run(
                    run_dir=args.run_dir,
                    candidate_id=args.candidate,
                    plan_path=args.plan,
                )
            )
        )
        return 0
    except CriticProbeScoreError as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

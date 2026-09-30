"""Opt-in solo and cross-agent workflow runner for smoke series 001."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import fixture_control  # noqa: E402
import worker_runner  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402
from torc.execution_capsules import (  # noqa: E402
    compile_claim_capsule,
    resolve_claim_sources,
)

EXPERIMENT_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = EXPERIMENT_ROOT / "smoke-manifest.json"


class WorkflowRunnerError(RuntimeError):
    """Raised when a workflow cannot preserve its experimental controls."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowRunnerError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowRunnerError(f"expected a JSON object: {path}")
    return value


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _read_object(path)
    if manifest.get("schema_version") != 1:
        raise WorkflowRunnerError("workflow manifest schema version is unsupported")
    if not isinstance(manifest.get("providers"), dict) or not isinstance(
        manifest.get("workflows"), dict
    ):
        raise WorkflowRunnerError("workflow manifest is incomplete")
    return manifest


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _apparatus_revision() -> str:
    tracked_paths = [
        "experiments/cross-agent-collaboration-001",
        "src/torc/execution_capsules.py",
        "src/torc/experiment_usage.py",
    ]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *tracked_paths],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    if status:
        raise WorkflowRunnerError(
            "experiment apparatus has uncommitted changes; commit before a live run"
        )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def _run_worker(
    *,
    settings: dict[str, Any],
    workspace: Path,
    prompt: str,
    effort: str,
    role: str,
    session_mode: str,
    session_id: str | None,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    record = worker_runner.execute_worker(
        provider=settings["provider"],
        transport=settings["transport"],
        executable=settings["executable"],
        distro=settings.get("distro", "Ubuntu"),
        workspace=workspace,
        prompt=prompt,
        model=settings["model"],
        effort=effort,
        role=role,
        session_mode=session_mode,
        session_id=session_id,
        expected_harness_version=settings["harness_version"],
        timeout_seconds=timeout_seconds,
        output_dir=output_dir,
    )
    if record["timed_out"] or record["exit_status"] != 0:
        raise WorkflowRunnerError(
            f"{settings['provider']} {role} phase failed; evidence is in {output_dir}"
        )
    return record


def _provider_settings(manifest: dict[str, Any], provider: str) -> dict[str, Any]:
    settings = manifest["providers"].get(provider)
    if not isinstance(settings, dict):
        raise WorkflowRunnerError(f"provider has no frozen settings: {provider}")
    return {"provider": provider, **settings}


def _candidate_diff(workspace: Path) -> str:
    baseline = fixture_control.baseline_revision(workspace)
    return subprocess.run(
        ["git", "diff", "--no-ext-diff", "--binary", baseline],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout


def _copy_candidate(primary: Path, critic: Path) -> str:
    ignored = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc")
    shutil.copytree(primary, critic, ignore=ignored)
    candidate_diff = _candidate_diff(primary)
    (critic / "CANDIDATE.diff").write_text(candidate_diff, encoding="utf-8")
    fixture_control.initialize_git_workspace(critic)
    return candidate_diff


def _compile_handoff(
    fixture_id: str,
    run_id: str,
    source_revision_id: str,
    target_substrate: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    definition = _read_object(EXPERIMENT_ROOT / "handoffs" / f"{fixture_id}.json")
    return compile_claim_capsule(
        projection_id=f"{run_id}-critic-projection",
        lineage_identity=definition["lineage_identity"],
        current_responsibility=definition["current_responsibility"],
        source_revision_id=source_revision_id,
        handoff_reason="independent_challenge",
        target_substrate=target_substrate,
        sections=definition["sections"],
    )


def _critic_prompt(capsule: dict[str, Any]) -> str:
    return (
        "Act as an independent critic. Do not edit files. Read TASK.md and any referenced "
        "architecture document, inspect the candidate source, tests, and CANDIDATE.diff, then "
        "return JSON only. Use this exact shape: "
        '{"schema_version":1,"verdict":"approve|changes_requested","findings":['
        '{"finding_id":"f1","severity":"blocking|non_blocking","summary":"...",'
        '"evidence":"path:line or testable observation","claim_ids":["x1"]}]}. '
        "Use only claim IDs from the execution capsule. Cite every requirement-related finding; "
        "use an empty claim_ids list only for a code defect unrelated to a stated claim. Do not "
        "invent a finding to avoid approving correct work.\n\nExecution capsule:\n"
        + canonical_json(capsule)
    )


def _critique_from_output(provider: str, phase_dir: Path) -> dict[str, Any]:
    stdout = (phase_dir / "stdout.jsonl").read_text(encoding="utf-8")
    events, _ = worker_runner._json_lines(stdout)
    text = worker_runner.final_agent_text(provider, events)
    if text is None:
        raise WorkflowRunnerError("critic produced no final agent message")
    return worker_runner.decode_json_object(text)


def _validate_critique(
    critique: dict[str, Any], control: dict[str, Any]
) -> dict[str, str]:
    if set(critique) != {"schema_version", "verdict", "findings"}:
        raise WorkflowRunnerError("critic output keys do not match the frozen contract")
    if critique["schema_version"] != 1 or critique["verdict"] not in {
        "approve",
        "changes_requested",
    }:
        raise WorkflowRunnerError("critic output header is invalid")
    findings = critique["findings"]
    if not isinstance(findings, list):
        raise WorkflowRunnerError("critic findings must be a list")
    identifiers: set[str] = set()
    cited: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {
            "finding_id",
            "severity",
            "summary",
            "evidence",
            "claim_ids",
        }:
            raise WorkflowRunnerError("critic finding does not match the frozen contract")
        finding_id = finding["finding_id"]
        if not isinstance(finding_id, str) or not finding_id or finding_id in identifiers:
            raise WorkflowRunnerError("critic finding IDs must be non-empty and unique")
        identifiers.add(finding_id)
        if finding["severity"] not in {"blocking", "non_blocking"}:
            raise WorkflowRunnerError("critic finding severity is invalid")
        if not isinstance(finding["summary"], str) or not finding["summary"]:
            raise WorkflowRunnerError("critic finding summary is invalid")
        if not isinstance(finding["evidence"], str) or not finding["evidence"]:
            raise WorkflowRunnerError("critic finding evidence is invalid")
        claim_ids = finding["claim_ids"]
        if not isinstance(claim_ids, list) or not all(
            isinstance(item, str) and item for item in claim_ids
        ):
            raise WorkflowRunnerError("critic claim IDs are invalid")
        cited.extend(claim_ids)
    if critique["verdict"] == "approve" and any(
        finding["severity"] == "blocking" for finding in findings
    ):
        raise WorkflowRunnerError("critic approval contradicts a blocking finding")
    if critique["verdict"] == "changes_requested" and not findings:
        raise WorkflowRunnerError("changes_requested requires at least one finding")
    try:
        return resolve_claim_sources(control, cited)
    except ValueError as exc:
        raise WorkflowRunnerError(f"critic cited an invalid claim: {exc}") from exc


def _claim_text(capsule: dict[str, Any], claim_id: str) -> str:
    for section in capsule["claims"].values():
        if claim_id in section:
            return section[claim_id]
    raise WorkflowRunnerError(f"validated claim disappeared from capsule: {claim_id}")


def _revision_prompt(critique: dict[str, Any], capsule: dict[str, Any]) -> str:
    cited = sorted(
        {
            claim_id
            for finding in critique["findings"]
            for claim_id in finding["claim_ids"]
        }
    )
    cited_claims = {claim_id: _claim_text(capsule, claim_id) for claim_id in cited}
    return (
        "An independent foreign-agent critic reviewed your candidate. Evaluate each finding "
        "against the code and requirements, apply every warranted correction, reject unsupported "
        "advice, and rerun the visible tests. Do not use the network or spawn subagents.\n\n"
        "Critique:\n"
        + canonical_json(critique)
        + "\n\nCited claim text:\n"
        + canonical_json(cited_claims)
    )


def _phase_summary(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record": path.relative_to(path.parents[2]).as_posix(),
        "provider": record["provider"],
        "role": record["role"],
        "usage": record["usage"],
        "timing": record["timing"],
    }


def run_workflow(
    *,
    manifest: dict[str, Any],
    fixture_id: str,
    workflow_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    if fixture_id not in manifest.get("fixtures", []):
        raise WorkflowRunnerError(f"fixture is not enabled by the manifest: {fixture_id}")
    workflow = manifest["workflows"].get(workflow_id)
    if not isinstance(workflow, dict):
        raise WorkflowRunnerError(f"unknown workflow: {workflow_id}")
    resolved_run = run_dir.resolve()
    if resolved_run.exists():
        raise WorkflowRunnerError(f"run directory already exists: {resolved_run}")
    apparatus_revision = _apparatus_revision()
    resolved_run.mkdir(parents=True)
    (resolved_run / "phases").mkdir()
    (resolved_run / "workspaces").mkdir()

    run_id = resolved_run.name
    primary_name = workflow["primary"]
    critic_name = workflow.get("critic")
    primary_settings = _provider_settings(manifest, primary_name)
    primary_workspace = resolved_run / "workspaces" / "primary"
    stage = fixture_control.stage_fixture(fixture_id, primary_workspace)
    _write_json(resolved_run / "fixture-stage.json", stage)

    cross_agent = isinstance(critic_name, str)
    initial_session_id = (
        str(uuid.uuid4())
        if cross_agent and primary_name == "claude-code"
        else None
    )
    initial_mode = "fresh-persistent" if cross_agent else "fresh-ephemeral"
    implement_prompt = (EXPERIMENT_ROOT / "prompts" / "implement.txt").read_text(
        encoding="utf-8"
    )
    primary_dir = resolved_run / "phases" / "01-primary"
    primary_record = _run_worker(
        settings=primary_settings,
        workspace=primary_workspace,
        prompt=implement_prompt,
        effort=primary_settings["primary_effort"],
        role="implementer",
        session_mode=initial_mode,
        session_id=initial_session_id,
        timeout_seconds=manifest["timeout_seconds"],
        output_dir=primary_dir,
    )
    primary_score = fixture_control.score_fixture(fixture_id, primary_workspace)
    _write_json(resolved_run / "score-after-primary.json", primary_score)

    phases = [_phase_summary(primary_dir / "worker-run.json", primary_record)]
    if not cross_agent:
        (resolved_run / "final.diff").write_text(
            _candidate_diff(primary_workspace), encoding="utf-8"
        )
        result = {
            "schema_version": 1,
            "series_id": manifest["series_id"],
            "run_id": run_id,
            "apparatus_revision": apparatus_revision,
            "fixture_id": fixture_id,
            "workflow_id": workflow_id,
            "phases": phases,
            "accepted_after_primary": primary_score["accepted"],
            "accepted_final": primary_score["accepted"],
            "operator_interventions": 0,
        }
        _write_json(resolved_run / "workflow-result.json", result)
        return result

    critic_settings = _provider_settings(manifest, critic_name)
    critic_workspace = resolved_run / "workspaces" / "critic"
    candidate_diff = _copy_candidate(primary_workspace, critic_workspace)
    source_revision_id = f"candidate-{primary_score['workspace_tree_sha256'][:16]}"
    capsule, control = _compile_handoff(
        fixture_id,
        run_id,
        source_revision_id,
        f"{critic_name}/{critic_settings['model']}",
    )
    _write_json(resolved_run / "execution-capsule.json", capsule)
    _write_json(resolved_run / "claim-control-envelope.json", control)
    critic_dir = resolved_run / "phases" / "02-critic"
    critic_record = _run_worker(
        settings=critic_settings,
        workspace=critic_workspace,
        prompt=_critic_prompt(capsule),
        effort=critic_settings["critic_effort"],
        role="critic",
        session_mode="fresh-ephemeral",
        session_id=None,
        timeout_seconds=manifest["timeout_seconds"],
        output_dir=critic_dir,
    )
    critique = _critique_from_output(critic_name, critic_dir)
    resolved_claims = _validate_critique(critique, control)
    _write_json(resolved_run / "critique.json", critique)
    _write_json(resolved_run / "resolved-claim-sources.json", resolved_claims)
    phases.append(_phase_summary(critic_dir / "worker-run.json", critic_record))

    observed_session_id = primary_record["session"]["observed_id"]
    if not isinstance(observed_session_id, str) or not observed_session_id:
        raise WorkflowRunnerError("primary persistent session identity is unavailable")
    revision_dir = resolved_run / "phases" / "03-revision"
    revision_record = _run_worker(
        settings=primary_settings,
        workspace=primary_workspace,
        prompt=_revision_prompt(critique, capsule),
        effort=primary_settings["primary_effort"],
        role="implementer",
        session_mode="resume",
        session_id=observed_session_id,
        timeout_seconds=manifest["timeout_seconds"],
        output_dir=revision_dir,
    )
    final_score = fixture_control.score_fixture(fixture_id, primary_workspace)
    _write_json(resolved_run / "score-final.json", final_score)
    (resolved_run / "candidate.diff").write_text(candidate_diff, encoding="utf-8")
    (resolved_run / "final.diff").write_text(
        _candidate_diff(primary_workspace), encoding="utf-8"
    )
    phases.append(_phase_summary(revision_dir / "worker-run.json", revision_record))
    result = {
        "schema_version": 1,
        "series_id": manifest["series_id"],
        "run_id": run_id,
        "apparatus_revision": apparatus_revision,
        "fixture_id": fixture_id,
        "workflow_id": workflow_id,
        "phases": phases,
        "candidate_diff_bytes": len(candidate_diff.encode("utf-8")),
        "critic_verdict": critique["verdict"],
        "critic_finding_count": len(critique["findings"]),
        "valid_claim_citation_count": sum(
            len(finding["claim_ids"]) for finding in critique["findings"]
        ),
        "accepted_after_primary": primary_score["accepted"],
        "accepted_final": final_score["accepted"],
        "operator_interventions": 0,
    }
    _write_json(resolved_run / "workflow-result.json", result)
    return result


def workflow_plan(
    manifest: dict[str, Any], fixture_id: str, workflow_id: str
) -> dict[str, Any]:
    if fixture_id not in manifest.get("fixtures", []):
        raise WorkflowRunnerError(f"fixture is not enabled by the manifest: {fixture_id}")
    workflow = manifest["workflows"].get(workflow_id)
    if not isinstance(workflow, dict):
        raise WorkflowRunnerError(f"unknown workflow: {workflow_id}")
    providers = [workflow["primary"]]
    if workflow.get("critic"):
        providers.extend([workflow["critic"], workflow["primary"]])
    return {
        "schema_version": 1,
        "series_id": manifest["series_id"],
        "fixture_id": fixture_id,
        "workflow_id": workflow_id,
        "model_call_count": len(providers),
        "phases": providers,
        "provider_controls": {
            name: manifest["providers"][name] for name in sorted(set(providers))
        },
        "execute": False,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if not args.execute:
            print(canonical_json(workflow_plan(manifest, args.fixture, args.workflow)))
            return 0
        if args.run_dir is None:
            raise WorkflowRunnerError("--run-dir is required with --execute")
        result = run_workflow(
            manifest=manifest,
            fixture_id=args.fixture,
            workflow_id=args.workflow,
            run_dir=args.run_dir,
        )
        print(canonical_json(result))
        return 0
    except (
        OSError,
        subprocess.SubprocessError,
        fixture_control.FixtureControlError,
        worker_runner.WorkerRunnerError,
        WorkflowRunnerError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

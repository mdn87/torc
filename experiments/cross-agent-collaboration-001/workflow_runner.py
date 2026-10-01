"""Opt-in solo and cross-agent workflow runner for smoke series 001."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath
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
PATCH_ARTIFACT_INTERFACE = "patch-artifact-v1"
_BUNDLE_IGNORED_PARTS = {".git", ".pytest_cache", "__pycache__"}
_MAX_BUNDLE_BYTES = 500_000
_MAX_REPLACEMENT_BYTES = 200_000


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
    interface = manifest.get("worker_interface")
    if (
        not isinstance(interface, dict)
        or interface.get("name") != PATCH_ARTIFACT_INTERFACE
        or not isinstance(interface.get("editable_paths"), dict)
    ):
        raise WorkflowRunnerError("workflow manifest has no supported worker interface")
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
    tool_mode: str,
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
        tool_mode=tool_mode,
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


def _editable_paths(manifest: dict[str, Any], fixture_id: str) -> list[str]:
    paths = manifest["worker_interface"]["editable_paths"].get(fixture_id)
    if not isinstance(paths, list) or not paths or not all(
        isinstance(path, str) and path for path in paths
    ):
        raise WorkflowRunnerError(f"fixture has no frozen editable paths: {fixture_id}")
    if len(paths) != len(set(paths)):
        raise WorkflowRunnerError("editable paths must be unique")
    for value in paths:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
            raise WorkflowRunnerError(f"invalid editable path: {value}")
    return paths


def _visible_file_bundle(workspace: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if not path.is_file() or any(part in _BUNDLE_IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".pyc":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowRunnerError(f"agent-visible file is not UTF-8: {relative}") from exc
        size = len(content.encode("utf-8"))
        total_bytes += size
        if total_bytes > _MAX_BUNDLE_BYTES:
            raise WorkflowRunnerError("agent-visible file bundle exceeds the frozen limit")
        files.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "content": content,
            }
        )
    return {"schema_version": 1, "files": files, "total_bytes": total_bytes}


def _patch_artifact_prompt(
    workspace: Path, editable_paths: list[str], instruction: str
) -> str:
    contract = {
        "schema_version": 1,
        "changes": [{"path": "one editable path", "content": "complete UTF-8 file"}],
        "summary": "short implementation summary",
        "test_plan": ["tests the runner should execute"],
    }
    return (
        "You are in tool-free patch artifact mode. Do not call any tool: every visible input is "
        "included below. Solve the task by reasoning over those inputs. Return one JSON object "
        "only, with no Markdown, matching this contract: "
        + canonical_json(contract)
        + ". Each change must contain the complete replacement content, not a diff. Change only "
        "a path in editable_paths. Do not claim tests were run; test_plan states what the runner "
        "should run. An empty changes list is allowed only if no edit is warranted.\n\n"
        "Phase instruction:\n"
        + instruction
        + "\n\neditable_paths:\n"
        + canonical_json(editable_paths)
        + "\n\nagent_visible_bundle:\n"
        + canonical_json(_visible_file_bundle(workspace))
    )


def _phase_output_object(provider: str, phase_dir: Path) -> dict[str, Any]:
    stdout = (phase_dir / "stdout.jsonl").read_text(encoding="utf-8")
    events, _ = worker_runner._json_lines(stdout)
    text = worker_runner.final_agent_text(provider, events)
    if text is None:
        raise WorkflowRunnerError("worker produced no final agent message")
    return worker_runner.decode_json_object(text)


def _validate_patch_artifact(
    artifact: dict[str, Any], editable_paths: list[str]
) -> list[dict[str, str]]:
    if set(artifact) != {"schema_version", "changes", "summary", "test_plan"}:
        raise WorkflowRunnerError("patch artifact keys do not match the frozen contract")
    if artifact["schema_version"] != 1:
        raise WorkflowRunnerError("patch artifact schema version is unsupported")
    if not isinstance(artifact["summary"], str) or not artifact["summary"]:
        raise WorkflowRunnerError("patch artifact summary is invalid")
    test_plan = artifact["test_plan"]
    if not isinstance(test_plan, list) or not all(
        isinstance(item, str) and item for item in test_plan
    ):
        raise WorkflowRunnerError("patch artifact test plan is invalid")
    changes = artifact["changes"]
    if not isinstance(changes, list):
        raise WorkflowRunnerError("patch artifact changes must be a list")
    allowed = set(editable_paths)
    seen: set[str] = set()
    validated: list[dict[str, str]] = []
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"path", "content"}:
            raise WorkflowRunnerError("patch artifact change is invalid")
        path = change["path"]
        content = change["content"]
        if path not in allowed or path in seen:
            raise WorkflowRunnerError(f"patch artifact path is unauthorized or repeated: {path}")
        if not isinstance(content, str) or "\x00" in content:
            raise WorkflowRunnerError(f"patch artifact content is invalid: {path}")
        if len(content.encode("utf-8")) > _MAX_REPLACEMENT_BYTES:
            raise WorkflowRunnerError(f"patch artifact replacement is too large: {path}")
        seen.add(path)
        validated.append({"path": path, "content": content})
    return validated


def _apply_patch_artifact(
    workspace: Path, artifact: dict[str, Any], editable_paths: list[str]
) -> dict[str, Any]:
    changes = _validate_patch_artifact(artifact, editable_paths)
    applied: list[dict[str, Any]] = []
    for change in changes:
        path = workspace / PurePosixPath(change["path"])
        if not path.is_file() or not path.resolve().is_relative_to(workspace.resolve()):
            raise WorkflowRunnerError(f"editable artifact path is unavailable: {change['path']}")
        before = path.read_bytes()
        after = change["content"].encode("utf-8")
        path.write_bytes(after)
        applied.append(
            {
                "path": change["path"],
                "before_sha256": hashlib.sha256(before).hexdigest(),
                "after_sha256": hashlib.sha256(after).hexdigest(),
                "bytes": len(after),
            }
        )
    return {
        "schema_version": 1,
        "interface": PATCH_ARTIFACT_INTERFACE,
        "applied": applied,
    }


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


def _critic_prompt(capsule: dict[str, Any], workspace: Path) -> str:
    return (
        "Act as an independent critic in tool-free mode. Do not call any tool: every visible "
        "input is included below. Inspect the task, candidate source, tests, and CANDIDATE.diff, "
        "then return JSON only. Use this exact shape: "
        '{"schema_version":1,"verdict":"approve|changes_requested","findings":['
        '{"finding_id":"f1","severity":"blocking|non_blocking","summary":"...",'
        '"evidence":"path:line or testable observation","claim_ids":["x1"]}]}. '
        "Use only claim IDs from the execution capsule. Cite every requirement-related finding; "
        "use an empty claim_ids list only for a code defect unrelated to a stated claim. Do not "
        "invent a finding to avoid approving correct work.\n\nExecution capsule:\n"
        + canonical_json(capsule)
        + "\n\nAgent-visible bundle:\n"
        + canonical_json(_visible_file_bundle(workspace))
    )


def _critique_from_output(provider: str, phase_dir: Path) -> dict[str, Any]:
    return _phase_output_object(provider, phase_dir)


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


def _revision_prompt(
    critique: dict[str, Any],
    capsule: dict[str, Any],
    workspace: Path,
    editable_paths: list[str],
) -> str:
    cited = sorted(
        {
            claim_id
            for finding in critique["findings"]
            for claim_id in finding["claim_ids"]
        }
    )
    cited_claims = {claim_id: _claim_text(capsule, claim_id) for claim_id in cited}
    instruction = (
        "An independent foreign-agent critic reviewed your candidate. Evaluate each finding "
        "against the code and requirements, apply every warranted correction in the returned "
        "artifact, and reject unsupported advice.\n\n"
        "Critique:\n"
        + canonical_json(critique)
        + "\n\nCited claim text:\n"
        + canonical_json(cited_claims)
    )
    return _patch_artifact_prompt(workspace, editable_paths, instruction)


def _phase_summary(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record": path.relative_to(path.parents[2]).as_posix(),
        "provider": record["provider"],
        "role": record["role"],
        "tool_mode": record.get("tool_mode", "workspace"),
        "prompt_bytes": record.get("prompt_bytes"),
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
    editable_paths = _editable_paths(manifest, fixture_id)

    cross_agent = isinstance(critic_name, str)
    initial_session_id = (
        str(uuid.uuid4())
        if cross_agent and primary_name == "claude-code"
        else None
    )
    initial_mode = "fresh-persistent" if cross_agent else "fresh-ephemeral"
    implement_prompt = _patch_artifact_prompt(
        primary_workspace,
        editable_paths,
        "Implement the task described by the bundled TASK.md. Preserve every stated constraint, "
        "satisfy the visible tests, and account for likely edge cases without seeing hidden tests.",
    )
    primary_dir = resolved_run / "phases" / "01-primary"
    primary_record = _run_worker(
        settings=primary_settings,
        workspace=primary_workspace,
        prompt=implement_prompt,
        effort=primary_settings["primary_effort"],
        role="implementer",
        tool_mode="none",
        session_mode=initial_mode,
        session_id=initial_session_id,
        timeout_seconds=manifest["timeout_seconds"],
        output_dir=primary_dir,
    )
    primary_artifact = _phase_output_object(primary_name, primary_dir)
    primary_application = _apply_patch_artifact(
        primary_workspace, primary_artifact, editable_paths
    )
    _write_json(resolved_run / "primary-artifact.json", primary_artifact)
    _write_json(resolved_run / "primary-application.json", primary_application)
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
            "worker_interface": PATCH_ARTIFACT_INTERFACE,
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
        prompt=_critic_prompt(capsule, critic_workspace),
        effort=critic_settings["critic_effort"],
        role="critic",
        tool_mode="none",
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

    revision_performed = critique["verdict"] == "changes_requested"
    if revision_performed:
        observed_session_id = primary_record["session"]["observed_id"]
        if not isinstance(observed_session_id, str) or not observed_session_id:
            raise WorkflowRunnerError("primary persistent session identity is unavailable")
        revision_dir = resolved_run / "phases" / "03-revision"
        revision_record = _run_worker(
            settings=primary_settings,
            workspace=primary_workspace,
            prompt=_revision_prompt(
                critique, capsule, primary_workspace, editable_paths
            ),
            effort=primary_settings["primary_effort"],
            role="implementer",
            tool_mode="none",
            session_mode="resume",
            session_id=observed_session_id,
            timeout_seconds=manifest["timeout_seconds"],
            output_dir=revision_dir,
        )
        revision_artifact = _phase_output_object(primary_name, revision_dir)
        revision_application = _apply_patch_artifact(
            primary_workspace, revision_artifact, editable_paths
        )
        _write_json(resolved_run / "revision-artifact.json", revision_artifact)
        _write_json(resolved_run / "revision-application.json", revision_application)
        phases.append(_phase_summary(revision_dir / "worker-run.json", revision_record))
        final_score = fixture_control.score_fixture(fixture_id, primary_workspace)
    else:
        final_score = primary_score
        _write_json(
            resolved_run / "revision-skipped.json",
            {
                "schema_version": 1,
                "reason": "critic_approved",
                "primary_score_reused": True,
            },
        )
    _write_json(resolved_run / "score-final.json", final_score)
    (resolved_run / "candidate.diff").write_text(candidate_diff, encoding="utf-8")
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
        "worker_interface": PATCH_ARTIFACT_INTERFACE,
        "phases": phases,
        "candidate_diff_bytes": len(candidate_diff.encode("utf-8")),
        "critic_verdict": critique["verdict"],
        "critic_finding_count": len(critique["findings"]),
        "revision_performed": revision_performed,
        "revision_skipped_reason": None if revision_performed else "critic_approved",
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
        "worker_interface": manifest["worker_interface"]["name"],
        "model_call_count": len(providers),
        "model_call_count_range": (
            [2, len(providers)] if workflow.get("critic") else [1, 1]
        ),
        "revision_policy": (
            "changes_requested_only" if workflow.get("critic") else "not_applicable"
        ),
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

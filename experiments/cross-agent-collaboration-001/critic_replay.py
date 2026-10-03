"""Replay one frozen primary candidate through a measured critic transport."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import fixture_control  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402


class CriticReplayError(RuntimeError):
    """Raised when a critic replay cannot preserve its controls."""


def _source_evidence(source_run: Path, fixture_id: str) -> dict[str, Any]:
    resolved = source_run.resolve()
    result = workflow._read_object(resolved / "workflow-result.json")
    artifact_path = resolved / "primary-artifact.json"
    score = workflow._read_object(resolved / "score-after-primary.json")
    artifact = workflow._read_object(artifact_path)
    if result.get("fixture_id") != fixture_id or score.get("fixture_id") != fixture_id:
        raise CriticReplayError("source run fixture does not match the replay fixture")
    if result.get("worker_interface") != workflow.PATCH_ARTIFACT_INTERFACE:
        raise CriticReplayError("source run does not use the patch artifact interface")
    workspace_hash = score.get("workspace_tree_sha256")
    if not isinstance(workspace_hash, str) or not workspace_hash:
        raise CriticReplayError("source run has no candidate workspace hash")
    return {
        "source_run_id": result.get("run_id", resolved.name),
        "source_apparatus_revision": result.get("apparatus_revision"),
        "primary_artifact": artifact,
        "primary_artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "workspace_tree_sha256": workspace_hash,
        "accepted_after_primary": score.get("accepted"),
    }


def replay_plan(
    *,
    manifest: dict[str, Any],
    fixture_id: str,
    source_run: Path,
    critic_provider: str,
    critic_context: str,
) -> dict[str, Any]:
    if fixture_id not in manifest.get("fixtures", []):
        raise CriticReplayError(f"fixture is not enabled by the manifest: {fixture_id}")
    if critic_context not in workflow.CRITIC_CONTEXTS:
        raise CriticReplayError(f"unsupported critic context: {critic_context}")
    settings = workflow._provider_settings(manifest, critic_provider)
    source = _source_evidence(source_run, fixture_id)
    return {
        "schema_version": 1,
        "series_id": manifest["series_id"],
        "fixture_id": fixture_id,
        "source_run_id": source["source_run_id"],
        "source_workspace_tree_sha256": source["workspace_tree_sha256"],
        "critic_provider": critic_provider,
        "critic_context": critic_context,
        "model_call_count": 1,
        "provider_controls": settings,
        "execute": False,
    }


def run_critic_replay(
    *,
    manifest: dict[str, Any],
    fixture_id: str,
    source_run: Path,
    critic_provider: str,
    critic_context: str,
    run_dir: Path,
) -> dict[str, Any]:
    replay_plan(
        manifest=manifest,
        fixture_id=fixture_id,
        source_run=source_run,
        critic_provider=critic_provider,
        critic_context=critic_context,
    )
    resolved_run = run_dir.resolve()
    if resolved_run.exists():
        raise CriticReplayError(f"run directory already exists: {resolved_run}")
    apparatus_revision = workflow._apparatus_revision()
    source = _source_evidence(source_run, fixture_id)
    editable_paths = workflow._editable_paths(manifest, fixture_id)
    settings = workflow._provider_settings(manifest, critic_provider)

    resolved_run.mkdir(parents=True)
    (resolved_run / "phases").mkdir()
    (resolved_run / "workspaces").mkdir()
    candidate_workspace = resolved_run / "workspaces" / "candidate"
    stage = fixture_control.stage_fixture(fixture_id, candidate_workspace)
    workflow._write_json(resolved_run / "fixture-stage.json", stage)
    application = workflow._apply_patch_artifact(
        candidate_workspace, source["primary_artifact"], editable_paths
    )
    workflow._write_json(resolved_run / "primary-application.json", application)
    candidate_score = fixture_control.score_fixture(fixture_id, candidate_workspace)
    workflow._write_json(resolved_run / "score-candidate.json", candidate_score)
    if candidate_score["workspace_tree_sha256"] != source["workspace_tree_sha256"]:
        raise CriticReplayError("reconstructed candidate does not match the source run")
    workflow._write_json(
        resolved_run / "source-primary-ref.json",
        {
            "schema_version": 1,
            "source_run_id": source["source_run_id"],
            "source_apparatus_revision": source["source_apparatus_revision"],
            "primary_artifact_sha256": source["primary_artifact_sha256"],
            "workspace_tree_sha256": source["workspace_tree_sha256"],
            "accepted_after_primary": source["accepted_after_primary"],
        },
    )

    critic_workspace = resolved_run / "workspaces" / "critic"
    candidate_diff = workflow._copy_candidate(candidate_workspace, critic_workspace)
    source_revision_id = f"candidate-{candidate_score['workspace_tree_sha256'][:16]}"
    capsule, control = workflow._compile_handoff(
        fixture_id,
        resolved_run.name,
        source_revision_id,
        f"{critic_provider}/{settings['model']}",
    )
    workflow._write_json(resolved_run / "execution-capsule.json", capsule)
    workflow._write_json(resolved_run / "claim-control-envelope.json", control)
    (resolved_run / "candidate.diff").write_text(candidate_diff, encoding="utf-8")

    critic_dir = resolved_run / "phases" / "01-critic"
    critic_record = workflow._run_worker(
        settings=settings,
        workspace=critic_workspace,
        prompt=workflow._critic_prompt(
            capsule, critic_workspace, editable_paths, critic_context
        ),
        effort=settings["critic_effort"],
        role="critic",
        tool_mode="none",
        session_mode="fresh-ephemeral",
        session_id=None,
        timeout_seconds=manifest["timeout_seconds"],
        output_dir=critic_dir,
    )
    critique = workflow._critique_from_output(critic_provider, critic_dir)
    resolved_claims = workflow._validate_critique(critique, control)
    workflow._write_json(resolved_run / "critique.json", critique)
    workflow._write_json(resolved_run / "resolved-claim-sources.json", resolved_claims)
    result = {
        "schema_version": 1,
        "series_id": manifest["series_id"],
        "run_id": resolved_run.name,
        "apparatus_revision": apparatus_revision,
        "fixture_id": fixture_id,
        "workflow_id": "critic-replay",
        "worker_interface": workflow.PATCH_ARTIFACT_INTERFACE,
        "replay_source_run_id": source["source_run_id"],
        "critic_context": critic_context,
        "critic_verdict": critique["verdict"],
        "critic_finding_count": len(critique["findings"]),
        "valid_claim_citation_count": sum(
            len(finding["claim_ids"]) for finding in critique["findings"]
        ),
        "revision_performed": False,
        "accepted_after_primary": candidate_score["accepted"],
        "accepted_final": candidate_score["accepted"],
        "phases": [
            workflow._phase_summary(critic_dir / "worker-run.json", critic_record)
        ],
        "operator_interventions": 0,
    }
    workflow._write_json(resolved_run / "workflow-result.json", result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=workflow.DEFAULT_MANIFEST)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument(
        "--critic-provider", choices=workflow.worker_runner.PROVIDERS, required=True
    )
    parser.add_argument(
        "--critic-context", choices=sorted(workflow.CRITIC_CONTEXTS), required=True
    )
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = workflow.load_manifest(args.manifest)
        if not args.execute:
            result = replay_plan(
                manifest=manifest,
                fixture_id=args.fixture,
                source_run=args.source_run,
                critic_provider=args.critic_provider,
                critic_context=args.critic_context,
            )
        else:
            if args.run_dir is None:
                raise CriticReplayError("--run-dir is required with --execute")
            result = run_critic_replay(
                manifest=manifest,
                fixture_id=args.fixture,
                source_run=args.source_run,
                critic_provider=args.critic_provider,
                critic_context=args.critic_context,
                run_dir=args.run_dir,
            )
        print(canonical_json(result))
        return 0
    except (
        CriticReplayError,
        OSError,
        subprocess.SubprocessError,
        fixture_control.FixtureControlError,
        workflow.worker_runner.WorkerRunnerError,
        workflow.WorkflowRunnerError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

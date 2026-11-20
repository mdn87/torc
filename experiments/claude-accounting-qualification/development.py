"""Two fixed development assignments through the installed Autowork subscription executor."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from autowork.campaign.assignment_policy import compile_execution_assignment, load_assignment_policy
from autowork.campaign.claude_route_execution import (
    build_claude_child_command,
    preflight_claude_launch,
)
from autowork.campaign.claude_stream_usage import export_assignment
from autowork.campaign.dispatch_contract import AllowedPath, DispatchRequest, VerificationCommand
from autowork.campaign.dispatch_store import DispatchStore
from autowork.campaign.execution_plan import build_execution_plan
from autowork.campaign.executor_adapter import (
    CAMPAIGN_ROOT,
    ClaudeSubscriptionCliExecutor,
    ExecutorRunRequest,
)
from autowork.campaign.local_node_attestation import attest_local_node
from autowork.campaign.model_catalog import load_model_catalog
from autowork.campaign.node_inventory import load_node_inventory
from autowork.campaign.placement import resolve_local_placement
from autowork.campaign.profile import load_profile
from autowork.campaign.project_config import screen_project_config
from autowork.campaign.remote_eligibility import assess_remote_eligibility
from autowork.campaign.route_class import compile_route_class_decision
from autowork.campaign.subscription_cli import (
    fingerprint_subscription_cli_launch,
    resolve_subscription_cli_launch,
)

TASKS = {
    "single": "Reply with exactly the two words violet square. This task needs no file changes.",
    "multi": (
        "Read label.txt, change its color from blue to violet, and keep the shape unchanged. "
        "Report the final label."
    ),
}


def save(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def develop(root, label, *, admit):
    root = root.resolve()
    folder = root / label
    folder.mkdir(parents=True, exist_ok=False)
    workspace = folder / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    target = workspace / "label.txt"
    target.write_text("blue square\n", encoding="utf-8")
    task = TASKS[label]
    run_id = f"torc-development-{label}"
    store = DispatchStore.create(folder / "runs" / run_id)
    profile = load_profile(CAMPAIGN_ROOT / "profiles/claude-measured-continuation.toml")
    request = DispatchRequest(
        version=2,
        correlation_id=run_id,
        caller="autowork",
        profile=profile.name,
        role="implementer",
        workspace=str(workspace),
        task=task,
        write=True,
        allowed_paths=(AllowedPath("label.txt", "file"),),
        verification=(VerificationCommand(("python", "-m", "pytest", "-q")),),
        timeout_seconds=600,
        task_class_hint="implementation",
        risk_tier_hint="standard",
    )
    policy = load_assignment_policy(CAMPAIGN_ROOT / "assignment-policy.toml")
    catalog = load_model_catalog(CAMPAIGN_ROOT / "model-catalog.toml")
    assignment = compile_execution_assignment(request, profile, catalog, None, policy).assignment
    route = catalog.resolve(assignment.route)
    screening = screen_project_config(workspace, write=True, project_trusted=True)
    executor = ClaudeSubscriptionCliExecutor()
    env = dict(os.environ)
    inventory = load_node_inventory()
    local = attest_local_node(
        inventory=inventory,
        workspace=workspace,
        executor=executor.descriptor,
        env=env,
        observed_at=datetime.now(UTC),
    )
    remotes = assess_remote_eligibility(
        inventory=inventory,
        local_attestation=local,
        assignment=assignment,
        executor=executor.descriptor,
        evaluated_at=datetime.now(UTC),
    )
    placement = resolve_local_placement(
        assignment=assignment,
        route=route,
        executor=executor.descriptor,
        inventory=inventory,
        local_attestation=local,
        remote_eligibility=remotes,
    )
    decision = compile_route_class_decision(assignment, policy)
    plan = build_execution_plan(
        assignment=assignment,
        route=route,
        catalog_sha256=catalog.provenance.sha256,
        route_class_decision=decision,
        executor=executor.descriptor,
        placement=placement,
    )
    store.publish_request_summary(request)
    store.publish_assignment(assignment)
    store.publish_execution_plan(plan)
    if not admit:
        prefix = resolve_subscription_cli_launch("claude", env=env)
        command = build_claude_child_command(
            request=request,
            assignment=assignment,
            profile=profile,
            route=route,
            screening=screening,
            env=env,
            run_dir=store.paths.run_dir,
            argv_prefix=prefix,
        )
        preflight = preflight_claude_launch(
            prefix,
            launch_sha256=fingerprint_subscription_cli_launch(prefix),
            env=command.env,
            cwd=workspace,
            stream_accounting=True,
        )
        return {
            "preflight": preflight.version,
            "auth": preflight.auth_method,
            "inference_starts": 0,
        }
    deadline = time.time() + request.timeout_seconds
    store.publish_starting(
        run_id=run_id,
        parent_pid=os.getpid(),
        owner_deadline_unix=deadline,
        source_commit=None,
        branch=None,
        worktree=str(workspace),
        allowed_paths=request.allowed_paths,
        initial_git_state={"fixture": label},
    )
    save(
        folder / "admission.json",
        {"development": label, "run_id": run_id, "max_starts": 2, "deadline_unix": deadline},
    )
    ctx = ExecutorRunRequest(
        run_id=run_id,
        attempt=1,
        request=request,
        assignment=assignment,
        route=route,
        execution_plan=plan,
        profile=profile,
        screening=screening,
        store=store,
        owner_path=store.paths.owner,
        owner_deadline_unix=deadline,
        attestation=None,
        env=env,
    )
    result = executor.execute(ctx)
    child = store.paths.child_output
    evidence = export_assignment(
        child / "attempt-001.claude-usage", child / "attempt-001.completion.json"
    )
    save(folder / "usage.json", evidence)
    behavior = (
        result.final_message.strip().rstrip(".").casefold() == "violet square"
        and target.read_text().strip() == "blue square"
        if label == "single"
        else target.read_text().strip() == "violet square"
    )
    summary = dict(
        development=label,
        owner_status=result.status.value,
        behavior_verified=behavior,
        complete=evidence["complete"],
        starts=len(evidence["calls"]),
        requests=[len(c["requests"]) for c in evidence["calls"]],
        issues=[c["issues"] for c in evidence["calls"]],
    )
    save(folder / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("case", choices=TASKS)
    parser.add_argument("--admit", action="store_true", help="Consume this development assignment")
    args = parser.parse_args()
    print(json.dumps(develop(args.root, args.case, admit=args.admit)))

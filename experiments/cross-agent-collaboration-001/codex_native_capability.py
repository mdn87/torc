"""Build the model-free local Codex native-subagent capability probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import fixture_control  # noqa: E402
import native_context_request as source_controls  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "codex-native-capability-001-plan.json"
_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "in_app_browser",
    "plugins",
    "remote_plugin",
    "skill_search",
    "code_mode_host",
    "shell_tool",
    "unified_exec",
)


class CodexNativeCapabilityError(RuntimeError):
    """Raised when the local capability probe controls do not reconstruct."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexNativeCapabilityError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CodexNativeCapabilityError(f"expected a JSON object: {path}")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _critic_schema() -> dict[str, Any]:
    finding = {
        "type": "object",
        "properties": {
            "finding_id": {"type": "string"},
            "severity": {"type": "string", "enum": ["blocking", "non_blocking"]},
            "summary": {"type": "string"},
            "evidence": {"type": "string"},
            "claim_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "finding_id",
            "severity",
            "summary",
            "evidence",
            "claim_ids",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "verdict": {
                "type": "string",
                "enum": ["approve", "changes_requested"],
            },
            "findings": {"type": "array", "items": finding},
        },
        "required": ["schema_version", "verdict", "findings"],
        "additionalProperties": False,
    }


def _payload(plan: dict[str, Any]) -> str:
    candidate = source_controls._candidate(plan["candidate"]["candidate_id"])
    if candidate["candidate_workspace_tree_sha256"] != plan["candidate"][
        "candidate_workspace_tree_sha256"
    ]:
        raise CodexNativeCapabilityError("capability candidate hash has drifted")
    fixture_id = candidate["fixture_id"]
    fixture_control.verify_fixture(fixture_id, fixture_control.load_manifest())
    model = plan["provider_controls"]["subagent_model"]
    capsule, _ = workflow._compile_handoff(
        fixture_id,
        plan["series_id"],
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"codex-native/{model}",
    )
    return workflow._critic_prompt(
        capsule,
        fixture_control.FIXTURES_ROOT / fixture_id / "agent-visible",
        workflow._editable_paths(workflow.load_manifest(), fixture_id),
        plan["candidate"]["critic_context"],
    )


def _root_prompt(payload: str, plan: dict[str, Any]) -> str:
    controls = plan["provider_controls"]
    return (
        "This is a controlled native-subagent capability probe. Do not review the candidate "
        "yourself. Call spawn_agent exactly once with task_name 'critic', fork_turns 'none', "
        f"model {controls['subagent_model']!r}, and reasoning_effort "
        f"{controls['subagent_effort']!r}. The child task message must contain the complete "
        "critic payload below unchanged and must tell the child not to spawn descendants or "
        "use tools. Wait for that child once. Return its JSON result unchanged and emit no "
        "other final prose. Do not call list, send, follow-up, interrupt, shell, file, web, "
        "MCP, app, or plugin tools.\n\nCritic payload:\n" + payload
    )


def build_probe(*, executable: str = "codex") -> dict[str, Any]:
    """Return exact app-server inputs without starting Codex or making a model call."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {
        "waiting_usage_reset",
        "ready",
        "capability_confirmed",
        "capability_rejected",
    }:
        raise CodexNativeCapabilityError("capability probe is not in a plannable state")
    controls = plan.get("provider_controls")
    if not isinstance(controls, dict):
        raise CodexNativeCapabilityError("capability provider controls are missing")
    payload = _payload(plan)
    prompt = _root_prompt(payload, plan)
    fixture_id = plan["candidate"]["fixture_id"]
    workspace = fixture_control.FIXTURES_ROOT / fixture_id / "agent-visible"
    launch = [executable, "app-server", "--stdio", "--strict-config"]
    for feature in _DISABLED_FEATURES:
        launch.extend(["--disable", feature])
    launch.extend(
        [
            "--enable",
            "multi_agent",
            "-c",
            "agents.enabled=true",
            "-c",
            "agents.max_concurrent_threads_per_session=1",
            "-c",
            f"agents.default_subagent_model={json.dumps(controls['subagent_model'])}",
            "-c",
            "agents.default_subagent_reasoning_effort="
            + json.dumps(controls["subagent_effort"]),
        ]
    )
    thread_config = {
        "features": {
            **{feature: False for feature in _DISABLED_FEATURES},
            "multi_agent": True,
        },
        "agents": {
            "enabled": True,
            "max_concurrent_threads_per_session": controls[
                "max_concurrent_subagents"
            ],
            "default_subagent_model": controls["subagent_model"],
            "default_subagent_reasoning_effort": controls["subagent_effort"],
        },
        "mcp_servers": {},
    }
    initialize = {
        "clientInfo": {"name": "torc-native-capability", "version": "1.0"},
        "capabilities": {"experimentalApi": True},
    }
    thread_start = {
        "model": controls["root_model"],
        "cwd": str(workspace.resolve()),
        "approvalPolicy": "never",
        "sandbox": "read-only",
        "ephemeral": True,
        "experimentalRawEvents": False,
        "serviceName": "torc-experiment",
        "threadSource": "appServer",
        "environments": [],
        "config": thread_config,
        "developerInstructions": (
            "This is a tool-free transport measurement. Use only spawn_agent and wait_agent "
            "exactly as the user requests. Do not solve the delegated review in the root."
        ),
    }
    turn_start = {
        "input": [{"type": "text", "text": prompt}],
        "model": controls["root_model"],
        "effort": controls["root_effort"],
        "cwd": str(workspace.resolve()),
        "approvalPolicy": "never",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
        "environments": [],
        "summary": "none",
        "outputSchema": _critic_schema(),
    }
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "status": "planned_not_executed",
        "execute": False,
        "harness_version": controls["harness_version"],
        "workspace": str(workspace.resolve()),
        "launch": launch,
        "initialize": initialize,
        "thread_start": thread_start,
        "turn_start": turn_start,
        "critic_payload_bytes": len(payload.encode("utf-8")),
        "critic_payload_sha256": _sha256_text(payload),
        "root_prompt_bytes": len(prompt.encode("utf-8")),
        "root_prompt_sha256": _sha256_text(prompt),
        "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
    }


def public_plan(*, executable: str = "codex", include_input: bool = False) -> dict[str, Any]:
    result = build_probe(executable=executable)
    if include_input:
        return result
    redacted = dict(result)
    redacted["turn_start"] = {
        **result["turn_start"],
        "input": "<redacted; see root prompt hash and bytes>",
    }
    return redacted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="codex")
    parser.add_argument("--include-input", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(
            canonical_json(
                public_plan(
                    executable=args.executable,
                    include_input=args.include_input,
                )
            )
        )
        return 0
    except (CodexNativeCapabilityError, fixture_control.FixtureControlError) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

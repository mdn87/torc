"""Thin P1a adapters for deterministic replay and bounded live harnesses."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol

_CONTINUITY_FIELDS = (
    "lineage_identity",
    "current_responsibility",
    "settled_decisions",
    "active_commitments",
    "hard_constraints",
    "unresolved_work",
    "uncertainties",
    "evidence_refs",
)
_RECONSTRUCTION_FIELDS = (
    "lineage_identity",
    "current_responsibility",
    "settled_decisions",
    "active_commitments",
    "hard_constraints",
    "unresolved_work",
    "uncertainties",
    "handoff_reason",
    "source_revision_id",
    "new_inferences",
    "assertions",
    "review_areas",
    "completion_status",
)
_SOURCE_ASSIGNMENT = (
    "Read only task.json. Return JSON only with schema_version 1 and a continuity "
    "object containing exactly these keys, copied without inference: "
    + ", ".join(_CONTINUITY_FIELDS)
    + ". Do not use network access or inspect any other path."
)
_TARGET_ASSIGNMENT_TEMPLATE = (
    "First attempt to read {canary} with the Read tool; it must be denied. "
    "Then read only task.json and continuity-payload.json. Independently perform "
    "the requested review and return boundary_probe='denied' plus reconstruction. "
    "The reconstruction must use exactly these keys: "
    + ", ".join(_RECONSTRUCTION_FIELDS)
    + ". Preserve inherited values verbatim, use handoff_reason "
    "'task_phase_transition', source_revision_id 'p1a-revision-0002', label "
    "inherited assertions with source_ref task.json, and do not modify files."
)


def _stage_controls(context: dict[str, Any], stage: str) -> dict[str, Any]:
    manifest = context.get("manifest", {})
    settings = manifest.get("settings", {}) if isinstance(manifest, dict) else {}
    controls = settings.get(stage, {}) if isinstance(settings, dict) else {}
    return controls if isinstance(controls, dict) else {}


def _record_controls(
    evidence: dict[str, Any], controls: dict[str, Any], assignment: str
) -> None:
    evidence["controlled_settings"] = {
        key: controls[key]
        for key in ("model", "reasoning_effort", "service_tier")
        if key in controls
    }
    evidence["assignment_sha256"] = hashlib.sha256(assignment.encode()).hexdigest()


class ExperimentAdapter(Protocol):
    def probe(self, context: dict[str, Any], stage: str) -> dict[str, Any]: ...

    def capture_source(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def start_target(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def collect_target(self, context: dict[str, Any]) -> dict[str, Any]: ...


class ReplayAdapter:
    name = "replay"

    def probe(self, context: dict[str, Any], stage: str) -> dict[str, Any]:
        lane = context["manifest"]["selected_lane"]
        if lane == "native-persistence":
            return {
                "adapter": self.name,
                "stage": stage,
                "available": False,
                "reason": "replay models cross-harness native persistence as unavailable",
            }
        return {
            "adapter": self.name,
            "stage": stage,
            "available": True,
            "version": "p1a-1",
        }

    def capture_source(self, context: dict[str, Any]) -> dict[str, Any]:
        task = json.loads(
            (Path(context["source_workspace"]) / "task.json").read_text(
                encoding="utf-8"
            )
        )
        return {
            "schema_version": 1,
            "adapter": self.name,
            "disposition": "accepted",
            "continuity": {field: task[field] for field in _CONTINUITY_FIELDS},
            "harness_evidence": self.probe(context, "source"),
        }

    def start_target(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "activation_ref": "replay-target-0001",
            "disposition": "accepted",
        }

    def collect_target(self, context: dict[str, Any]) -> dict[str, Any]:
        task = json.loads(
            (Path(context["target_workspace"]) / "task.json").read_text(
                encoding="utf-8"
            )
        )
        reconstruction = {
            "lineage_identity": task["lineage_identity"],
            "current_responsibility": task["current_responsibility"],
            "settled_decisions": task["settled_decisions"],
            "active_commitments": task["active_commitments"],
            "hard_constraints": task["hard_constraints"],
            "unresolved_work": task["unresolved_work"],
            "uncertainties": task["uncertainties"],
            "handoff_reason": "task_phase_transition",
            "source_revision_id": "p1a-revision-0002",
            "new_inferences": [],
            "assertions": [
                {"text": item, "label": "inherited", "source_ref": "task.json"}
                for field in (
                    "settled_decisions",
                    "active_commitments",
                    "hard_constraints",
                    "unresolved_work",
                )
                for item in task[field]
            ],
            "review_areas": ["authority", "artifact-integrity", "adapter-boundary"],
            "completion_status": "complete",
        }
        return {
            "schema_version": 1,
            "adapter": self.name,
            "disposition": "accepted",
            "task_output": {
                "review_areas": reconstruction["review_areas"],
                "completion_status": "complete",
            },
            "reconstruction": reconstruction,
            "usage": {"supplied": False},
        }


def _run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, **kwargs)


def _decode_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("harness output did not contain a JSON object") from None
        value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("harness output must be a JSON object")
    return value


class _WslLiveAdapter:
    executable = ""
    name = ""

    def __init__(self) -> None:
        self._probe_cache: dict[str, dict[str, Any]] = {}

    @property
    def distro(self) -> str:
        return os.environ.get("TORC_WSL_DISTRO", "Ubuntu")

    def _wsl(self) -> str | None:
        return shutil.which("wsl.exe") if os.name == "nt" else None

    def _resolve(self, name: str) -> str | None:
        wsl = self._wsl()
        if not wsl:
            return None
        script = (
            'export NVM_DIR="$HOME/.nvm"; '
            '[ ! -s "$NVM_DIR/nvm.sh" ] || . "$NVM_DIR/nvm.sh" >/dev/null; '
            "nvm use default >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || true; "
            'command -v "$1"'
        )
        completed = _run(
            [wsl, "-d", self.distro, "--exec", "bash", "-lc", script, "torc", name],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        resolved = completed.stdout.strip().splitlines()
        return resolved[-1] if completed.returncode == 0 and resolved else None

    def _path(self, path: Path) -> str | None:
        wsl = self._wsl()
        if not wsl:
            return None
        completed = _run(
            [wsl, "-d", self.distro, "--exec", "wslpath", "-a", str(path.resolve())],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    def _version_command(self, executable: str) -> list[str]:
        return [executable, "--version"]

    def probe(self, context: dict[str, Any], stage: str) -> dict[str, Any]:
        if stage in self._probe_cache:
            return self._probe_cache[stage]
        workspace = Path(context[f"{stage}_workspace"])
        evidence: dict[str, Any] = {
            "adapter": self.name,
            "stage": stage,
            "available": False,
            "workspace_identity": workspace.name,
            "allowed_paths": context.get(f"{stage}_allowed_paths", []),
            "execution_environment": "wsl2",
        }
        executable = self._resolve(self.executable)
        linux_workspace = self._path(workspace)
        wsl = self._wsl()
        if not executable or not linux_workspace or not wsl:
            evidence["reason"] = f"native WSL {self.executable} executable not found"
            self._probe_cache[stage] = evidence
            return evidence
        command = self._version_command(executable)
        completed = _run(
            [wsl, "-d", self.distro, "--exec", *command],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        version = (completed.stdout or completed.stderr).strip()[:200]
        controls = _stage_controls(context, stage)
        evidence.update(
            {
                "available": completed.returncode == 0,
                "exit_status": completed.returncode,
                "version": version,
                "command_plan": [self.executable, "--version"],
                "linux_workspace": linux_workspace,
            }
        )
        if completed.returncode:
            evidence["reason"] = f"{self.executable} version probe failed"
        expected_version = controls.get("harness_version")
        if completed.returncode == 0 and expected_version and version != expected_version:
            evidence.update(
                available=False,
                reason=(
                    f"{self.executable} version differs from frozen control: "
                    f"expected {expected_version!r}, got {version!r}"
                ),
            )
        evidence["_resolved"] = executable
        self._probe_cache[stage] = evidence
        return evidence

    @staticmethod
    def _public_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in evidence.items() if not key.startswith("_")}

    def _stopped(self, evidence: dict[str, Any], disposition: str) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "disposition": disposition,
            "harness_evidence": self._public_evidence(evidence),
            "reason": evidence.get("reason", "live harness boundary was not evidenced"),
        }


class CodexSourceAdapter(_WslLiveAdapter):
    executable = "codex"
    name = "codex"

    def _version_command(self, executable: str) -> list[str]:
        node = self._resolve("node")
        return [node, executable, "--version"] if node else [executable, "--version"]

    def _profile(self, executable: str) -> tuple[str, str] | None:
        node = self._resolve("node")
        wsl = self._wsl()
        if not node or not wsl:
            return None
        script = (
            'entry=$(readlink -f "$1"); root=$(dirname "$(dirname "$entry")"); '
            'helper=$(find "$root" -type f '
            '-path "*/@openai/codex-linux-*/vendor/*/bin/codex" -print -quit); '
            'printf "%s\\n%s" "$(dirname "$helper")" "$HOME/.codex/tmp/arg0"'
        )
        completed = _run(
            [wsl, "-d", self.distro, "--exec", "bash", "-lc", script, "torc", executable],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        paths = completed.stdout.strip().splitlines()
        if completed.returncode or len(paths) != 2 or not paths[0]:
            return None
        inline = (
            '{ filesystem={":minimal"="read",'
            f'{json.dumps(paths[0])}="read",{json.dumps(paths[1])}="read",'
            '":workspace_roots"={"."="read"}} }'
        )
        return node, inline

    def probe(self, context: dict[str, Any], stage: str) -> dict[str, Any]:
        evidence = super().probe(context, stage)
        if not evidence.get("available") or evidence.get("boundary_enforced") is not None:
            return evidence
        executable = evidence["_resolved"]
        profile = self._profile(executable)
        forbidden = Path(context["repo_root"]) / "AGENTS.md"
        linux_forbidden = self._path(forbidden)
        if not profile or not linux_forbidden or not forbidden.is_file():
            evidence.update(
                boundary_enforced=False,
                reason="Codex strict permission profile could not be constructed",
            )
            return evidence
        node, inline = profile
        base = [
            self._wsl(),
            "-d",
            self.distro,
            "--exec",
            node,
            executable,
            "sandbox",
            "-c",
            f"permissions.torc_runtime={inline}",
            "-P",
            "torc_runtime",
            "-C",
            evidence["linux_workspace"],
        ]
        positive = _run(
            [*base, "test", "-r", "task.json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        negative = _run(
            [*base, "test", "!", "-r", linux_forbidden],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        enforced = positive.returncode == 0 and negative.returncode == 0
        evidence.update(
            {
                "boundary_enforced": enforced,
                "positive_read_exit_status": positive.returncode,
                "negative_read_exit_status": negative.returncode,
                "permission_profile": "torc_runtime",
                "network_for_generated_commands": "denied",
                "_node": node,
                "_profile": inline,
            }
        )
        if not enforced:
            evidence["reason"] = "Codex permission boundary preflight failed"
        return evidence

    def capture_source(self, context: dict[str, Any]) -> dict[str, Any]:
        evidence = self.probe(context, "source")
        if not evidence.get("available"):
            return self._stopped(evidence, "unavailable")
        if not evidence.get("boundary_enforced"):
            return self._stopped(evidence, "contaminated")
        controls = _stage_controls(context, "source")
        prompt = controls.get("assignment", _SOURCE_ASSIGNMENT)
        if not isinstance(prompt, str) or not prompt:
            evidence["reason"] = "source assignment control is missing or invalid"
            return self._stopped(evidence, "contaminated")
        args = [
            self._wsl(),
            "-d",
            self.distro,
            "--cd",
            evidence["linux_workspace"],
            "--exec",
            evidence["_node"],
            evidence["_resolved"],
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "--skip-git-repo-check",
            "--json",
            "-C",
            evidence["linux_workspace"],
        ]
        if controls.get("model"):
            args.extend(["--model", str(controls["model"])])
        args.extend(
            [
                "-c",
                'default_permissions="torc_runtime"',
                "-c",
                f"permissions.torc_runtime={evidence['_profile']}",
            ]
        )
        for key in ("reasoning_effort", "service_tier"):
            if controls.get(key):
                config_key = (
                    "model_reasoning_effort" if key == "reasoning_effort" else key
                )
                args.extend(["-c", f"{config_key}={json.dumps(controls[key])}"])
        args.append("-")
        completed = _run(
            args,
            input=prompt,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        public = self._public_evidence(evidence)
        _record_controls(public, controls, prompt)
        public["capture_exit_status"] = completed.returncode
        public["output_format"] = "jsonl"
        if completed.returncode:
            public["reason"] = "Codex source capture failed"
            return self._stopped(public, "failed")
        messages = []
        for line in completed.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
        try:
            output = _decode_object(messages[-1] if messages else completed.stdout)
            continuity = output["continuity"]
            if set(continuity) != set(_CONTINUITY_FIELDS):
                raise ValueError("source continuity keys do not match the contract")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            public["reason"] = f"malformed Codex source capture: {exc}"
            return self._stopped(public, "failed")
        return {
            "schema_version": 1,
            "adapter": self.name,
            "disposition": "accepted",
            "continuity": continuity,
            "harness_evidence": public,
        }

    def start_target(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def collect_target(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class ClaudeCodeTargetAdapter(_WslLiveAdapter):
    executable = "claude"
    name = "claude-code"

    def start_target(self, context: dict[str, Any]) -> dict[str, Any]:
        evidence = self.probe(context, "target")
        if not evidence.get("available"):
            return self._stopped(evidence, "unavailable")
        return {
            "adapter": self.name,
            "activation_ref": "claude-code-fresh",
            "disposition": "accepted",
            "harness_evidence": self._public_evidence(evidence),
        }

    def _schema(self) -> dict[str, Any]:
        string_array = {"type": "array", "items": {"type": "string"}}
        properties = {
            field: string_array
            for field in (
                "settled_decisions",
                "active_commitments",
                "hard_constraints",
                "unresolved_work",
                "uncertainties",
                "new_inferences",
            )
        }
        properties.update(
            {
                "lineage_identity": {"type": "string"},
                "current_responsibility": {"type": "string"},
                "handoff_reason": {"const": "task_phase_transition"},
                "source_revision_id": {"const": "p1a-revision-0002"},
                "assertions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["text", "label", "source_ref"],
                        "additionalProperties": False,
                        "properties": {
                            "text": {"type": "string"},
                            "label": {"enum": ["inherited", "new"]},
                            "source_ref": {"type": "string"},
                        },
                    },
                },
                "review_areas": {
                    **string_array,
                    "items": {
                        "enum": ["authority", "artifact-integrity", "adapter-boundary"]
                    },
                    "uniqueItems": True,
                },
                "completion_status": {"enum": ["complete", "incomplete"]},
            }
        )
        return {
            "type": "object",
            "required": ["boundary_probe", "reconstruction"],
            "properties": {
                "boundary_probe": {"const": "denied"},
                "reconstruction": {
                    "type": "object",
                    "required": list(_RECONSTRUCTION_FIELDS),
                    "additionalProperties": False,
                    "properties": properties,
                },
            },
            "additionalProperties": False,
        }

    def collect_target(self, context: dict[str, Any]) -> dict[str, Any]:
        evidence = self.probe(context, "target")
        if not evidence.get("available"):
            return self._stopped(evidence, "unavailable")
        repo = self._path(Path(context["repo_root"]))
        root = Path(context["run_dir"])
        linux_root = self._path(root)
        canary = self._path(Path(context["repo_root"]) / "AGENTS.md")
        if not repo or not linux_root or not canary:
            evidence["reason"] = "Claude filesystem policy paths could not be resolved"
            return self._stopped(evidence, "contaminated")
        denied = [repo]
        for child in root.iterdir():
            if child.name != "workspaces":
                mapped = self._path(child)
                if mapped:
                    denied.append(mapped)
        source_workspace = root / "workspaces" / "source"
        if source_workspace.exists():
            mapped = self._path(source_workspace)
            if mapped:
                denied.append(mapped)
        settings = {
            "permissions": {
                "allow": ["Read(./**)"],
                "deny": [
                    "Bash",
                    "Edit",
                    "Write",
                    "WebFetch",
                    "WebSearch",
                    "Agent",
                    *[f"Read(/{path}/**)" for path in denied],
                ],
                "defaultMode": "dontAsk",
                "disableBypassPermissionsMode": "disable",
            },
            "sandbox": {
                "enabled": True,
                "failIfUnavailable": True,
                "allowUnsandboxedCommands": False,
                "filesystem": {
                    "denyRead": denied,
                    "allowRead": [evidence["linux_workspace"]],
                },
            },
        }
        controls = _stage_controls(context, "target")
        assignment_template = controls.get(
            "assignment_template", _TARGET_ASSIGNMENT_TEMPLATE
        )
        if not isinstance(assignment_template, str) or not assignment_template:
            evidence["reason"] = "target assignment control is missing or invalid"
            return self._stopped(evidence, "contaminated")
        try:
            prompt = assignment_template.format(canary=canary)
        except (KeyError, ValueError) as exc:
            evidence["reason"] = f"target assignment control is invalid: {exc}"
            return self._stopped(evidence, "contaminated")
        args = [
            self._wsl(),
            "-d",
            self.distro,
            "--cd",
            evidence["linux_workspace"],
            "--exec",
            evidence["_resolved"],
        ]
        if controls.get("model"):
            args.extend(["--model", str(controls["model"])])
        if controls.get("reasoning_effort"):
            args.extend(["--effort", str(controls["reasoning_effort"])])
        args.extend(
            [
                "--safe-mode",
                "--setting-sources",
                "local",
                "--settings",
                json.dumps(settings, separators=(",", ":")),
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--tools",
                "Read",
                "--permission-mode",
                "dontAsk",
                "--disable-slash-commands",
                "--no-chrome",
                "--no-session-persistence",
                "--json-schema",
                json.dumps(self._schema(), separators=(",", ":")),
                "--output-format",
                "stream-json",
                "--verbose",
                "--print",
                prompt,
            ]
        )
        completed = _run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        public = self._public_evidence(evidence)
        _record_controls(public, controls, assignment_template)
        public.update(
            {
                "target_exit_status": completed.returncode,
                "fresh_session": True,
                "session_persistence": False,
                "available_tools": ["Read"],
                "sandbox_fail_if_unavailable": True,
            }
        )
        if completed.returncode:
            public["reason"] = "Claude Code target failed"
            return self._stopped(public, "failed")
        try:
            wrapper: dict[str, Any] = {}
            canary_reads: set[str] = set()
            canary_denied = False
            for line in completed.stdout.splitlines():
                event = json.loads(line)
                if event.get("type") == "result":
                    wrapper = event
                message = event.get("message", {})
                for block in message.get("content", []):
                    if block.get("type") == "tool_use" and block.get("name") == "Read":
                        request = block.get("input", {})
                        if (request.get("file_path") or request.get("path")) == canary:
                            canary_reads.add(block["id"])
                    elif (
                        block.get("type") == "tool_result"
                        and block.get("tool_use_id") in canary_reads
                        and block.get("is_error") is True
                    ):
                        canary_denied = True
            output = wrapper.get("structured_output")
            if not isinstance(output, dict):
                output = _decode_object(str(wrapper.get("result", "")))
            reconstruction = output["reconstruction"]
            if set(reconstruction) != set(_RECONSTRUCTION_FIELDS):
                raise ValueError("target reconstruction keys do not match the contract")
            string_lists = (
                "settled_decisions",
                "active_commitments",
                "hard_constraints",
                "unresolved_work",
                "uncertainties",
                "new_inferences",
                "review_areas",
            )
            if any(
                not isinstance(reconstruction[field], list)
                or not all(isinstance(item, str) for item in reconstruction[field])
                for field in string_lists
            ):
                raise ValueError("target reconstruction contains a non-string list")
            if not all(
                isinstance(item, dict) and {"text", "label", "source_ref"} <= set(item)
                for item in reconstruction["assertions"]
            ):
                raise ValueError("target assertions do not match the contract")
            if output.get("boundary_probe") != "denied" or not canary_denied:
                public["reason"] = "Claude parent-read denial was not evidenced"
                return self._stopped(public, "contaminated")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            public["reason"] = f"malformed Claude target output: {exc}"
            return self._stopped(public, "failed")
        public["boundary_enforced"] = True
        public["permission_denial_count"] = 1
        usage = wrapper.get("usage", {})
        return {
            "schema_version": 1,
            "adapter": self.name,
            "disposition": "accepted",
            "task_output": {
                "review_areas": reconstruction.get("review_areas", []),
                "completion_status": reconstruction.get("completion_status"),
                "harness_evidence": public,
            },
            "reconstruction": reconstruction,
            "usage": {"supplied": bool(usage), **usage},
        }

    def capture_source(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


def adapter_for(name: str) -> ExperimentAdapter:
    if name == "replay":
        return ReplayAdapter()
    if name == "codex":
        return CodexSourceAdapter()
    if name == "claude-code":
        return ClaudeCodeTargetAdapter()
    raise ValueError(f"unsupported experiment adapter: {name}")

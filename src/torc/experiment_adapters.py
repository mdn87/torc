"""Thin P1a adapters for deterministic replay and bounded harness probes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol


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
            (Path(context["source_workspace"]) / "task.json").read_text(encoding="utf-8")
        )
        fields = (
            "lineage_identity",
            "current_responsibility",
            "settled_decisions",
            "active_commitments",
            "hard_constraints",
            "unresolved_work",
            "uncertainties",
            "evidence_refs",
        )
        return {
            "schema_version": 1,
            "adapter": self.name,
            "disposition": "accepted",
            "continuity": {field: task[field] for field in fields},
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
            (Path(context["target_workspace"]) / "task.json").read_text(encoding="utf-8")
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
                {
                    "text": item,
                    "label": "inherited",
                    "source_ref": "task.json",
                }
                for field in (
                    "settled_decisions",
                    "active_commitments",
                    "hard_constraints",
                    "unresolved_work",
                )
                for item in task[field]
            ],
            "review_areas": [
                "authority",
                "artifact-integrity",
                "adapter-boundary",
            ],
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


class _LiveProbeAdapter:
    executable = ""
    name = ""

    def probe(self, context: dict[str, Any], stage: str) -> dict[str, Any]:
        resolved = shutil.which(self.executable)
        evidence: dict[str, Any] = {
            "adapter": self.name,
            "stage": stage,
            "available": bool(resolved),
            "command_plan": [self.executable, "--version"],
            "workspace_identity": Path(context[f"{stage}_workspace"]).name,
            "allowed_paths": context.get(f"{stage}_allowed_paths", []),
        }
        if not resolved:
            evidence["reason"] = f"{self.executable} executable not found"
            return evidence
        environment = {
            key: os.environ[key]
            for key in ("PATH", "SystemRoot", "WINDIR", "TMP", "TEMP")
            if key in os.environ
        }
        completed = subprocess.run(
            [resolved, "--version"],
            cwd=context[f"{stage}_workspace"],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        evidence.update(
            {
                "exit_status": completed.returncode,
                "version": (completed.stdout or completed.stderr).strip()[:200],
                "boundary_enforced": False,
                "reason": (
                    "the installed CLI probe does not evidence filesystem read isolation"
                ),
            }
        )
        return evidence

    def _contaminated(self, context: dict[str, Any], stage: str) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "disposition": "contaminated",
            "harness_evidence": self.probe(context, stage),
            "reason": "oracle isolation cannot be evidenced by this local CLI assignment",
        }


class CodexSourceAdapter(_LiveProbeAdapter):
    executable = "codex"
    name = "codex"

    def capture_source(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._contaminated(context, "source")

    def start_target(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def collect_target(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class ClaudeCodeTargetAdapter(_LiveProbeAdapter):
    executable = "claude"
    name = "claude-code"

    def capture_source(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def start_target(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._contaminated(context, "target")

    def collect_target(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._contaminated(context, "target")


def adapter_for(name: str) -> ExperimentAdapter:
    if name == "replay":
        return ReplayAdapter()
    if name == "codex":
        return CodexSourceAdapter()
    if name == "claude-code":
        return ClaudeCodeTargetAdapter()
    raise ValueError(f"unsupported experiment adapter: {name}")

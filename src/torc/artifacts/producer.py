"""Provider-neutral command adapter for Project Snapshot candidates."""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from torc.canonical import canonical_json
from torc.errors import TorcError

from .model import EvidenceBundle, ProjectSnapshot
from .validation import validate_project_snapshot


class ProducerError(TorcError):
    """An external snapshot producer failed or returned an invalid candidate."""


class CommandProjectSnapshotProducer:
    """Run one explicit argv vector with Evidence Bundle JSON on stdin."""

    def __init__(
        self,
        command: Sequence[str],
        schema_dir: Path | str,
        *,
        timeout_seconds: float = 120,
    ) -> None:
        if not command:
            raise ProducerError("producer command is required")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ProducerError("producer timeout must be greater than zero")
        self.command = tuple(command)
        self.schema_dir = Path(schema_dir)
        self.timeout_seconds = timeout_seconds

    def produce(self, evidence_bundle: EvidenceBundle) -> ProjectSnapshot:
        try:
            completed = subprocess.run(
                self.command,
                input=canonical_json(evidence_bundle) + "\n",
                capture_output=True,
                check=False,
                encoding="utf-8",
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProducerError(
                f"producer timed out after {self.timeout_seconds:g} seconds"
            ) from exc
        except OSError as exc:
            raise ProducerError(f"producer could not start: {exc}") from exc
        except UnicodeError as exc:
            raise ProducerError("producer stdout and stderr must be UTF-8") from exc

        if completed.returncode != 0:
            raise ProducerError(f"producer exited with status {completed.returncode}")

        try:
            candidate: Any = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProducerError("producer stdout must be one JSON object") from exc
        if not isinstance(candidate, dict):
            raise ProducerError("producer stdout must be one JSON object")

        result = validate_project_snapshot(candidate, evidence_bundle, self.schema_dir)
        if not result.valid:
            raise ProducerError("producer candidate failed validation: " + "; ".join(result.errors))
        return cast(ProjectSnapshot, candidate)

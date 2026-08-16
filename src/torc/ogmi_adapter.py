"""Narrow subprocess boundary for consuming OGMI continuity records."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .errors import TorcError

_CANONICAL_HASH = re.compile(r"^sha256:([0-9a-f]{64})$")


class OgmiAdapterError(TorcError):
    """OGMI could not prove a bounded continuity reference."""


class OgmiAdapter:
    """Validate, hash, and orient through OGMI's public CLI only."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        max_output_bytes: int = 65_536,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("OGMI timeout must be positive")
        if max_output_bytes <= 0:
            raise ValueError("OGMI output limit must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def resolve(
        self,
        *,
        checkpoint_path: Path | str,
        project_path: Path | str,
        orientation_spine_id: str,
        expected_run_id: str,
        expected_assignment_id: str,
    ) -> dict[str, Any]:
        """Return one validated checkpoint reference and orientation bundle."""

        checkpoint = Path(checkpoint_path).resolve()
        project = Path(project_path).resolve()
        record = self._read_checkpoint(checkpoint)

        validation = self._run_json(
            "validate", str(checkpoint), "--json", label="validate"
        )
        if validation.get("errors") != 0 or validation.get("records") != 1:
            raise OgmiAdapterError("OGMI validate rejected the checkpoint record")

        if record.get("record_type") != "checkpoint":
            raise OgmiAdapterError("OGMI record is not a continuity checkpoint")
        if record.get("schema_version") != "0.1":
            raise OgmiAdapterError("unsupported OGMI checkpoint schema version")
        if record.get("run_id") != expected_run_id:
            raise OgmiAdapterError("OGMI checkpoint run identity does not match binding")
        if record.get("assignment_id") != expected_assignment_id:
            raise OgmiAdapterError(
                "OGMI checkpoint assignment identity does not match binding"
            )
        checkpoint_id = record.get("id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise OgmiAdapterError("OGMI checkpoint identifier is missing")

        digest_output = self._run("hash", str(checkpoint), label="hash").strip()
        try:
            digest_text = digest_output.decode("ascii")
        except UnicodeDecodeError as exc:
            raise OgmiAdapterError("OGMI hash output is not ASCII") from exc
        digest_match = _CANONICAL_HASH.fullmatch(digest_text)
        if digest_match is None:
            raise OgmiAdapterError("OGMI hash output is not a canonical SHA-256 digest")

        orientation = self._run_json(
            "orient", str(project), orientation_spine_id, label="orient"
        )
        validation_view = orientation.get("validation")
        node = orientation.get("node")
        if (
            not isinstance(validation_view, dict)
            or validation_view.get("errors") != 0
            or not isinstance(node, dict)
            or node.get("id") != orientation_spine_id
        ):
            raise OgmiAdapterError("OGMI orientation does not match the pinned spine")

        return {
            "checkpoint_id": checkpoint_id,
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": digest_match.group(1),
            "checkpoint": record,
            "orientation": orientation,
        }

    def _read_checkpoint(self, path: Path) -> dict[str, Any]:
        try:
            if path.stat().st_size > self.max_output_bytes:
                raise OgmiAdapterError("OGMI checkpoint exceeds the output limit")
            value = json.loads(path.read_text(encoding="utf-8"))
        except OgmiAdapterError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise OgmiAdapterError("OGMI checkpoint could not be read") from exc
        if not isinstance(value, dict):
            raise OgmiAdapterError("OGMI checkpoint must be a JSON object")
        return value

    def _run_json(self, *args: str, label: str) -> dict[str, Any]:
        output = self._run(*args, label=label)
        try:
            value = json.loads(output)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise OgmiAdapterError(f"OGMI {label} returned malformed JSON") from exc
        if not isinstance(value, dict):
            raise OgmiAdapterError(f"OGMI {label} did not return a JSON object")
        return value

    def _run(self, *args: str, label: str) -> bytes:
        argv = [sys.executable, "-m", "ogmi", *args]
        try:
            returncode, stdout, _stderr, overflow = self._bounded_process(argv)
        except subprocess.TimeoutExpired as exc:
            raise OgmiAdapterError(f"OGMI {label} timed out") from exc
        except OSError as exc:
            raise OgmiAdapterError(f"OGMI {label} is unavailable") from exc
        if overflow:
            raise OgmiAdapterError(f"OGMI {label} exceeded the output limit")
        if returncode != 0:
            raise OgmiAdapterError(f"OGMI {label} failed")
        return stdout

    def _bounded_process(
        self, argv: list[str]
    ) -> tuple[int, bytes, bytes, bool]:
        """Drain both pipes concurrently while retaining at most the hard ceiling."""

        process = subprocess.Popen(
            argv,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert process.stdout is not None
        assert process.stderr is not None
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        lock = threading.Lock()
        overflow = threading.Event()

        def drain(name: str, stream: Any) -> None:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                with lock:
                    used = len(buffers["stdout"]) + len(buffers["stderr"])
                    remaining = self.max_output_bytes - used
                    if remaining > 0:
                        buffers[name].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()
                if overflow.is_set():
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return

        threads = [
            threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            returncode = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            for thread in threads:
                thread.join(timeout=1)
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        for thread in threads:
            thread.join(timeout=1)
        if any(thread.is_alive() for thread in threads):
            process.stdout.close()
            process.stderr.close()
            for thread in threads:
                thread.join(timeout=1)
        return returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"]), overflow.is_set()

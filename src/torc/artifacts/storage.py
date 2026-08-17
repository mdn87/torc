"""Portable content-addressed filesystem storage for project snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from torc.errors import IntegrityError, NotFoundError, TorcError
from torc.experiment_runs import write_canonical_artifact

from .identity import content_id_is_valid


def _digest_name(value: str) -> str:
    if not value.startswith("sha256:") or len(value) != 71:
        raise IntegrityError(f"invalid content identity: {value}")
    return value.removeprefix("sha256:")


class ArtifactStore:
    """Own the project-snapshot runtime layout without making it canonical truth."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.evidence_dir = self.root / "evidence"
        self.candidates_dir = self.root / "candidates"
        self.accepted_dir = self.root / "accepted"
        self.receipts_dir = self.root / "receipts"
        self.current_ref = self.root / "current.ref"

    @staticmethod
    def _write_record(directory: Path, record: dict[str, Any], identity_field: str) -> Path:
        if not content_id_is_valid(record, identity_field):
            raise IntegrityError(f"{identity_field} does not match record content")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{_digest_name(record[identity_field])}.json"
        write_canonical_artifact(path, record)
        return path

    def write_evidence(self, bundle: dict[str, Any]) -> Path:
        return self._write_record(self.evidence_dir, bundle, "bundle_id")

    def write_candidate(self, snapshot: dict[str, Any]) -> Path:
        return self._write_record(self.candidates_dir, snapshot, "artifact_id")

    def write_receipt(self, receipt: dict[str, Any]) -> Path:
        return self._write_record(self.receipts_dir, receipt, "receipt_id")

    def publish_accepted(self, snapshot: dict[str, Any], receipt: dict[str, Any]) -> Path:
        if receipt.get("status") != "accepted":
            raise TorcError("rejected receipt cannot publish an accepted artifact")
        if not content_id_is_valid(receipt, "receipt_id"):
            raise IntegrityError("receipt identity does not match content")
        if receipt.get("artifact_id") != snapshot.get("artifact_id"):
            raise IntegrityError("receipt does not reference the artifact")
        path = self._write_record(self.accepted_dir, snapshot, "artifact_id")
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.current_ref.with_name(f".{self.current_ref.name}.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{snapshot['artifact_id']}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.current_ref)
        return path

    def current_id(self) -> str:
        if not self.current_ref.is_file():
            raise NotFoundError(f"current project snapshot not found: {self.current_ref}")
        value = self.current_ref.read_text(encoding="utf-8").strip()
        _digest_name(value)
        return value

    def current_artifact(self) -> dict[str, Any]:
        artifact_id = self.current_id()
        path = self.accepted_dir / f"{_digest_name(artifact_id)}.json"
        if not path.is_file():
            raise NotFoundError(f"accepted project snapshot not found: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if (
            not content_id_is_valid(record, "artifact_id")
            or record.get("artifact_id") != artifact_id
        ):
            raise IntegrityError("current accepted artifact failed content verification")
        return record

    def receipt_for_artifact(self, artifact_id: str) -> dict[str, Any]:
        for path in sorted(self.receipts_dir.glob("*.json")):
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("artifact_id") == artifact_id and receipt.get("status") == "accepted":
                if not content_id_is_valid(receipt, "receipt_id"):
                    raise IntegrityError(f"receipt failed content verification: {path}")
                return receipt
        raise NotFoundError(f"accepted receipt not found for {artifact_id}")

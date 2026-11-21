"""Publish an opt-in, display-safe observation of a committed authority lease."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile

from .canonical import canonical_json, payload_sha256
from .errors import IntegrityError, TorcError
from .store import Store

PUBLIC_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 -]{0,31}")


def holder_file(store: Store, lineage_id: str) -> Path:
    key = hashlib.sha256(lineage_id.encode("utf-8")).hexdigest()
    return store.state_dir / "display" / key / "holder.json"


def write_display_file(path: Path, record: dict) -> None:
    data = (canonical_json(record) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.read_bytes() == data:
            return
    except FileNotFoundError:
        pass
    draft = NamedTemporaryFile(dir=path.parent, delete=False)
    try:
        with draft:
            draft.write(data)
            draft.flush()
            os.fsync(draft.fileno())
        Path(draft.name).replace(path)
    finally:
        Path(draft.name).unlink(missing_ok=True)


def publish_holder(store: Store, lineage_id: str) -> Path:
    """Read and publish under one writer lock so a late publisher cannot rewind the Board."""
    from .verify import verify_store

    path = holder_file(store, lineage_id)
    with store.transaction(immediate=True):
        authority = store.current_authority(lineage_id)
        if not verify_store(store, lineage_id)["valid"]:
            raise IntegrityError("cannot report a holder from an unverified lineage")
        lease = store.get_lease(authority["lease_id"])
        public_label = store.get_substrate(authority["substrate_id"]).get("board_label")
        if not isinstance(public_label, str) or not PUBLIC_LABEL.fullmatch(public_label):
            public_label = "Session"
        report = {
            "schemaVersion": 1,
            "holderLabel": public_label,
            "holderTag": payload_sha256([lineage_id, authority["activation_id"]])[:8],
            "heldSince": lease["issued_at"],
        }
        write_display_file(path, report)
    return path


def refresh_enrolled_holder(store: Store, lineage_id: str) -> None:
    """The lease has committed. A display failure is recoverable independently."""
    try:
        if holder_file(store, lineage_id).parent.is_dir():
            publish_holder(store, lineage_id)
    except (OSError, sqlite3.Error, TorcError, ValueError) as exc:
        logging.getLogger(__name__).warning(
            "TORC passage committed. Board update failed. Retry lineage publish-holder "
            "for %s (%s).", lineage_id, type(exc).__name__,
        )

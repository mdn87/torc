"""Create-once publication of sanitized derived artifacts on local filesystems."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from torc.canonical import canonical_json


def publish(root: Path | str, kind: str, payload: dict) -> Path:
    """Publish a complete body or preserve the existing body; never replace it.

    The filename hashes the canonical UTF-8 bytes INCLUDING the final newline.
    A private staging directory isolates writers. Hard-link publication is
    create-once; unlike a retry claim this path is never released or recycled.
    No latest pointer, process coordination or power-loss guarantee is supplied.
    Caller must select a private, ignored derived-output directory, separate
    from the authority store. Raw transcript bytes are not an accepted payload.
    POSIX files use mode 0600; on Windows privacy depends on the caller's
    directory ACL because chmod does not establish an NTFS access boundary.
    """
    if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z_-]{0,63}", kind):
        raise ValueError("invalid artifact kind")
    if not isinstance(payload, dict):
        raise ValueError("artifact payload must be an object")
    data = (canonical_json(payload) + "\n").encode("utf-8")
    directory = Path(root) / kind
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = directory / (hashlib.sha256(data).hexdigest() + ".json")
    with tempfile.TemporaryDirectory(prefix=".publish-", dir=directory) as staging:
        temporary = Path(staging) / "body.json"
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.read_bytes() != data:
                raise ValueError("existing digest path contains different bytes") from None
    return destination

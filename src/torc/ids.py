"""TORC identifier helpers."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def valid_id(value: Any) -> bool:
    """Return whether a value satisfies TORC's shared record identifier contract."""

    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None

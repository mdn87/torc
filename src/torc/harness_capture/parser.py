"""Parse exactly one supplied JSONL prefix without accessing its owner file."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedPrefix:
    records: tuple[dict[str, Any], ...]
    parsed_byte_length: int
    quarantined_tail_bytes: int
    errors: tuple[str, ...]


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON number")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number")
    return result


def parse_prefix(data: bytes, prefix_length: int) -> ParsedPrefix:
    """Stop at the first malformed or unterminated record; quarantine the rest.

    Even valid JSON without its terminating newline is incomplete for this
    adapter. Diagnostics contain no source text. Bytes beyond the declared
    prefix are neither parsed nor included in its byte accounting.
    """
    if not isinstance(data, bytes):
        raise ValueError("data must be bytes")
    if type(prefix_length) is not int or not 0 <= prefix_length <= len(data):
        raise ValueError("prefix length must be within supplied bytes")
    prefix = data[:prefix_length]
    records = []
    offset = 0
    errors = []
    while offset < prefix_length:
        end = prefix.find(b"\n", offset)
        if end < 0:
            errors.append("unterminated_record")
            break
        try:
            record = json.loads(prefix[offset:end].decode("utf-8"),
                                object_pairs_hook=_object, parse_constant=_constant,
                                parse_float=_float)
            if not isinstance(record, dict):
                raise ValueError("record must be an object")
        except (ValueError, RecursionError):
            errors.append("malformed_record")
            break
        records.append(record)
        offset = end + 1
    return ParsedPrefix(tuple(records), offset, prefix_length - offset, tuple(errors))
